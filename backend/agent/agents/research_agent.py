import json

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent import llm
from agent.prompts import render_prompt
from agent.settings import RESEARCH_AGENT_MAX_STEPS
from agent.tools import dossier_tools, web_tools

TOOL_OUTPUT_LIMIT = 16000


class SearchInput(BaseModel):
    query: str = Field(description="a specific search query to run against the live web")


class FetchInput(BaseModel):
    url: str = Field(description="the full http or https url of a page to read")


class FindingInput(BaseModel):
    claim: str = Field(
        description="one self-contained factual sentence carrying the figure, unit and timeframe"
    )
    source: str = Field(description="the exact url you read this fact on")
    date: str = Field(
        default="", description="publication date of the source as YYYY-MM-DD, or empty for today"
    )
    supersedes: str = Field(
        default="", description="id of an existing finding this one replaces, or empty"
    )


def format_existing(findings):
    if not findings:
        return "(nothing recorded on this slice yet)"
    return "\n".join(
        f"- [{finding['id']}] ({finding.get('date')}) {finding['claim']}" for finding in findings
    )


def build_toolkit(topic, information, activity, written):
    def record(tool_name, summary, **extra):
        activity.append(
            {
                "step": len(activity) + 1,
                "agent": "research",
                "tool": tool_name,
                "summary": summary,
                **extra,
            }
        )

    def run_search(query):
        result = web_tools.web_search(query)
        results = result.get("results", [])
        if results:
            record("web_search", f"searched for {query}", result_count=len(results))
        else:
            record("web_search", f"searched for {query} and found nothing usable")
        return result

    def run_fetch(url):
        page = web_tools.fetch_page(url)
        if "error" in page:
            record("fetch_page", f"could not read {url}")
        else:
            record("fetch_page", f"read {page['title']}", url=page["url"])
        return page

    def run_write(claim, source, date="", supersedes=""):
        result = dossier_tools.write_finding(
            topic, information, claim, source, date=date or None, supersedes=supersedes or None
        )
        if result["status"] == "written":
            written.append(result["id"])
            record(
                "write_finding",
                f"recorded: {claim}",
                finding_id=result["id"],
                source=source,
                superseded=result.get("superseded"),
            )
        else:
            record("write_finding", f"rejected a finding: {result.get('reason', result['status'])}")
        return result

    return {
        "web_search": StructuredTool.from_function(
            func=run_search,
            name="web_search",
            description="Search the live web for a specific query and get back titles, urls and snippets.",
            args_schema=SearchInput,
        ),
        "fetch_page": StructuredTool.from_function(
            func=run_fetch,
            name="fetch_page",
            description="Read one web page and get back its article text.",
            args_schema=FetchInput,
        ),
        "write_finding": StructuredTool.from_function(
            func=run_write,
            name="write_finding",
            description=(
                "Record one factual claim in the case file with the url you read it on. "
                f"It is filed under {topic} / {information}."
            ),
            args_schema=FindingInput,
        ),
    }


def run_research_agent(state):
    task = state.get("research_task") or {}
    topic = task.get("topic") or "general"
    information = task.get("information") or "general"
    question = task.get("research_question") or state.get("user_query", "")

    activity = []
    written = []
    toolkit = build_toolkit(topic, information, activity, written)

    prompt = render_prompt(
        "research_agent",
        topic=topic,
        information=information,
        research_question=question,
        existing=format_existing(dossier_tools.get_dossier(topic, information)["findings"]),
    )

    model = llm.get_tool_llm(list(toolkit.values()))
    transcript = [HumanMessage(prompt)]
    closing = ""

    for _ in range(RESEARCH_AGENT_MAX_STEPS):
        response = model.invoke(transcript)
        transcript.append(response)

        calls = getattr(response, "tool_calls", None)
        if not calls:
            closing = str(response.content or "")
            break

        for call in calls:
            selected = toolkit.get(call["name"])
            if selected is None:
                output = {"error": f"there is no tool called {call['name']}"}
            else:
                output = selected.invoke(call["args"])
            transcript.append(
                ToolMessage(
                    content=json.dumps(output, default=str)[:TOOL_OUTPUT_LIMIT],
                    tool_call_id=call["id"],
                )
            )

    return {
        "activity": activity,
        "findings_added": len(written),
        "iteration": state.get("iteration", 0) + 1,
        "research_task": None,
        "research_result": {
            "topic": topic,
            "information": information,
            "findings_added": len(written),
            "summary": closing,
        },
    }
