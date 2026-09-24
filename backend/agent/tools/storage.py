import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager

from agent.settings import DOSSIER_PATH

_access_lock = threading.RLock()

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(text):
    collapsed = _SLUG_PATTERN.sub("_", str(text).strip().lower()).strip("_")
    return collapsed or "unknown"


def _read_file():
    try:
        with open(DOSSIER_PATH, encoding="utf-8") as handle:
            parsed = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_file(dossier):
    DOSSIER_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=str(DOSSIER_PATH.parent), suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dossier, handle, indent=2, ensure_ascii=False)
        os.replace(temporary_path, DOSSIER_PATH)
    except BaseException:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


def load_dossier():
    with _access_lock:
        return _read_file()


@contextmanager
def dossier_transaction():
    with _access_lock:
        dossier = _read_file()
        yield dossier
        _write_file(dossier)


def find_slice(dossier, topic, information):
    return dossier.get(topic, {}).get(information, [])


def ensure_slice(dossier, topic, information):
    return dossier.setdefault(topic, {}).setdefault(information, [])


def next_finding_id(dossier, topic, information):
    highest = 0
    for finding in find_slice(dossier, topic, information):
        suffix = str(finding.get("id", "")).rsplit("_", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{topic}_{information}_{highest + 1:03d}"
