from mcp.server.fastmcp import FastMCP
from prism_client import PrismClient
import os

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")

mcp = FastMCP(
    "Crayon PRISM",
    host="0.0.0.0",
    port=8785,
    streamable_http_path="/mcp"
)


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
        mcp.run(transport="streamable-http")
    else:
        raise ValueError("Invalid MCP_TRANSPORT value")
