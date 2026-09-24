import datetime
import difflib
from urllib.parse import urlparse

from agent.settings import RETRIEVAL_TOP_K
from agent.tools import storage


def is_real_source(source):
    try:
        parsed = urlparse(str(source or "").strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _ranking_key(finding):
    return (
        1 if finding.get("active", True) else 0,
        str(finding.get("date") or ""),
        str(finding.get("id") or ""),
    )


def get_dossier_structure():
    dossier = storage.load_dossier()
    return {
        topic: {
            information: len(findings) for information, findings in categories.items()
        }
        for topic, categories in dossier.items()
    }


def get_dossier(topic, information, limit=None, include_inactive=False):
    cap = RETRIEVAL_TOP_K if limit is None else limit
    topic_key = storage.slugify(topic)
    information_key = storage.slugify(information)

    dossier = storage.load_dossier()
    available = storage.find_slice(dossier, topic_key, information_key)
    if not include_inactive:
        available = [finding for finding in available if finding.get("active", True)]

    ordered = sorted(available, key=_ranking_key, reverse=True)
    selected = ordered[:cap]

    return {
        "topic": topic_key,
        "information": information_key,
        "findings": selected,
        "total_available": len(available),
        "returned": len(selected),
    }


def write_finding(topic, information, claim, source, date=None, supersedes=None):
    claim_text = str(claim or "").strip()
    if not claim_text:
        return {"status": "rejected", "reason": "claim must not be empty"}
    if not is_real_source(source):
        return {
            "status": "rejected",
            "reason": "source must be a real http or https url from a page you actually read",
        }

    topic_key = storage.slugify(topic)
    information_key = storage.slugify(information)
    source_url = str(source).strip()
    recorded_on = str(date or "").strip() or datetime.date.today().isoformat()

    with storage.dossier_transaction() as dossier:
        existing = storage.ensure_slice(dossier, topic_key, information_key)

        for finding in existing:
            same_claim = str(finding.get("claim", "")).strip().lower() == claim_text.lower()
            if same_claim and finding.get("source") == source_url:
                return {"status": "duplicate", "id": finding.get("id")}

        finding_id = storage.next_finding_id(dossier, topic_key, information_key)

        superseded_id = None
        if supersedes:
            older = storage.find_by_id(dossier, str(supersedes).strip())
            if older is not None:
                older["active"] = False
                older["superseded_by"] = finding_id
                superseded_id = older.get("id")

        existing.append(
            {
                "id": finding_id,
                "claim": claim_text,
                "source": source_url,
                "date": recorded_on,
                "active": True,
                "supersedes": superseded_id,
                "superseded_by": None,
                "last_verified": datetime.date.today().isoformat(),
            }
        )

    return {"status": "written", "id": finding_id, "superseded": superseded_id}


def get_findings_by_ids(finding_ids):
    dossier = storage.load_dossier()
    resolved = []
    missing = []
    for finding_id in finding_ids:
        finding = storage.find_by_id(dossier, str(finding_id).strip())
        if finding is None:
            missing.append(finding_id)
        else:
            resolved.append(finding)
    return resolved, missing


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


def apply_replacement(dossier, record, replaces):
    if not replaces:
        return None

    older = storage.find_by_id(dossier, str(replaces).strip())
    if older is None or older.get("id") == record["id"]:
        return None

    if str(record["date"]) >= str(older.get("date") or ""):
        older["active"] = False
        older["superseded_by"] = record["id"]
        record["supersedes"] = older["id"]
        return older["id"]

    record["active"] = False
    record["supersedes"] = older["id"]
    return None


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
                    {
                        "status": "duplicate",
                        "id": duplicate["id"],
                        "information": information,
                    }
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

            replaced = apply_replacement(dossier, record, item.get("replaces"))
            existing.append(record)

            results.append(
                {
                    "status": "written",
                    "id": record["id"],
                    "information": information,
                    "replaced": replaced,
                    "active": record["active"],
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
