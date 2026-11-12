# Docker Deployment Guide

Deploy the Crayon PRISM MCP server as a container with Docker Compose. This guide is platform-neutral and assumes no particular host directory, operating system, or existing container stack.

## Features

The server exposes three read-only MCP tools:

- `list_customers()` retrieves accessible active PRISM customers.
- `search_customers(search_text)` searches customer names case-insensitively.
- `list_microsoft_csp_subscriptions(customer_id)` retrieves active Microsoft CSP subscriptions associated with a PRISM customer.

The subscription tool does **not** guarantee Microsoft 365-only results. It returns basic subscription and tenant information, not licence quantities or billing details.

## Prerequisites

- Docker with the Compose v2 plugin
- Git, or a downloaded source archive
- PRISM API client ID and client secret authorised for the `rhipeapi` scope
- Outbound HTTPS access to the PRISM identity and API services
- A free host port (the examples use `8785`)

No host Python installation, Aider, Ollama or Node.js is required.

## 1. Get the source

```sh
git clone https://github.com/AndyAIT/Crayon-Prism-MCP.git
cd Crayon-Prism-MCP
```

Alternatively, download and extract the repository archive. Confirm it contains `Dockerfile`, `.dockerignore`, `server.py`, `prism_client.py`, `pyproject.toml` and `uv.lock`.

## 2. Configure credentials

Create a local `.env` in the deployment directory, based on `.env.example`:

```dotenv
PRISM_TOKEN_URL=https://identity.prismportal.online/connect/token
PRISM_API_BASE_URL=https://api.prismportal.online
PRISM_CLIENT_ID=REPLACE_WITH_CLIENT_ID
PRISM_CLIENT_SECRET=REPLACE_WITH_CLIENT_SECRET
```

Keep `.env` out of Git and the image build context. Never place credentials directly in the Compose file, Dockerfile or public issue reports. Use a dedicated secrets solution where appropriate for production.

## 3. Create the Compose configuration

Create `compose.yaml` in the repository root:

```yaml
services:
  prism-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    image: prism-mcp:local
    container_name: prism-mcp
    restart: unless-stopped
    ports:
      - "127.0.0.1:8785:8785"
    environment:
      MCP_TRANSPORT: streamable-http
      PRISM_TOKEN_URL: ${PRISM_TOKEN_URL}
      PRISM_API_BASE_URL: ${PRISM_API_BASE_URL}
      PRISM_CLIENT_ID: ${PRISM_CLIENT_ID}
      PRISM_CLIENT_SECRET: ${PRISM_CLIENT_SECRET}
```

The example binds to loopback for **local-only testing**. For deployment in an existing Compose stack, merge the `prism-mcp` service under that stack's existing `services:` key and adjust the build context relative to its Compose file. If access from another host or container is required, configure an appropriate private network route and authentication before changing exposure.

## 4. Build and start

```sh
docker compose config --quiet
docker compose config --services
docker compose build prism-mcp
docker compose up -d --no-deps prism-mcp
docker compose ps prism-mcp
docker compose logs --tail=50 prism-mcp
```

The container should start a Streamable HTTP MCP server listening on port `8785`, with the endpoint at `/mcp`.

Do not publish the expanded output of `docker compose config`, which may reveal environment-variable values.

## 5. Check the endpoint

```sh
curl -i http://127.0.0.1:8785/mcp
```

A plain GET can return `406 Not Acceptable` because it lacks MCP protocol headers. That establishes HTTP reachability, **not** successful MCP tool execution.

## 6. Test the MCP protocol using curl

These examples use standard HTTP requests and JSON-RPC. Some MCP servers respond using Server-Sent Events (`event: message` followed by `data: ...`) rather than plain JSON. Preserve the session identifier from the initialization response.

### Initialize

```sh
curl -i -N -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}}}'
```

Expect HTTP 200 with server capabilities. Copy the value of the `mcp-session-id` response header and substitute it for `YOUR_SESSION_ID` below. Complete initialization:

```sh
curl -i -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: YOUR_SESSION_ID' \
  -H 'MCP-Protocol-Version: 2025-03-26' \
  --data-binary '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

### Discover tools

```sh
curl -N -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: YOUR_SESSION_ID' \
  -H 'MCP-Protocol-Version: 2025-03-26' \
  --data-binary '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

Expected tool names: `list_customers`, `search_customers`, `list_microsoft_csp_subscriptions`.

### Invoke list_customers

```sh
curl -N -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: YOUR_SESSION_ID' \
  -H 'MCP-Protocol-Version: 2025-03-26' \
  --data-binary '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_customers","arguments":{}}}'
```

### Invoke search_customers

```sh
curl -N -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: YOUR_SESSION_ID' \
  -H 'MCP-Protocol-Version: 2025-03-26' \
  --data-binary '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_customers","arguments":{"search_text":"Contoso"}}}'
```

`Contoso` is fictional; substitute a customer name accessible to your own API credentials for a meaningful result.

### Invoke list_microsoft_csp_subscriptions

```sh
curl -N -X POST http://127.0.0.1:8785/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: YOUR_SESSION_ID' \
  -H 'MCP-Protocol-Version: 2025-03-26' \
  --data-binary '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"list_microsoft_csp_subscriptions","arguments":{"customer_id":"00000000-0000-4000-8000-000000000001"}}}'
```

The UUID above is a **synthetic placeholder**. Replace it with an authorised PRISM `CustomerId` from a customer-list or search response. An empty result for the placeholder is expected. Check the MCP response for `isError`; HTTP 200 alone does not mean the tool succeeded.

> **Shell quoting:** The single-quoted JSON arguments above are suitable for POSIX-style shells. On shells that handle quoting differently, place the JSON request body in a UTF-8 file and use `curl --data-binary @request.json`, or use an MCP client SDK.

## 7. Update

From the cloned repository:

```sh
git pull --ff-only origin main
docker compose up -d --no-deps --build prism-mcp
docker compose logs --tail=50 prism-mcp
```

If using a source archive rather than Git, replace the source files before rebuilding. Keep the local `.env` and any deployment-specific Compose configuration private.

## Troubleshooting

- **Service not found:** Check `docker compose config --services` and the service name `prism-mcp`.
- **Compose YAML error:** Verify indentation, quoting and placement under `services:`.
- **Container exits:** Inspect `docker compose logs --tail=100 prism-mcp`.
- **Connection refused:** Confirm the container is running, the port is available, and the host binding is appropriate.
- **406 response:** Include `Accept: application/json, text/event-stream` for MCP requests.
- **Invalid or missing session:** Reinitialize and reuse the returned `Mcp-Session-Id`.
- **PRISM 401/403:** Check credentials, scope and permissions without exposing secrets.
- **No matching records:** Check that the example name/ID has been replaced with an authorised customer.

## Security

The tools are read-only, but they expose customer and subscription information. The basic server configuration does **not** itself provide public-client authentication. Keep it on a trusted network until an appropriate authentication and authorization layer is implemented. A tunnel or TLS alone does not grant authorization.

Never publish secrets, real customer identifiers, tenant domains, raw API responses, or unredacted container environment/configuration output. Review Git history as well as current files before making a repository public.
