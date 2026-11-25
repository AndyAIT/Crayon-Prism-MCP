from mcp.server.fastmcp import FastMCP
from prism_client import PrismClient
import hmac
import os
import sys

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

if __name__ == "__main__":
    if MCP_TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    elif MCP_TRANSPORT == "streamable-http":
        run_http()
    else:
        raise ValueError("Invalid MCP_TRANSPORT value")
