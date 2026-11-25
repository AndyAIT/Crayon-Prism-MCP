"""Offline tests for the subscription change tools. No network, fictional data only.

Run with: uv run python -m unittest test_subscription_changes -v
"""
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

import httpx

import server
import subscription_changes as changes

NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def details(**overrides):
    base = {
        "ProductName": "Contoso Suite (NCE)",
        "ProductSku": "SKU1:0002",
        "Status": "Active",
        "Quantity": 20,
        "MinQuantity": 1,
        "MaxQuantity": 1000,
        "IsLocked": False,
        "ModificationLockReason": None,
        "BillingCycle": "Monthly",
        "TermDurationNumber": 1,
        "TermDurationUnit": "MONTHS",
        "NextRenewalDate": "2026-02-01T00:00:00+00:00",
        "CancellationAllowedUntilDate": "2026-01-20T06:50:52.7629034+00:00",
        "MicrosoftCSPScheduledNextTermInstructions": {
            "RenewToProductSku": "SKU1:0002",
            "BillingCycleOption": "Monthly",
            "TermDurationNumber": 1,
            "TermDurationUnit": "MONTHS",
            "Quantity": 20,
            "ActionType": "RenewToNewTerm",
            "ScheduleType": "TermEnd",
        },
    }
    base.update(overrides)
    return base


class PlanTests(unittest.TestCase):
    def test_increase_allowed(self):
        self.assertTrue(changes.plan_increase(details(), 25, NOW)["allowed"])

    def test_increase_must_be_higher(self):
        self.assertFalse(changes.plan_increase(details(), 20, NOW)["allowed"])

    def test_increase_respects_max_lock_and_status(self):
        self.assertFalse(changes.plan_increase(details(), 5000, NOW)["allowed"])
        self.assertFalse(changes.plan_increase(details(IsLocked=True), 25, NOW)["allowed"])
        self.assertFalse(changes.plan_increase(details(Status="Suspended"), 25, NOW)["allowed"])

    def test_reduce_inside_window(self):
        self.assertTrue(changes.plan_reduce_now(details(), 10, NOW)["allowed"])

    def test_reduce_after_window_points_to_renewal(self):
        late = datetime(2026, 1, 21, tzinfo=timezone.utc)
        plan = changes.plan_reduce_now(details(), 10, late)
        self.assertFalse(plan["allowed"])
        self.assertEqual(plan["fallback"], "schedule_subscription_quantity_at_renewal")

    def test_reduce_without_window_date_is_blocked(self):
        plan = changes.plan_reduce_now(details(CancellationAllowedUntilDate=None), 10, NOW)
        self.assertFalse(plan["allowed"])

    def test_schedule_keeps_existing_terms(self):
        plan = changes.plan_schedule(details(), 12, NOW)
        action = plan["request"]["body"]["scheduledActions"][0]
        self.assertEqual(action["scheduledAction"]["quantity"], 12)
        self.assertEqual(action["scheduledAction"]["renewToProductSku"], "SKU1:0002")
        self.assertEqual(action["actionType"], "RenewToNewTerm")

    def test_schedule_builds_instruction_when_none_exists(self):
        plan = changes.plan_schedule(
            details(MicrosoftCSPScheduledNextTermInstructions=None), 12, NOW
        )
        scheduled = plan["request"]["body"]["scheduledActions"][0]["scheduledAction"]
        self.assertEqual(scheduled["renewToProductSku"], "SKU1:0002")
        self.assertEqual(scheduled["billingCycleOption"], "Monthly")

    def test_schedule_never_overwrites_cancellation(self):
        cancelling = details(
            MicrosoftCSPScheduledNextTermInstructions={"ActionType": "Cancel", "ScheduleType": "TermEnd"}
        )
        self.assertFalse(changes.plan_schedule(cancelling, 12, NOW)["allowed"])


class GatingTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(server, "PrismClient")
        self.client = patcher.start().return_value
        self.client.get_subscription_details.return_value = details(
            CancellationAllowedUntilDate="2999-01-01T00:00:00+00:00"
        )
        self.client.change_subscription_quantity.return_value = "ref-1"
        self.addCleanup(patcher.stop)

    def run_tool(self, env, **kwargs):
        with mock.patch.dict(os.environ, env, clear=False):
            if "MCP_ALLOW_WRITES" not in env:
                os.environ.pop("MCP_ALLOW_WRITES", None)
            return server.increase_subscription_quantity("sub-1", 25, **kwargs)

    def test_dry_run_is_default_and_never_writes(self):
        result = self.run_tool({"MCP_ALLOW_WRITES": "true"})
        self.assertEqual(result["status"], "dry_run")
        self.client.change_subscription_quantity.assert_not_called()

    def test_writes_disabled_blocks_real_run(self):
        result = self.run_tool({}, dry_run=False)
        self.assertEqual(result["status"], "writes_disabled")
        self.client.change_subscription_quantity.assert_not_called()

    def test_real_run_completes_once_prism_shows_new_quantity(self):
        before = details(CancellationAllowedUntilDate="2999-01-01T00:00:00+00:00")
        after = details(Quantity=25)
        self.client.get_subscription_details.side_effect = [before, before, after]
        env = {"MCP_ALLOW_WRITES": "true", "MCP_CONFIRM_TIMEOUT_SECONDS": "30", "MCP_CONFIRM_INTERVAL_SECONDS": "0.5"}
        with mock.patch.object(server.time, "sleep"):
            result = self.run_tool(env, dry_run=False)
        self.assertEqual(result["status"], "completed")
        self.client.change_subscription_quantity.assert_called_once_with("sub-1", 25)

    def test_real_run_is_pending_when_change_never_appears(self):
        env = {"MCP_ALLOW_WRITES": "true", "MCP_CONFIRM_TIMEOUT_SECONDS": "0"}
        result = self.run_tool(env, dry_run=False)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["reference"], "ref-1")
        self.assertIn("audit log", result["message"])

    def test_schedule_confirms_against_scheduled_quantity_not_current(self):
        self.client.set_scheduled_actions.return_value = "ref-2"
        applied = details(
            Quantity=20,
            MicrosoftCSPScheduledNextTermInstructions={"ActionType": "RenewToNewTerm", "Quantity": 12},
        )
        self.client.get_subscription_details.side_effect = [details(), details(), applied]
        env = {"MCP_ALLOW_WRITES": "true", "MCP_CONFIRM_TIMEOUT_SECONDS": "30"}
        with mock.patch.dict(os.environ, env), mock.patch.object(server.time, "sleep"):
            result = server.schedule_subscription_quantity_at_renewal("sub-1", 12, dry_run=False)
        self.assertEqual(result["status"], "completed")

    def test_prism_rejection_is_reported_with_hint(self):
        response = httpx.Response(400, text="not allowed", request=httpx.Request("POST", "http://x"))
        self.client.change_subscription_quantity.side_effect = httpx.HTTPStatusError(
            "bad", request=response.request, response=response
        )
        with mock.patch.dict(os.environ, {"MCP_ALLOW_WRITES": "true"}):
            result = server.reduce_subscription_quantity("sub-1", 5, dry_run=False)
        self.assertEqual(result["status"], "rejected_by_prism")
        self.assertIn("schedule_subscription_quantity_at_renewal", result["hint"])


if __name__ == "__main__":
    unittest.main()
