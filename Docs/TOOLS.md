# Tool reference

The server exposes seven MCP tools: three read-only lookups, one read-only inspection tool and three gated change tools. All examples use fictional data (Contoso, placeholder IDs).

| Tool | Type | Purpose |
|---|---|---|
| [`list_customers`](#list_customers) | Read | List accessible active customers |
| [`search_customers`](#search_customers) | Read | Find customers by name |
| [`list_microsoft_csp_subscriptions`](#list_microsoft_csp_subscriptions) | Read | List a customer's active Microsoft CSP subscriptions |
| [`get_subscription_change_options`](#get_subscription_change_options) | Read | Show what quantity changes are possible right now |
| [`increase_subscription_quantity`](#increase_subscription_quantity) | Write (gated) | Raise seats now |
| [`reduce_subscription_quantity`](#reduce_subscription_quantity) | Write (gated) | Reduce seats now, inside the cancellation window |
| [`schedule_subscription_quantity_at_renewal`](#schedule_subscription_quantity_at_renewal) | Write (gated) | Set the seat count for the next term |

## Typical workflow

1. `search_customers` to find the customer and its `CustomerId`.
2. `list_microsoft_csp_subscriptions` to see its subscriptions and their `SubscriptionId` values. A customer can hold several subscriptions for the same product, so identify the right one by `SubscriptionId` (check name, quantity and renewal date, and ask the user if more than one matches).
3. `get_subscription_change_options` to see which change is allowed.
4. A change tool with the default `dry_run=true` to preview the exact request.
5. The same change tool with `dry_run=false` to apply it (needs `MCP_ALLOW_WRITES=true`).

## Read tools

### list_customers

No input. Returns the active customers the configured PRISM application can access, each with `CustomerId` and `CustomerName`. Results are paginated internally.

### search_customers

| Input | Type | Notes |
|---|---|---|
| `search_text` | string | Case-insensitive match on the customer name |

Returns the same shape as `list_customers`, filtered. Several customers can match one search text, so confirm the right one before using its ID.

### list_microsoft_csp_subscriptions

| Input | Type | Notes |
|---|---|---|
| `customer_id` | string | PRISM `CustomerId` (UUID) |

Returns the customer's active Microsoft CSP subscriptions across its matching CSP tenants, including `TenantId`, `SubscriptionId`, `SubscriptionFriendlyName`, `ProductName`, `Quantity`, `Status`, billing cycle, term and `NextRenewalDate`.

This is **not** a Microsoft 365-only filter, and it carries no pricing. A customer with no CSP tenants returns an empty list. The tool fetches each subscription's details individually, so customers with many subscriptions can take a while.

### get_subscription_change_options

| Input | Type | Notes |
|---|---|---|
| `subscription_id` | string | PRISM `SubscriptionId` (UUID) |

Read-only. Returns the facts needed to pick a change:

```json
{
  "ProductName": "Contoso Suite (NCE Product)",
  "Status": "Active",
  "Quantity": 20,
  "MinQuantity": 1,
  "MaxQuantity": 300,
  "IsLocked": false,
  "ModificationLockReason": null,
  "CancellationAllowedUntilDate": "2026-01-08T00:00:00+00:00",
  "CanReduceNow": false,
  "NextRenewalDate": "2026-02-08T00:00:00+00:00",
  "ScheduledNextTermAction": null,
  "ScheduledNextTermQuantity": null
}
```

`CanReduceNow` is true only while the current time is on or before `CancellationAllowedUntilDate`. That date is the grace window in which Microsoft allows seats to be removed. After it closes, only a scheduled reduction at renewal is possible.

## Change tools

The three change tools share the same safety model.

| Input | Type | Notes |
|---|---|---|
| `subscription_id` | string | PRISM `SubscriptionId` (UUID) |
| `new_quantity` / `target_quantity` | integer | The new **total** seat count, not the amount to add or remove |
| `dry_run` | boolean | Defaults to `true` |

### Gating

1. **Dry run (default).** Reads live data only, validates the change and returns the exact request that would be sent. Nothing is written.
2. **Real run.** Needs `dry_run=false` **and** `MCP_ALLOW_WRITES=true` on the server. Without the flag the result is `writes_disabled`.
3. **Confirmation.** PRISM answers `202 Accepted` before it has processed the change, so the server then re-reads the subscription until the new value shows, or until `MCP_CONFIRM_TIMEOUT_SECONDS` (default 60) runs out, polling every `MCP_CONFIRM_INTERVAL_SECONDS` (default 5). A real run can therefore take up to about a minute.

### Result statuses

| `status` | Meaning |
|---|---|
| `dry_run` | Valid and previewed. Nothing was sent. |
| `blocked` | Refused before contacting PRISM. See `reason`; `fallback` names an alternative tool where one exists. |
| `writes_disabled` | A real run was requested but the server has `MCP_ALLOW_WRITES` off. |
| `rejected_by_prism` | PRISM refused the request. `http_status` and `detail` explain why; `hint` may suggest the fallback. |
| `completed` | PRISM accepted the change and now shows the new value. |
| `pending` | PRISM accepted the request but the new value had not appeared when the wait ended. PRISM reports a failed change only in its audit log, not through the API, so treat this as **unconfirmed**: re-check with `get_subscription_change_options`, and if it never applies tell the user it failed. |

A `completed` or `pending` result includes a `reference` (PRISM's process identifier).

### Common checks

Every change tool refuses (`blocked`) unless the subscription is `Active`, is not locked, and the requested quantity is within `MinQuantity` and `MaxQuantity`.

### increase_subscription_quantity

Raises the seat count immediately. The new quantity must be higher than the current one. Confirmation compares the current `Quantity`.

### reduce_subscription_quantity

Lowers the seat count immediately. The new quantity must be lower than the current one, and the cancellation window must still be open. If the window has closed (or PRISM supplies no date) the tool returns `blocked` with `fallback: schedule_subscription_quantity_at_renewal`. If PRISM rejects an attempt anyway, `rejected_by_prism` carries the same hint, so an AI client should explain this and offer to schedule the reduction at renewal instead.

### schedule_subscription_quantity_at_renewal

Sets the seat count the subscription will renew with at the end of its current term. It copies the instruction PRISM already holds for the next term and changes only the quantity, so the renewal product, term length and billing cycle are kept. If no instruction exists, it builds a plain renew-to-new-term instruction from the subscription's current details. It refuses to overwrite a scheduled **cancellation**. Confirmation compares `ScheduledNextTermQuantity`, not the current quantity, which stays unchanged until renewal.

Example dry-run result (abridged):

```json
{
  "status": "dry_run",
  "message": "No change made. Call again with dry_run=false to apply.",
  "allowed": true,
  "request": {
    "method": "PUT",
    "path": "scheduled-actions",
    "body": {
      "scheduledActions": [
        {
          "actionType": "RenewToNewTerm",
          "scheduleType": "TermEnd",
          "scheduledAction": {
            "renewToProductSku": "SKU1:0002",
            "billingCycleOption": "Monthly",
            "termDurationNumber": 1,
            "termDurationUnit": "MONTHS",
            "actionType": "RenewToNewTerm",
            "scheduleType": "TermEnd",
            "quantity": 18
          }
        }
      ]
    }
  }
}
```

## PRISM endpoints used

| Tool | Endpoint |
|---|---|
| Customer tools | `GET /api/v2/me/customers` |
| `list_microsoft_csp_subscriptions` | `GET /api/v2/microsoftcsp/tenants`, `GET /api/v2/microsoftcsp/tenants/{tenantId}/subscriptions?status=Active`, then per-subscription details |
| `get_subscription_change_options` and dry runs | `GET` subscription details |
| `increase_…` and `reduce_…` | `POST /api/v2/microsoftcsp/subscriptions/{id}/quantity/{newQuantity}` |
| `schedule_…` | `PUT /api/v2/microsoftcsp/subscriptions/{id}/scheduled-actions` |

## Not covered

* Adding a new product or SKU to a customer, creating subscriptions, cancelling subscriptions, or clearing a scheduled change.
* Per-user authorisation. The HTTP endpoint uses one shared bearer token.
* A direct way to see why PRISM failed a change. Check the PRISM audit log.
