from agent.tools import dossier_tools, storage


def write_cost(claim, source="https://example.com/report", **extra):
    return dossier_tools.write_finding(
        "solid state batteries", "cost", claim, source, **extra
    )


def test_writing_appends_and_never_overwrites():
    write_cost("Cost is $100/kWh", source="https://example.com/a")
    write_cost("Cost is $85/kWh", source="https://example.com/b")

    findings = dossier_tools.get_dossier("solid state batteries", "cost")["findings"]
    claims = {finding["claim"] for finding in findings}

    assert claims == {"Cost is $100/kWh", "Cost is $85/kWh"}


def test_finding_ids_increment_within_a_slice():
    first = write_cost("First", source="https://example.com/a")
    second = write_cost("Second", source="https://example.com/b")

    assert first["id"] == "solid_state_batteries_cost_001"
    assert second["id"] == "solid_state_batteries_cost_002"


def test_topic_spelling_variants_land_in_one_slice():
    dossier_tools.write_finding(
        "Solid-State Batteries!", "Cost", "First", "https://example.com/a"
    )
    dossier_tools.write_finding(
        "solid state batteries", "cost", "Second", "https://example.com/b"
    )

    result = dossier_tools.get_dossier("SOLID STATE BATTERIES", "cost")

    assert result["topic"] == "solid_state_batteries"
    assert result["total_available"] == 2


def test_retrieval_returns_only_the_requested_slice():
    write_cost("Battery cost claim")
    dossier_tools.write_finding(
        "nvidia", "products", "NVIDIA claim", "https://example.com/n"
    )

    result = dossier_tools.get_dossier("solid state batteries", "cost")
    claims = [finding["claim"] for finding in result["findings"]]

    assert claims == ["Battery cost claim"]


def test_retrieval_is_capped_but_reports_what_it_held_back():
    for index in range(12):
        write_cost(f"Claim {index}", source=f"https://example.com/{index}")

    result = dossier_tools.get_dossier("solid state batteries", "cost", limit=8)

    assert result["total_available"] == 12
    assert result["returned"] == 8
    assert len(result["findings"]) == 8


def test_superseding_deactivates_the_old_finding_without_deleting_it():
    old = write_cost("Cost is $100/kWh", source="https://example.com/old")
    new = write_cost(
        "Cost is $85/kWh", source="https://example.com/new", supersedes=old["id"]
    )

    assert new["superseded"] == old["id"]

    everything = dossier_tools.get_dossier(
        "solid state batteries", "cost", include_inactive=True
    )["findings"]
    by_id = {finding["id"]: finding for finding in everything}

    assert len(everything) == 2
    assert by_id[old["id"]]["active"] is False
    assert by_id[old["id"]]["superseded_by"] == new["id"]
    assert by_id[new["id"]]["supersedes"] == old["id"]


def test_active_retrieval_hides_superseded_findings():
    old = write_cost("Cost is $100/kWh", source="https://example.com/old")
    write_cost("Cost is $85/kWh", source="https://example.com/new", supersedes=old["id"])

    active = dossier_tools.get_dossier("solid state batteries", "cost")["findings"]

    assert [finding["claim"] for finding in active] == ["Cost is $85/kWh"]


def test_a_finding_without_a_real_url_is_rejected():
    for bad_source in ["", "not a url", "example.com/report", "ftp://example.com"]:
        result = write_cost("Some claim", source=bad_source)
        assert result["status"] == "rejected"

    assert dossier_tools.get_dossier_structure() == {}


def test_an_empty_claim_is_rejected():
    assert write_cost("   ")["status"] == "rejected"


def test_the_same_claim_from_the_same_source_is_not_stored_twice():
    first = write_cost("Cost is $85/kWh", source="https://example.com/report")
    second = write_cost("Cost is $85/kWh", source="https://example.com/report")

    assert second["status"] == "duplicate"
    assert second["id"] == first["id"]


def test_structure_exposes_shape_but_no_claims():
    write_cost("A very specific number nobody should leak")
    dossier_tools.write_finding(
        "nvidia", "products", "NVIDIA claim", "https://example.com/n"
    )

    structure = dossier_tools.get_dossier_structure()

    assert structure == {
        "solid_state_batteries": {"cost": 1},
        "nvidia": {"products": 1},
    }
    assert "very specific number" not in str(structure)


def test_missing_topics_retrieve_empty_rather_than_raising():
    result = dossier_tools.get_dossier("never researched", "cost")

    assert result["findings"] == []
    assert result["total_available"] == 0


def test_hydration_reports_ids_that_do_not_exist():
    written = write_cost("Real claim")

    resolved, missing = dossier_tools.get_findings_by_ids(
        [written["id"], "battery_margin_999"]
    )

    assert [finding["id"] for finding in resolved] == [written["id"]]
    assert missing == ["battery_margin_999"]


def test_writes_survive_a_reload_from_disk():
    write_cost("Persisted claim")

    assert "solid_state_batteries" in storage.load_dossier()
