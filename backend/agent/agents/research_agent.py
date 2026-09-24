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


class FindingItem(BaseModel):
    information: str = Field(
        description="the category this fact belongs to, in snake_case, from the plan or a new one you judge is needed"
    )
    claim: str = Field(
        description="one self-contained factual sentence carrying the figure, unit and timeframe"
    )
    source: str = Field(description="the exact url you read this fact on")
    date: str = Field(
        default="", description="publication date of the source as YYYY-MM-DD, or empty for today"
    )
    replaces: str = Field(
        default="",
        description="id of an existing finding this one supersedes, when yours is fresher and contradicts it",
    )


class WriteFindingsInput(BaseModel):
    findings: list[FindingItem] = Field(
        description="every fact you have gathered, each tagged with its category"
    )


class ReportInput(BaseModel):
    subject_confirmed: bool = Field(
        description="true if the sources were genuinely about this subject, false if you could not find it"
    )
    could_not_establish: list[str] = Field(
        default_factory=list,
        description="parts of the plan you found no reliable information for",
    )
    notes: str = Field(
        description="one or two sentences for the Main Agent: what you covered and anything it should know"
    )


def format_plan(plan):
    if not plan:
        return "  (no plan given, research the question as it stands)"
    return "\n".join(
        f"  {item.get('information')}  —  {item.get('what_to_find', '')}" for item in plan
    )


def format_existing(topic):
    structure = dossier_tools.get_dossier_structure().get(topic, {})
    if not structure:
        return "  (nothing recorded on this topic yet)"

    lines = []
    for category in structure:
        lines.append(f"  {category}:")
        for finding in dossier_tools.get_dossier(topic, category)["findings"]:
            lines.append(f"    [{finding['id']}] ({finding.get('date')}) {finding['claim']}")
    return "\n".join(lines)


def build_toolkit(topic, preferred, activity, written, created, outcome):
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

    def run_write(findings):
        items = [
            finding.model_dump() if isinstance(finding, FindingItem) else dict(finding)
            for finding in findings
        ]
        result = dossier_tools.write_findings(topic, items, preferred_information=preferred)
        created.update(result["new_categories"])

        for item, outcome_row in zip(items, result["results"]):
            if outcome_row["status"] == "written":
                written.append(outcome_row["id"])
                record(
                    "write_findings",
                    f"filed under {outcome_row['information']}: {item['claim']}",
                    finding_id=outcome_row["id"],
                    source=item.get("source"),
                    information=outcome_row["information"],
                    superseded=outcome_row.get("replaced"),
                )
            elif outcome_row["status"] == "duplicate":
                record("write_findings", f"already on file: {item['claim'][:90]}")
            else:
                record("write_findings", f"rejected: {outcome_row.get('reason', '')[:110]}")

        return result

    def run_report(subject_confirmed, notes, could_not_establish=None):
        outcome["report"] = {
            "subject_confirmed": subject_confirmed,
            "could_not_establish": list(could_not_establish or []),
            "notes": notes,
        }
        record("report", notes[:110])
        return {"status": "received"}

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
        "write_findings": StructuredTool.from_function(
            func=run_write,
            name="write_findings",
            description=(
                f"File many facts at once under the topic {topic}, each tagged with its own "
                "category. Use a plan category where one fits, or a new category when the fact "
                "belongs somewhere the plan did not anticipate."
            ),
            args_schema=WriteFindingsInput,
        ),
        "report": StructuredTool.from_function(
            func=run_report,
            name="report",
            description="Finish the research and hand your report back to the Main Agent.",
            args_schema=ReportInput,
        ),
    }


def run_research_agent(state):
    task = state.get("research_task") or {}
    topic = task.get("topic") or "general"
    question = task.get("research_question") or state.get("user_query", "")
    plan = task.get("plan") or []
    preferred = [item["information"] for item in plan if item.get("information")]

    activity = []
    written = []
    created = set()
    outcome = {}
    toolkit = build_toolkit(topic, preferred, activity, written, created, outcome)

    prompt = render_prompt(
        "research_agent",
        topic=topic,
        research_question=question,
        plan=format_plan(plan),
        existing=format_existing(topic),
    )

    model = llm.get_tool_llm(list(toolkit.values()))
    transcript = [HumanMessage(prompt)]
    spoken = ""

    for _ in range(RESEARCH_AGENT_MAX_STEPS):
        response = model.invoke(transcript)
        transcript.append(response)

        calls = getattr(response, "tool_calls", None)
        if not calls:
            spoken = llm.message_text(response)
            break

        for call in calls:
            selected = toolkit.get(call["name"])
            if selected is None:
                result = {"error": f"there is no tool called {call['name']}"}
            else:
                result = selected.invoke(call["args"])
            transcript.append(
                ToolMessage(
                    content=json.dumps(result, default=str)[:TOOL_OUTPUT_LIMIT],
                    tool_call_id=call["id"],
                )
            )

        if "report" in outcome:
            break

    report = outcome.get("report") or {
        "subject_confirmed": bool(written),
        "could_not_establish": [],
        "notes": spoken or "The Research Agent stopped without filing a report.",
    }

    covered = sorted(
        {
            entry["information"]
            for entry in activity
            if entry.get("tool") == "write_findings" and entry.get("information")
        }
    )

    return {
        "activity": activity,
        "findings_added": len(written),
        "iteration": state.get("iteration", 0) + 1,
        "research_task": None,
        "research_result": {
            "topic": topic,
            "findings_added": len(written),
            "categories_covered": covered,
            "categories_created": sorted(created),
            "could_not_establish": report["could_not_establish"],
            "subject_confirmed": report["subject_confirmed"],
            "notes": report["notes"],
        },
    }
