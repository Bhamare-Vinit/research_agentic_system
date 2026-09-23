from django.http import JsonResponse

from agent import settings


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "dossier",
            "provider": settings.active_provider(),
            "model": settings.active_model(),
            "fallback_available": settings.OPENAI_CONFIGURED and settings.OPENROUTER_CONFIGURED,
            "search_configured": settings.SEARCH_CONFIGURED,
        }
    )
