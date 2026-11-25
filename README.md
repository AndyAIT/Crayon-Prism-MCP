# Crayon PRISM MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) server for the Crayon PRISM Portal API. It lets an AI client look up customers and Microsoft CSP subscriptions, and, with explicit opt-in, change subscription seat counts.

* **Seven tools:** four read-only, three gated writes. See [Docs/TOOLS.md](Docs/TOOLS.md).
* **Transports:** stdio (local clients) and Streamable HTTP (containers, remote clients).
* **Safe by default:** change tools only preview (`dry_run`) unless the server is explicitly started with `MCP_ALLOW_WRITES=true`.

> This is an unofficial community project, not affiliated with or endorsed by Crayon. It can change real subscriptions and billing when writes are enabled. Test against non-critical data first and review the behaviour described below.

## Tools

| Tool | Type | Purpose |
|---|---|---|
| `list_customers` | Read | List accessible active customers |
| `search_customers` | Read | Find customers by name |
| `list_microsoft_csp_subscriptions` | Read | List a customer's active Microsoft CSP subscriptions |
| `get_subscription_change_options` | Read | Show which quantity changes are possible now |
| `increase_subscription_quantity` | Write | Raise seats now |
| `reduce_subscription_quantity` | Write | Reduce seats now (cancellation window only) |
| `schedule_subscription_quantity_at_renewal` | Write | Set the seat count for the next term |

Full parameters, result statuses and examples: [Docs/TOOLS.md](Docs/TOOLS.md).

## How changes are made safely

1. Change tools default to `dry_run=true`: they read live data, validate, and return the exact request without sending it.
2. A real change needs `dry_run=false` **and** `MCP_ALLOW_WRITES=true` on the server.
3. PRISM replies `202 Accepted` before it processes a change, and reports failures only in its audit log. The server therefore re-reads the subscription and returns `completed` only once the new value is visible; otherwise it returns `pending` (unconfirmed). Never treat an accepted request as a finished change.
4. Reductions outside the cancellation window are blocked up front, with the renewal-time schedule offered as the alternative.

## Requirements

* Python 3.12 or later and [uv](https://docs.astral.sh/uv/), or Docker
* A PRISM API client ID and secret authorised for the `rhipeapi` scope

## Configuration

Copy `.env.example` to `.env` (it is git-ignored) and fill it in:

| Variable | Required | Purpose |
|---|---|---|
| `PRISM_TOKEN_URL` | Yes | PRISM identity token endpoint |
| `PRISM_API_BASE_URL` | Yes | PRISM API base URL |
| `PRISM_CLIENT_ID` | Yes | API client ID |
| `PRISM_CLIENT_SECRET` | Yes | API client secret |
| `MCP_TRANSPORT` | No | `stdio` (default) or `streamable-http` |
| `MCP_AUTH_TOKEN` | HTTP only | Shared bearer token; the server will not start in HTTP mode without it |
| `MCP_ALLOW_WRITES` | No | `true`/`1`/`yes` lets change tools act. Default off |
| `MCP_CONFIRM_TIMEOUT_SECONDS` | No | How long to wait for a change to appear (default 60) |
| `MCP_CONFIRM_INTERVAL_SECONDS` | No | Poll interval (default 5, minimum 0.5) |

Never commit `.env`, API responses, or customer data.

## Run locally

```sh
uv sync
uv run python server.py          # stdio
```

An example stdio client entry:

```json
{
  "mcpServers": {
    "prism": {
      "command": "uv",
      "args": ["--directory", "/path/to/Crayon-Prism-MCP", "run", "python", "server.py"]
    }
  }
}
```

## Run in Docker (HTTP)

```sh
docker compose up -d --build prism-mcp
```

The endpoint is `http://127.0.0.1:8785/mcp` and requires `Authorization: Bearer <MCP_AUTH_TOKEN>`. Full guide, curl tests and troubleshooting: [Docs/DOCKER_INSTALL.md](Docs/DOCKER_INSTALL.md). Put TLS in front of it (for example a tunnel or reverse proxy) before exposing it beyond localhost.

## Tests

```sh
uv run python -m unittest test_subscription_changes -v
```

These are offline unit tests with fictional data. `test_mcp.py` is a stdio integration test that calls the live PRISM API and needs real credentials; its customer ID is a placeholder.

## Project files

| File | Purpose |
|---|---|
| `server.py` | MCP server, tool definitions, bearer-token middleware |
| `prism_client.py` | PRISM API client (authentication, customers, subscriptions, changes) |
| `subscription_changes.py` | Pure validation and planning logic for quantity changes |
| `main.py` | Small command-line customer list/search helper |
| `test_subscription_changes.py` | Offline unit tests |
| `test_mcp.py` | Live stdio integration test |
| `Dockerfile`, `compose.yaml` | Container build and Compose service |
| `Docs/TOOLS.md` | Tool reference |
| `Docs/DOCKER_INSTALL.md` | Docker deployment guide |
| `CHANGELOG.md` | Release notes |
| `LICENSE` | MIT licence |

The `Dockerfile` copies source files by name. If you add a module, add it to the `COPY` line or the image will fail at startup.

## Known limitations

* One shared bearer token, not per-user authorisation.
* Access tokens are not cached; each tool call authenticates afresh.
* Listing subscriptions fetches details one by one, so large customers are slow.
* No tools yet for adding products, creating or cancelling subscriptions, or clearing a scheduled change.
* PRISM exposes no process-status endpoint, so a failed change is detectable only as `pending` here and in the PRISM audit log.
* The PRISM swagger file is not included in this repository.

## Contributing

Issues and pull requests are welcome. Keep examples fictional, and never include real customer names, identifiers, tenant domains, credentials or raw API responses in code, tests, docs, issues or commits.

## Licence

[MIT](LICENSE).
