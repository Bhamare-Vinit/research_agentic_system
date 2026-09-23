import datetime
import json
import threading

import tiktoken

from agent.settings import TOKEN_LOG_PATH

ENCODING_NAME = "cl100k_base"

_encoding = None


def encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(ENCODING_NAME)
    return _encoding


def count_tokens(payload):
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False, default=str)
    return len(encoding().encode(payload))


_log_lock = threading.Lock()


def summarise_usage(usage_by_model):
    prompt_tokens = 0
    completion_tokens = 0
    for usage in (usage_by_model or {}).values():
        prompt_tokens += usage.get("input_tokens", 0)
        completion_tokens += usage.get("output_tokens", 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "by_model": usage_by_model or {},
    }


def record_turn(entry):
    line = json.dumps(
        {"at": datetime.datetime.now().isoformat(timespec="seconds"), **entry},
        default=str,
    )
    with _log_lock:
        TOKEN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_LOG_PATH, "a", encoding="utf-8") as handle:
            print(line, file=handle)


def read_log():
    try:
        with open(TOKEN_LOG_PATH, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def summarise_log():
    turns = read_log()
    if not turns:
        return {"turns": 0}

    whole = sum(turn.get("retrieval", {}).get("whole_dossier_tokens", 0) for turn in turns)
    retrieved = sum(turn.get("retrieval", {}).get("retrieved_tokens", 0) for turn in turns)
    prompt = sum(turn.get("llm", {}).get("prompt_tokens", 0) for turn in turns)
    completion = sum(turn.get("llm", {}).get("completion_tokens", 0) for turn in turns)

    return {
        "turns": len(turns),
        "context_without_retrieval_cap": whole,
        "context_with_retrieval_cap": retrieved,
        "tokens_saved": whole - retrieved,
        "tokens_saved_pct": round(100 * (1 - retrieved / whole), 1) if whole else 0.0,
        "llm_prompt_tokens": prompt,
        "llm_completion_tokens": completion,
        "llm_total_tokens": prompt + completion,
    }
