import os
import uuid

import anyio
from langchain_core.messages import HumanMessage
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from agent.graph import initial_state
from agent.tools import dossier_tools, web_tools
from api.events import get_graph

server = FastMCP(
    "dossier",
    instructions=(
        "Dossier is a research case file of discrete, sourced findings organised by topic and "
        "information category. Call get_info before retrieve so you use the real topic and "
        "category keys. Use ask to put a question to the full Dossier agent."
    ),
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8001")),
)


class Finding(BaseModel):
    information: str = Field(description="the snake_case category the fact belongs to, such as pricing or limitations")
    claim: str = Field(description="one self-contained sentence stating a single fact")
    source: str = Field(description="the exact http or https url the fact was read on")
    date: str = Field(default="", description="publication date as YYYY-MM-DD, or empty for today")


@server.tool(description="Search the live web and get back titles, urls and snippets.")
def web_search(query: str) -> dict:
    return web_tools.web_search(query)


@server.tool(description="Read one web page and get back its article text.")
def web_fetch(url: str) -> dict:
    return web_tools.fetch_page(url)


@server.tool(description="List every topic in the case file and the information categories each holds, with counts.")
def get_info() -> dict:
    return dossier_tools.get_dossier_structure()


@server.tool(description="Read the findings stored under one topic and one information category, newest first.")
def retrieve(topic: str, information: str) -> dict:
    return dossier_tools.get_dossier(topic, information)


@server.tool(description="File findings under a topic. Each needs a category, a single-fact claim and a real source url.")
def write(topic: str, findings: list[Finding]) -> dict:
    return dossier_tools.write_findings(topic, [finding.model_dump() for finding in findings])


def cited_sources(blocks):
    urls = []
    for block in blocks:
        for finding in block.get("findings", []):
            if finding["source"] not in urls:
                urls.append(finding["source"])
    return urls


@server.tool(description="Ask the full Dossier agent a question. It answers from the case file, researching the web first if it needs to. Pass the returned thread_id back to continue the conversation.")
async def ask(question: str, thread_id: str = "") -> dict:
    thread = thread_id or f"mcp-{uuid.uuid4()}"
    state = initial_state(question)
    state["messages"] = [HumanMessage(question)]
    config = {"configurable": {"thread_id": thread}}

    result = await anyio.to_thread.run_sync(lambda: get_graph().invoke(state, config=config))
    blocks = result.get("blocks") or []

    return {
        "thread_id": thread,
        "answer": " ".join(
            block["text"] for block in blocks if block["type"] == "summary" and block.get("text")
        ),
        "gaps": [block["text"] for block in blocks if block["type"] == "gap" and block.get("text")],
        "sources": cited_sources(blocks),
        "research_passes": result.get("iteration", 0),
    }


if __name__ == "__main__":
    server.run(transport="streamable-http")
