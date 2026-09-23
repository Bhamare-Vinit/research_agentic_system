from langchain_core.messages import AIMessage

from agent import llm
from agent.nodes import research
from agent.tools import dossier_tools, web_tools


class ScriptedModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return self.replies.pop(0)


def tool_call(name, args, call_id):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}]
    )


def stub_web(monkeypatch, search_results=None, page_text="A long page about battery costs. " * 20):
    monkeypatch.setattr(
        web_tools,
        "web_search",
        lambda query: {
            "query": query,
            "results": search_results
            if search_results is not None
            else [{"title": "Cost report", "url": "https://example.com/report", "snippet": "..."}],
        },
    )
    monkeypatch.setattr(
        web_tools,
        "fetch_page",
        lambda url: {"url": url, "title": "Cost report", "content": page_text, "truncated": False},
    )


def test_the_loop_runs_tools_and_stops_when_the_model_stops_calling(monkeypatch):
    stub_web(monkeypatch)
    model = ScriptedModel(
        [
            tool_call("web_search", {"query": "battery cost 2026"}, "c1"),
            tool_call("fetch_page", {"url": "https://example.com/report"}, "c2"),
            tool_call(
                "write_finding",
                {
                    "topic": "battery",
                    "information": "cost",
                    "claim": "Pack cost is $85 per kWh in 2026",
                    "source": "https://example.com/report",
                },
                "c3",
            ),
            AIMessage(content="Covered 2026 pack cost."),
        ]
    )
    monkeypatch.setattr(llm, "get_tool_llm", lambda tools: model)

    result = research.run_research(
        {"research_task": {"topic": "battery", "information": "cost", "research_question": "cost?"}}
    )

    assert result["findings_added"] == 1
    assert result["iteration"] == 1
    assert [entry["tool"] for entry in result["research_log"]] == [
        "web_search",
        "fetch_page",
        "write_finding",
    ]
    assert dossier_tools.get_dossier("battery", "cost")["findings"][0]["source"] == (
        "https://example.com/report"
    )


def test_the_loop_cannot_run_past_its_step_cap(monkeypatch):
    stub_web(monkeypatch)
    endless = ScriptedModel(
        [tool_call("web_search", {"query": f"attempt {index}"}, f"c{index}") for index in range(50)]
    )
    monkeypatch.setattr(llm, "get_tool_llm", lambda tools: endless)
    monkeypatch.setattr(research, "RESEARCH_AGENT_MAX_STEPS", 4)

    result = research.run_research({"research_task": {"topic": "battery", "information": "cost"}})

    assert endless.calls == 4
    assert result["findings_added"] == 0


def test_a_finding_without_a_real_url_never_reaches_the_dossier(monkeypatch):
    stub_web(monkeypatch)
    model = ScriptedModel(
        [
            tool_call(
                "write_finding",
                {
                    "topic": "battery",
                    "information": "margins",
                    "claim": "Margins are 40%",
                    "source": "a report I remember",
                },
                "c1",
            ),
            AIMessage(content="done"),
        ]
    )
    monkeypatch.setattr(llm, "get_tool_llm", lambda tools: model)

    result = research.run_research({"research_task": {"topic": "battery", "information": "margins"}})

    assert result["findings_added"] == 0
    assert dossier_tools.get_dossier("battery", "margins")["findings"] == []
    assert "rejected" in result["research_log"][0]["summary"]


def test_an_unreadable_page_is_reported_and_the_run_continues(monkeypatch):
    monkeypatch.setattr(web_tools, "web_search", lambda query: {"query": query, "results": []})
    monkeypatch.setattr(web_tools, "fetch_page", lambda url: {"error": f"403 on {url}"})
    model = ScriptedModel(
        [
            tool_call("fetch_page", {"url": "https://example.com/blocked"}, "c1"),
            AIMessage(content="could not read that source"),
        ]
    )
    monkeypatch.setattr(llm, "get_tool_llm", lambda tools: model)

    result = research.run_research({"research_task": {"topic": "battery", "information": "cost"}})

    assert "could not read" in result["research_log"][0]["summary"]
    assert result["findings_added"] == 0
