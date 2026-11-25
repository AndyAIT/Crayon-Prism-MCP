from mcp.server.fastmcp import FastMCP
import httpx

import subscription_changes as changes
from prism_client import PrismClient
import hmac
import os
import sys
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")

mcp = FastMCP(
    "Crayon PRISM",
    host="0.0.0.0",
    port=8785,
    streamable_http_path="/mcp"
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that lack the correct `Authorization: Bearer <token>`."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self._token = token.encode()

    async def dispatch(self, request, call_next):
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(
            supplied.strip().encode(), self._token
        ):
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


def run_http() -> None:
    import uvicorn

    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        sys.exit("MCP_AUTH_TOKEN must be set when MCP_TRANSPORT=streamable-http")

    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware, token=token)
    uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port)


@mcp.tool()
def list_customers() -> list[dict]:
    """List all accessible active PRISM customers."""
    client = PrismClient()
    customers = client.search_customers()

    return [
        {
            "CustomerId": customer.get("CustomerId"),
            "CustomerName": customer.get("CustomerName")
        }
        for customer in customers
    ]

@mcp.tool()
def search_customers(search_text: str) -> list[dict]:
    """Search accessible active PRISM customers by name."""
    client = PrismClient()
    customers = client.search_customers(search_text)

    return [
        {
            "CustomerId": customer.get("CustomerId"),
            "CustomerName": customer.get("CustomerName")
        }
        for customer in customers
    ]

@mcp.tool()
def list_microsoft_csp_subscriptions(customer_id: str) -> list[dict]:
    """List Microsoft CSP subscriptions for a given customer."""
    client = PrismClient()
    subscriptions = client.list_microsoft_csp_subscriptions(customer_id)

    return subscriptions


def _await_applied(client, subscription_id, kind, quantity):
    """PRISM answers 202 before the change is processed, so re-read until it shows or time runs out."""
    timeout, interval = changes.confirm_settings()
    deadline = time.monotonic() + timeout
    while True:
        details = client.get_subscription_details(subscription_id)
        if changes.is_applied(kind, details, quantity):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def _apply_change(subscription_id, planner, quantity, dry_run, send, hint=None, kind="quantity"):
    """Plan from live read-only data; only send the write when not a dry run and writes are enabled.
    A real run waits for the change to appear, so 'completed' means PRISM shows the new value."""
    client = PrismClient()
    plan = planner(client.get_subscription_details(subscription_id), quantity)
    if not plan["allowed"]:
        return {"status": "blocked", **plan}
    if dry_run:
        return {
            "status": "dry_run",
            "message": "No change made. Call again with dry_run=false to apply.",
            **plan,
        }
    if not changes.writes_enabled():
        return {
            "status": "writes_disabled",
            "message": "This server is read-only. Set MCP_ALLOW_WRITES=true to enable changes.",
            **plan,
        }
    try:
        reference = send(client)
    except httpx.HTTPStatusError as e:
        return changes.rejection(e, hint)
    if _await_applied(client, subscription_id, kind, quantity):
        return {"status": "completed", "reference": reference, **plan}
    return {
        "status": "pending",
        "reference": reference,
        "message": (
            "PRISM accepted the request but the new value has not appeared yet. Failures are only "
            "visible in the PRISM audit log, so do not assume it worked. Re-check with "
            "get_subscription_change_options, and if it never applies tell the user it failed."
        ),
        **plan,
    }


@mcp.tool()
def get_subscription_change_options(subscription_id: str) -> dict:
    """Read-only. Show the current quantity, limits, lock state, whether seats can still be
    reduced now (cancellation window), and any quantity already scheduled for renewal."""
    client = PrismClient()
    return changes.summarise(client.get_subscription_details(subscription_id))


@mcp.tool()
def increase_subscription_quantity(
    subscription_id: str, new_quantity: int, dry_run: bool = True
) -> dict:
    """Increase seats on a Microsoft CSP subscription to new_quantity. Identify the subscription by
    SubscriptionId; if a customer has several matching subscriptions, ask the user which one.
    Defaults to a dry run that changes nothing. A real run returns 'completed' only once PRISM
    shows the new quantity; 'pending' means it is unconfirmed and must not be reported as done."""
    return _apply_change(
        subscription_id,
        changes.plan_increase,
        new_quantity,
        dry_run,
        lambda c: c.change_subscription_quantity(subscription_id, new_quantity),
    )


@mcp.tool()
def reduce_subscription_quantity(
    subscription_id: str, new_quantity: int, dry_run: bool = True
) -> dict:
    """Reduce seats immediately. Only possible inside the cancellation window. If the result is
    blocked, rejected or still 'pending' (unconfirmed), tell the user and offer
    schedule_subscription_quantity_at_renewal instead. Defaults to a dry run that changes nothing."""
    return _apply_change(
        subscription_id,
        changes.plan_reduce_now,
        new_quantity,
        dry_run,
        lambda c: c.change_subscription_quantity(subscription_id, new_quantity),
        hint="Use schedule_subscription_quantity_at_renewal to reduce at the next renewal.",
    )


@mcp.tool()
def schedule_subscription_quantity_at_renewal(
    subscription_id: str, target_quantity: int, dry_run: bool = True
) -> dict:
    """Set the seat count the subscription will renew with at the end of its current term. Keeps
    the existing renewal product, term and billing cycle. Defaults to a dry run that changes nothing.
    'completed' means PRISM shows the new scheduled quantity; 'pending' means it is unconfirmed."""
    return _apply_change(
        subscription_id,
        changes.plan_schedule,
        target_quantity,
        dry_run,
        lambda c: c.set_scheduled_actions(
            subscription_id,
            changes.plan_schedule(
                c.get_subscription_details(subscription_id), target_quantity
            )["request"]["body"]["scheduledActions"],
        ),
        kind="scheduled",
    )


if __name__ == "__main__":
    if MCP_TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    elif MCP_TRANSPORT == "streamable-http":
        run_http()
    else:
        raise ValueError("Invalid MCP_TRANSPORT value")
