# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

* Gated subscription quantity tools: `get_subscription_change_options` (read-only), `increase_subscription_quantity`, `reduce_subscription_quantity` and `schedule_subscription_quantity_at_renewal`. See `Docs/TOOLS.md`.
* `dry_run` (default `true`) on every change tool, and the `MCP_ALLOW_WRITES` switch that must be on before a real change is sent.
* Confirmation after a change is accepted: the server re-reads the subscription and reports `completed` or `pending`. Configurable with `MCP_CONFIRM_TIMEOUT_SECONDS` and `MCP_CONFIRM_INTERVAL_SECONDS`.
* Bearer-token authentication (`MCP_AUTH_TOKEN`) for the Streamable HTTP transport. The server refuses to start without a token.
* `compose.yaml` for running the server in Docker.
* Offline unit tests for the change logic (`test_subscription_changes.py`), using fictional data.
* `LICENSE` (MIT), `CHANGELOG.md` and `Docs/TOOLS.md`.

### Changed

* PRISM authentication failures now raise a clear error instead of sending `Bearer None`; diagnostics go to stderr.
* The Docker image includes `subscription_changes.py`.
* README and Docker guide rewritten for the current tool set.

### Fixed

* Change tools no longer report success when PRISM has only queued the request: a `202` is now treated as unconfirmed until the new value appears.

## [0.1.0] - 2026-11-12

### Added

* MCP server for the Crayon PRISM Portal API with read-only tools `list_customers`, `search_customers` and `list_microsoft_csp_subscriptions`.
* OAuth2 client-credentials authentication and paginated customer retrieval.
* stdio transport, Streamable HTTP transport and a Dockerfile.
* Command-line customer list/search (`main.py`) and a sanitised MCP stdio integration test (`test_mcp.py`).
* Docker deployment guide.
