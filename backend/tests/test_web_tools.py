from agent import settings
from agent.tools import web_tools


def test_a_url_without_a_scheme_is_refused():
    assert "error" in web_tools.fetch_page("example.com/report")
    assert "error" in web_tools.fetch_page("")
    assert "error" in web_tools.fetch_page(None)


def test_search_reports_a_missing_key_instead_of_raising(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_CONFIGURED", False)
    monkeypatch.setattr(web_tools, "_client", None)

    result = web_tools.web_search("anything")

    assert "TAVILY_API_KEY" in result["error"]


def test_search_failures_come_back_as_values(monkeypatch):
    class BrokenClient:
        def search(self, **kwargs):
            raise RuntimeError("provider is down")

    monkeypatch.setattr(settings, "SEARCH_CONFIGURED", True)
    monkeypatch.setattr(web_tools, "_client", BrokenClient())

    result = web_tools.web_search("anything")

    assert "provider is down" in result["error"]


def test_thin_pages_are_rejected_so_the_agent_picks_another_source(monkeypatch):
    class Response:
        text = "<html><body><p>tiny</p></body></html>"
        url = "https://example.com/video"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(web_tools.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(web_tools.trafilatura, "extract", lambda *args, **kwargs: "tiny")

    result = web_tools.fetch_page("https://example.com/video")

    assert "not enough readable article text" in result["error"]
