import json
import uuid

from django.http import JsonResponse, StreamingHttpResponse

from agent import settings
from agent.tools import dossier_tools, storage
from api.events import run_stream


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "dossier",
            "provider": settings.active_provider(),
            "model": settings.active_model(),
            "fallback_available": settings.OPENAI_CONFIGURED and settings.OPENROUTER_CONFIGURED,
            "search_configured": settings.SEARCH_CONFIGURED,
            "tracing": settings.LANGSMITH_PROJECT if settings.TRACING_ENABLED else None,
        }
    )


def research(request):
    if request.method != "POST":
        return JsonResponse({"error": "use POST"}, status=405)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "body must be json"}, status=400)

    query = str(body.get("query") or "").strip()
    if not query:
        return JsonResponse({"error": "query is required"}, status=400)

    thread_id = str(body.get("thread_id") or uuid.uuid4())

    response = StreamingHttpResponse(
        run_stream(query, thread_id), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def dossier(request):
    stored = storage.load_dossier()
    return JsonResponse(
        {
            "structure": dossier_tools.get_dossier_structure(),
            "topics": stored,
            "total_findings": sum(
                len(findings)
                for categories in stored.values()
                for findings in categories.values()
            ),
        }
    )
