from app.grounding import (
    cited_claims_are_supported,
    claims_have_citations,
    evidence_is_sufficient,
    only_cited_evidence,
    retain_cited_claims,
    retain_supported_cited_claims,
)


def test_only_cited_evidence_is_exposed_to_the_ui() -> None:
    evidence = [{"id": "used"}, {"id": "retrieved-but-unused"}]

    assert only_cited_evidence(evidence, {"used"}) == [{"id": "used"}]


def test_claim_level_citation_coverage_rejects_uncited_sentences() -> None:
    cited = "A sufficiently detailed supported factual claim belongs right here. [[source:episode:10:abc]]"
    uncited = "A second sufficiently detailed factual claim has no supporting source token."

    assert claims_have_citations(cited)
    assert not claims_have_citations(f"{cited} {uncited}")
    assert retain_cited_claims(f"{cited} {uncited}") == cited.replace(
        ". [[source:episode:10:abc]]", " [[source:episode:10:abc]]."
    )


def test_all_routes_share_one_conservative_evidence_floor() -> None:
    assert evidence_is_sufficient([{"route": "guest", "score": 0.399943}])
    assert not evidence_is_sufficient([{"route": "global", "score": 0.299}])


def test_valid_citation_id_does_not_make_an_unrelated_claim_supported() -> None:
    evidence = [{
        "id": "casey:1",
        "title": "Founder intuition",
        "excerpt": (
            "Founders should directly hire senior people until those leaders show they "
            "understand the business, and then the founder can back away."
        ),
    }]
    unsupported = (
        "Casey says leaders should document strategic tradeoffs and explain their reasoning "
        "before delegating decisions. [[source:casey:1]]"
    )

    assert not cited_claims_are_supported(unsupported, evidence)
    assert retain_supported_cited_claims(unsupported, evidence) == ""


def test_material_overlap_allows_a_reasonable_grounded_paraphrase() -> None:
    evidence = [{
        "id": "dan:1",
        "title": "Growth models",
        "excerpt": "Retention compounds through the wider growth model.",
    }]
    supported = (
        "Dan connects retention and compounding effects to the wider growth model for the "
        "business. [[source:dan:1]]"
    )

    assert cited_claims_are_supported(supported, evidence)
