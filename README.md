# Crayon PRISM MCP

A small, read-only Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for querying customers and Microsoft CSP subscriptions through the Crayon PRISM Portal API.

**Current status:** The three tools below have been exercised against PRISM, including an MCP client/server test over **stdio**. This is an early development project, not a packaged production service.

## Available tools

|Tool|Input|Result|
|-|-|-|
|`list\_customers`|None|Accessible active customers, including IDs and names|
|`search\_customers`|`search\_text: str`|Case-insensitive customer-name matches|
|`list\_microsoft\_csp\_subscriptions`|`customer\_id: str` (PRISM CustomerId UUID)|Active Microsoft CSP subscriptions across the customer's matching CSP tenants, including tenant and subscription IDs/names|

The subscription tool is **not** a Microsoft 365-only product filter. It uses the Microsoft CSP subscription API, and currently returns basic subscription identifiers and friendly names, not seat counts, prices, or renewal dates. All tools are read-only.

## Requirements

* Python 3.12 or later (the project was tested with Python 3.12)
* [`uv`](https://docs.astral.sh/uv/)
* Crayon PRISM API client ID and client secret authorised for the `rhipeapi` scope
* Network access to the PRISM identity and API endpoints

Aider and Ollama were used during development but **are not required** to run this repository. Docker is not required for the current stdio version.

## Clone and install

```bash
git clone https://github.com/AndyAIT/Crayon-Prism-MCP.git
cd Crayon-Prism-MCP
uv sync
```

`uv sync` creates/updates the project virtual environment and installs dependencies from `pyproject.toml` and `uv.lock`.

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Ensure `.env` contains these names and values (replace placeholders with your own credentials):

```dotenv
PRISM\_TOKEN\_URL=https://identity.prismportal.online/connect/token
PRISM\_API\_BASE\_URL=https://api.prismportal.online
PRISM\_CLIENT\_ID=your-client-id
PRISM\_CLIENT\_SECRET=your-client-secret
```

Authentication uses OAuth2 client credentials with `grant\_type=client\_credentials` and scope `rhipeapi`. The token is then sent as a bearer token on API requests.

**Security:** Never commit `.env`, client secrets, or access tokens. `.env.example` should contain only non-secret examples. Confirm `.env` is ignored before committing:

```bash
git check-ignore .env
```

## Test the command-line client

List accessible active customers:

```bash
uv run python main.py
```

Search customer names locally, case-insensitively, after retrieving paginated results:

```bash
uv run python main.py contoso
```

The customer list uses the PRISM customer endpoint and retrieves multiple pages as necessary.

## Run the MCP server (stdio)

```bash
uv run python server.py
```

The server communicates via **stdin/stdout** and may appear idle when launched directly. This is expected: it waits for an MCP client. Do not type ordinary prompts into that process. Any application integrating it should launch the server as a subprocess with the repository as its working directory and the configured environment available.

## End-to-end stdio test

The repository includes `test\_mcp.py`, which starts `server.py` as a child process, initializes an MCP session, discovers tools and invokes a tool.

```bash
uv run python test\_mcp.py
```

The development test was last configured to invoke `list\_microsoft\_csp\_subscriptions` for an example customer. **Review the tool name and `customer\_id` in `test\_mcp.py` before running** and replace the customer ID with one accessible to your PRISM account. You can also adapt it to call `search\_customers` with `{"search\_text": "contoso"}` or `list\_customers` with `{}`.

Successful protocol testing should show an initialized connection, the available tool names, and a successful tool result. A successful Python import or direct FastMCP method call alone does not establish that stdio works.

For syntax-only checks:

```bash
uv run python -m py\_compile main.py prism\_client.py server.py test\_mcp.py
```

## Project files

|File|Purpose|
|-|-|
|`prism\_client.py`|Environment configuration, OAuth authentication, customer retrieval/search/pagination and CSP tenant/subscription lookup|
|`server.py`|FastMCP stdio server and tool registrations|
|`main.py`|Command-line customer listing/search test|
|`test\_mcp.py`|MCP client integration test over stdio|
|`pyproject.toml`|Python project and dependency declarations|
|`uv.lock`|Resolved dependency versions|
|`.env.example`|Template for runtime configuration|
|`.gitignore`|Local/secret file exclusions|

During development, `test\_tenants.py` and downloaded Swagger JSON files were used to investigate the API. They are **not required** to run the three MCP tools and may not be included in the repository.

## PRISM API operations currently used

* Token: `POST https://identity.prismportal.online/connect/token` (`application/x-www-form-urlencoded`)
* Customers: `GET https://api.prismportal.online/api/v2/me/customers` (paginated)
* CSP tenants: `GET https://api.prismportal.online/api/v2/microsoftcsp/tenants` (filter by `endCustomerId`, paginated)
* Active CSP subscriptions: `GET https://api.prismportal.online/api/v2/microsoftcsp/tenants/{tenantId}/subscriptions?status=Active`

The implementation uses the actual PRISM response property casing, such as `Items`, `TotalRecords`, `TenantId`, `SubscriptionId`, and `SubscriptionFriendlyName`.

## Current limitations and planned work

* Stdio transport only; no remote Streamable HTTP endpoint or endpoint authentication yet.
* No Docker image or distribution package yet.
* Read-only customer and CSP subscription tools only; no write operations.
* Subscription output is basic. It does not yet provide quantities, billing terms, prices or renewals, nor a verified M365-only filter.
* API access depends on the permissions of the configured PRISM application.
* Additional production hardening may be needed, including token refresh/retry behaviour, structured logging, and automated tests with mocked API responses.

Planned work includes additional read-only PRISM operations, richer subscription metadata, Streamable HTTP transport with appropriate authentication, and Docker packaging.

## Troubleshooting

* **Missing configuration:** Check that `.env` is in the project directory and that all four variable names above are populated.
* **401/403:** Verify PRISM API credentials, scope and authorisation for the requested customer/tenant.
* **404:** Check the API base URL and endpoint path; the identity host and API host are different.
* **Unexpected response shape:** PRISM responses can use PascalCase keys. Inspect a sanitised response and compare with the implementation.
* **MCP client connects but a tool fails:** First confirm `uv run python main.py` works, then inspect the tool's exception without exposing tokens or secrets.

## Development notes

The project was developed on an Apple Silicon Mac mini using `uv`, Aider and Ollama. These development tools are separate from the application runtime. Review all generated changes and test before committing or deploying.

