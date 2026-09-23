from langchain_openai import ChatOpenAI

from agent import settings

REQUEST_TIMEOUT_SECONDS = 90
MAX_REQUEST_RETRIES = 2


class NoModelConfigured(RuntimeError):
    pass


def openai_chat_model(temperature):
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_REQUEST_RETRIES,
    )


def get_llm(temperature=0.0):
    if not settings.OPENAI_CONFIGURED:
        raise NoModelConfigured("OPENAI_API_KEY is not set in .env")
    return openai_chat_model(temperature)


def get_structured_llm(schema, temperature=0.0):
    return get_llm(temperature).with_structured_output(schema, method="json_schema")
