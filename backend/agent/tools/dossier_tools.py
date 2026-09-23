import datetime
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
