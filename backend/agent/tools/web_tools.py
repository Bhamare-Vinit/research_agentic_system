import httpx
import trafilatura
from tavily import TavilyClient

from agent import settings

USER_AGENT = "DossierResearchAgent/1.0 (autonomous research agent; take-home assignment)"
FETCH_TIMEOUT_SECONDS = 15
SNIPPET_LIMIT = 600
MIN_READABLE_CHARS = 250


def trust_system_certificates():
    try:
        import truststore
    except ImportError:
        return False
    truststore.inject_into_ssl()
    return True


SYSTEM_CERTIFICATES_TRUSTED = trust_system_certificates()

_client = None


def search_client():
    global _client
    if not settings.SEARCH_CONFIGURED:
        return None
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def web_search(query):
    client = search_client()
    if client is None:
        return {"error": "TAVILY_API_KEY is not set, so live search is unavailable"}

    try:
        response = client.search(
            query=query,
            max_results=settings.SEARCH_RESULTS_PER_QUERY,
            search_depth=settings.SEARCH_DEPTH,
        )
    except Exception as failure:
        return {"error": f"search failed for {query!r}: {failure}"}

    results = []
    for item in response.get("results", []):
        url = item.get("url")
        if not url:
            continue
        results.append(
            {
                "title": item.get("title") or url,
                "url": url,
                "snippet": (item.get("content") or "")[:SNIPPET_LIMIT],
                "published_date": item.get("published_date"),
            }
        )

    if not results:
        return {"query": query, "results": [], "error": "no results for that query"}

    return {"query": query, "results": results}


def fetch_page(url):
    address = str(url or "").strip()
    if not address.startswith(("http://", "https://")):
        return {"error": "fetch_page needs a full http or https url"}

    try:
        response = httpx.get(
            address,
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
    except Exception as failure:
        return {"error": f"could not fetch {address}: {failure}"}

    extracted = trafilatura.extract(
        response.text, include_comments=False, include_tables=True
    )
    if not extracted or len(extracted) < MIN_READABLE_CHARS:
        return {
            "error": f"not enough readable article text at {address}, try a different source"
        }

    limit = settings.FETCH_PAGE_MAX_CHARS
    metadata = trafilatura.extract_metadata(response.text)

    return {
        "url": str(response.url),
        "title": getattr(metadata, "title", None) or address,
        "published_date": getattr(metadata, "date", None),
        "content": extracted[:limit],
        "truncated": len(extracted) > limit,
    }
