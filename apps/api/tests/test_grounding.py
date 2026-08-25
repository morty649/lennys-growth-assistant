from app.grounding import (
    claims_have_citations,
    evidence_is_sufficient,
    only_cited_evidence,
    retain_cited_claims,
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
