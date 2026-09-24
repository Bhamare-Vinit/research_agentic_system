import datetime
import difflib
from urllib.parse import urlparse

from agent.settings import RETRIEVAL_TOP_K
from agent.tools import storage

GENERIC_CATEGORIES = {
    "research",
    "info",
    "information",
    "data",
    "general",
    "misc",
    "details",
    "notes",
    "findings",
    "results",
    "summary",
    "other",
    "topic",
    "overview",
}


def is_real_source(source):
    try:
        parsed = urlparse(str(source or "").strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_information(requested, preferred):
    key = storage.slugify(requested or "")
    if not key:
        return None
    if preferred and key not in preferred:
        nearest = difflib.get_close_matches(key, preferred, n=1, cutoff=0.8)
        if nearest:
            return nearest[0]
    return key


def matches_existing(finding, claim, source):
    same_claim = str(finding.get("claim", "")).strip().lower() == claim.lower()
    return same_claim and finding.get("source") == source


def newest_first(finding):
    return (str(finding.get("date") or ""), str(finding.get("id") or ""))


def get_dossier_structure():
    dossier = storage.load_dossier()
    return {
        topic: {
            information: len(findings) for information, findings in categories.items()
        }
        for topic, categories in dossier.items()
    }


def get_dossier(topic, information, limit=None):
    cap = RETRIEVAL_TOP_K if limit is None else limit
    topic_key = storage.slugify(topic)
    information_key = storage.slugify(information)

    dossier = storage.load_dossier()
    available = storage.find_slice(dossier, topic_key, information_key)
    ordered = sorted(available, key=newest_first, reverse=True)
    selected = ordered[:cap]

    return {
        "topic": topic_key,
        "information": information_key,
        "findings": selected,
        "total_available": len(available),
        "returned": len(selected),
    }


def write_findings(topic, items, preferred_information=None):
    topic_key = storage.slugify(topic)
    today = datetime.date.today().isoformat()
    expected = set(preferred_information or [])
    results = []

    with storage.dossier_transaction() as dossier:
        for item in items:
            claim = str(item.get("claim") or "").strip()
            source = str(item.get("source") or "").strip()
            information = resolve_information(item.get("information"), preferred_information)

            if information is None or information in GENERIC_CATEGORIES:
                results.append(
                    {
                        "status": "rejected",
                        "claim": claim[:90],
                        "reason": (
                            f"'{item.get('information')}' names no particular kind of information. "
                            "Use a category that says what the fact is about, such as pricing, "
                            "architecture, benchmarks, limitations or training_data."
                        ),
                    }
                )
                continue

            if not claim:
                results.append({"status": "rejected", "reason": "the claim was empty"})
                continue

            if not is_real_source(source):
                results.append(
                    {
                        "status": "rejected",
                        "claim": claim[:90],
                        "reason": "the source must be a real http or https url from a page you actually read",
                    }
                )
                continue

            existing = storage.ensure_slice(dossier, topic_key, information)
            duplicate = next(
                (finding for finding in existing if matches_existing(finding, claim, source)),
                None,
            )
            if duplicate:
                results.append(
                    {"status": "duplicate", "id": duplicate["id"], "information": information}
                )
                continue

            record = {
                "id": storage.next_finding_id(dossier, topic_key, information),
                "claim": claim,
                "source": source,
                "date": str(item.get("date") or "").strip() or today,
                "active": True,
                "supersedes": None,
                "superseded_by": None,
                "last_verified": today,
            }
            existing.append(record)

            results.append(
                {
                    "status": "written",
                    "id": record["id"],
                    "information": information,
                    "new_category": bool(expected) and information not in expected,
                }
            )

    written = [result for result in results if result["status"] == "written"]
    return {
        "topic": topic_key,
        "written": len(written),
        "categories": sorted({result["information"] for result in written}),
        "new_categories": sorted(
            {result["information"] for result in written if result["new_category"]}
        ),
        "results": results,
    }
