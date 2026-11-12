"""
Crayon PRISM MCP stdio integration test.

Uses fictional customer information by default.

For live testing, optionally configure:
    TEST_CUSTOMER_SEARCH
    TEST_CUSTOMER_ID

Never commit real customer information or credentials.
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


TEST_CUSTOMER_SEARCH = os.getenv(
    "TEST_CUSTOMER_SEARCH",
    "Contoso"
)

TEST_CUSTOMER_ID = os.getenv(
    "TEST_CUSTOMER_ID",
    "00000000-0000-4000-8000-000000000001"
)


async def main():

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"]
    )

    print("Starting Crayon PRISM MCP server...")

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("MCP connection established!")

            # Discover tools
            tools = await session.list_tools()

            print("\nAvailable MCP tools:")

            for tool in tools.tools:
                print(f" - {tool.name}")

            # Test customer listing
            print("\nTesting list_customers...")

            result = await session.call_tool(
                "list_customers",
                arguments={}
            )

            print(
                "list_customers:",
                "ERROR" if result.isError else "SUCCESS"
            )

            # Test customer searching
            print(
                f"\nTesting search_customers "
                f"with '{TEST_CUSTOMER_SEARCH}'..."
            )

            result = await session.call_tool(
                "search_customers",
                arguments={
                    "search_text": TEST_CUSTOMER_SEARCH
                }
            )

            print(
                "search_customers:",
                "ERROR" if result.isError else "SUCCESS"
            )

            # Test subscription listing
            print("\nTesting list_microsoft_csp_subscriptions...")

            result = await session.call_tool(
                "list_microsoft_csp_subscriptions",
                arguments={
                    "customer_id": TEST_CUSTOMER_ID
                }
            )

            print(
                "list_microsoft_csp_subscriptions:",
                "ERROR" if result.isError else "SUCCESS"
            )

            print("\nMCP integration tests completed.")


if __name__ == "__main__":
    asyncio.run(main())