import logging

from langchain_openai import ChatOpenAI

from agent import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 90
MAX_REQUEST_RETRIES = 2


class NoModelConfigured(RuntimeError):
    pass


def default_temperature():
    raw = settings.MODEL_TEMPERATURE
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def temperature_kwargs(temperature):
    return {} if temperature is None else {"temperature": temperature}


def openai_chat_model(temperature):
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_REQUEST_RETRIES,
        **temperature_kwargs(temperature),
    )


def openrouter_chat_model(temperature):
    return ChatOpenAI(
        model=settings.OPENROUTER_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_REQUEST_RETRIES,
        **temperature_kwargs(temperature),
    )


PROVIDERS = [
    ("openai", lambda: settings.OPENAI_CONFIGURED, openai_chat_model),
    ("openrouter", lambda: settings.OPENROUTER_CONFIGURED, openrouter_chat_model),
]


def available_providers():
    return [
        (name, build_model) for name, is_configured, build_model in PROVIDERS if is_configured()
    ]


def provider_chain_description():
    names = [name for name, _ in available_providers()]
    if not names:
        return "no provider configured"
    if len(names) == 1:
        return f"{names[0]} (no fallback configured)"
    return f"{names[0]}, falling back to {' then '.join(names[1:])}"


def build_chain(temperature, to_runnables):
    runnables = []
    for _, build_model in available_providers():
        runnables.extend(to_runnables(build_model(temperature)))

    if not runnables:
        raise NoModelConfigured(
            "set OPENAI_API_KEY or OPENROUTER_API_KEY in .env before running the graph"
        )

    primary, *fallbacks = runnables
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


def get_llm(temperature=Ellipsis):
    chosen = default_temperature() if temperature is Ellipsis else temperature
    return build_chain(chosen, lambda model: [model])


def get_structured_llm(schema, temperature=Ellipsis):
    chosen = default_temperature() if temperature is Ellipsis else temperature

    def to_runnables(model):
        return [
            model.with_structured_output(schema, method="json_schema"),
            model.with_structured_output(schema, method="function_calling"),
        ]

    return build_chain(chosen, to_runnables)


def get_tool_llm(tools, temperature=Ellipsis):
    chosen = default_temperature() if temperature is Ellipsis else temperature
    return build_chain(chosen, lambda model: [model.bind_tools(tools)])


def log_provider_chain():
    logger.info("dossier llm: %s", provider_chain_description())
