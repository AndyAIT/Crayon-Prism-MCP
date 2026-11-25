"""Planning and gating logic for subscription quantity changes.

Everything here is pure (no network) so it can be unit tested with mocked data.
"""
import os
import re
from datetime import datetime, timezone

import httpx


def writes_enabled() -> bool:
    return os.getenv("MCP_ALLOW_WRITES", "").strip().lower() in ("1", "true", "yes")


def _parse_date(value):
    if not value:
        return None
    # PRISM returns 7 fractional digits, which fromisoformat rejects.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def summarise(details: dict, now=None) -> dict:
    """Facts an AI needs to choose which change is possible right now."""
    now = now or datetime.now(timezone.utc)
    cancel_until = _parse_date(details.get("CancellationAllowedUntilDate"))
    scheduled = details.get("MicrosoftCSPScheduledNextTermInstructions") or {}
    return {
        "ProductName": details.get("ProductName"),
        "Status": details.get("Status"),
        "Quantity": details.get("Quantity"),
        "MinQuantity": details.get("MinQuantity"),
        "MaxQuantity": details.get("MaxQuantity"),
        "IsLocked": bool(details.get("IsLocked")),
        "ModificationLockReason": details.get("ModificationLockReason"),
        "CancellationAllowedUntilDate": details.get("CancellationAllowedUntilDate"),
        "CanReduceNow": bool(cancel_until and now <= cancel_until),
        "NextRenewalDate": details.get("NextRenewalDate"),
        "ScheduledNextTermAction": scheduled.get("ActionType"),
        "ScheduledNextTermQuantity": scheduled.get("Quantity"),
    }


def _blocked(reason: str, **extra) -> dict:
    return {"allowed": False, "reason": reason, **extra}


def _common_checks(info: dict, quantity: int):
    if info["Status"] != "Active":
        return f"Subscription status is {info['Status']}, not Active."
    if info["IsLocked"]:
        return f"Subscription is locked: {info['ModificationLockReason'] or 'another operation is in progress'}."
    if quantity < (info["MinQuantity"] or 0):
        return f"Quantity {quantity} is below the minimum of {info['MinQuantity']}."
    if info["MaxQuantity"] is not None and quantity > info["MaxQuantity"]:
        return f"Quantity {quantity} is above the maximum of {info['MaxQuantity']}."
    return None


def plan_increase(details: dict, new_quantity: int, now=None) -> dict:
    info = summarise(details, now)
    problem = _common_checks(info, new_quantity)
    if problem:
        return _blocked(problem, current=info)
    if new_quantity <= info["Quantity"]:
        return _blocked(
            f"New quantity {new_quantity} is not higher than the current {info['Quantity']}.",
            current=info,
        )
    return {
        "allowed": True,
        "current": info,
        "request": {"method": "POST", "path": f"quantity/{new_quantity}"},
    }


def plan_reduce_now(details: dict, new_quantity: int, now=None) -> dict:
    info = summarise(details, now)
    problem = _common_checks(info, new_quantity)
    if problem:
        return _blocked(problem, current=info)
    if new_quantity >= info["Quantity"]:
        return _blocked(
            f"New quantity {new_quantity} is not lower than the current {info['Quantity']}.",
            current=info,
        )
    if not info["CanReduceNow"]:
        return _blocked(
            "The cancellation window for this subscription has closed "
            f"(allowed until {info['CancellationAllowedUntilDate']}), so seats cannot be "
            "reduced now. Use schedule_subscription_quantity_at_renewal to reduce at the next renewal.",
            current=info,
            fallback="schedule_subscription_quantity_at_renewal",
        )
    return {
        "allowed": True,
        "current": info,
        "request": {"method": "POST", "path": f"quantity/{new_quantity}"},
    }


def _camel(instruction: dict) -> dict:
    return {key[0].lower() + key[1:]: value for key, value in instruction.items()}


def plan_schedule(details: dict, target_quantity: int, now=None) -> dict:
    """Change only the quantity of the instruction PRISM already holds for the next term."""
    info = summarise(details, now)
    problem = _common_checks(info, target_quantity)
    if problem:
        return _blocked(problem, current=info)

    instruction = dict(details.get("MicrosoftCSPScheduledNextTermInstructions") or {})
    if instruction.get("ActionType") == "Cancel":
        return _blocked(
            "The subscription is currently scheduled to cancel at renewal; "
            "this tool will not overwrite a cancellation.",
            current=info,
        )
    if not instruction:
        instruction = {
            "RenewToProductSku": details.get("ProductSku"),
            "BillingCycleOption": details.get("BillingCycle"),
            "TermDurationNumber": details.get("TermDurationNumber"),
            "TermDurationUnit": details.get("TermDurationUnit"),
            "ActionType": "RenewToNewTerm",
            "ScheduleType": "TermEnd",
        }
    instruction["Quantity"] = target_quantity

    body = _camel(instruction)
    return {
        "allowed": True,
        "current": info,
        "request": {
            "method": "PUT",
            "path": "scheduled-actions",
            "body": {
                "scheduledActions": [
                    {
                        "actionType": body.get("actionType"),
                        "scheduleType": body.get("scheduleType"),
                        "scheduledAction": body,
                    }
                ]
            },
        },
    }


def rejection(error: httpx.HTTPStatusError, hint=None) -> dict:
    result = {
        "status": "rejected_by_prism",
        "http_status": error.response.status_code,
        "detail": error.response.text[:500],
    }
    if hint:
        result["hint"] = hint
    return result
