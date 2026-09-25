import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agent.settings import MCP_URL


async def call_remote(name, arguments):
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)

    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    if result.isError:
        return {"error": text or f"{name} failed on the MCP server"}
    return json.loads(text)


def call_tool(name, arguments):
    try:
        return asyncio.run(call_remote(name, arguments))
    except Exception as failure:
        return {"error": f"could not reach the MCP server at {MCP_URL} for {name}: {failure}"}
