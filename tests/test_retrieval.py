"""A4: retrieval returns passages that resolve to the real corpus."""

from __future__ import annotations

import pytest

from src.retrieval import LexicalIndex, chunk_by_section, chunk_whole_document


def test_every_returned_passage_resolves_to_a_real_article(index, articles):
    real_ids = {a["doc_id"] for a in articles}
    passages = index.search("invalid credentials when signing in to the console")
    assert passages
    by_id = {a["doc_id"]: a for a in articles}
    for passage in passages:
        assert passage.doc_id in real_ids
        # The chunk_id names the section that matched; the text returned is the
        # article it belongs to. Both must resolve to the same real article.
        assert index.resolve(passage.chunk_id).doc_id == passage.doc_id
        assert by_id[passage.doc_id]["content"] in passage.text


def test_a_known_question_returns_the_right_article(index):
    passages = index.search("I get invalid credentials even though my password is correct")
    assert passages[0].doc_id == "DOC-AUTH-001"


def test_a_symptom_phrased_question_is_grounded_on_the_resolution_steps(index):
    """The measured failure that whole-document return exists to fix."""
    passages = index.search("the console returns invalid credentials despite a correct password")
    assert passages[0].chunk_id.endswith("#01")  # the Symptoms section matched
    assert "## Resolution" in passages[0].text  # the fix came with it


def test_results_are_ranked_by_descending_score(index):
    scores = [p.score for p in index.search("webhook deliveries are failing", top_k=3)]
    assert scores == sorted(scores, reverse=True)


def test_nothing_relevant_returns_nothing(index):
    assert index.search("aaaa bbbb cccc dddd eeee") == []
    assert index.search("") == []
    assert index.search("   ") == []


def test_an_off_topic_question_does_not_retrieve_the_whole_corpus(index):
    passages = index.search("what is the best pizza topping in Naples")
    assert len(passages) <= 3


def test_a_feature_request_has_nothing_to_retrieve(index):
    assert index.search("Please add a dark mode toggle, it would be a nice feature") == []


def test_results_are_one_passage_per_document(index):
    passages = index.search("deployment is failing during dependency resolution", top_k=3)
    assert len({p.doc_id for p in passages}) == len(passages)


def test_search_is_deterministic(index):
    query = "my api requests are being rate limited"
    first = [(p.chunk_id, p.score) for p in index.search(query)]
    second = [(p.chunk_id, p.score) for p in index.search(query)]
    assert first == second


def test_both_chunking_strategies_cover_every_article(articles):
    for chunker in (chunk_by_section, chunk_whole_document):
        covered = {c.doc_id for a in articles for c in chunker(a)}
        assert covered == {a["doc_id"] for a in articles}


def test_section_chunking_produces_more_chunks_than_documents(articles):
    section = LexicalIndex(articles, strategy="section")
    document = LexicalIndex(articles, strategy="document")
    assert len(section) > len(document) == len(articles)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("login says invalid credentials", "DOC-AUTH-001"),
        ("i am rate limited on the api, 429 errors", "DOC-API-001"),
    ],
)
def test_hit_rate_on_representative_queries(index, query, expected):
    assert expected in {p.doc_id for p in index.search(query, top_k=3)}


def test_hit_rate_over_the_development_set_holds(index, dev_tickets):
    """Guards the measured figure so a future change cannot quietly lose it."""
    from src.ingest import normalise_all

    tickets = normalise_all(dev_tickets)
    answerable = [
        t
        for t in tickets
        if t.raw["labels"]["answerable_from_docs"] and t.raw["labels"]["expected_doc_ids"]
    ]
    hits = sum(
        1
        for t in answerable
        if set(t.raw["labels"]["expected_doc_ids"]) & {p.doc_id for p in index.search(t.text)}
    )
    assert hits / len(answerable) >= 0.90
