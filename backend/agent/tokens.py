import json

import tiktoken

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
