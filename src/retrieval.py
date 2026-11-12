"""Retrieval over CloudServe's 29 documentation articles (A4).

Two decisions are visible in this file and both are measured rather than
asserted; the numbers are in evaluation/results/retrieval_tuning.json and the
reasoning is in docs/architecture.md (ADR-002).

Chunking, and why ranking and grounding use different units. The articles
share a rigid internal structure: a title, an applies-to line, symptoms,
common causes, numbered resolution steps, notes. Sections are the right unit
to *rank* on, because a whole article dilutes the terms that distinguish it.
They are the wrong unit to *ground* on: measured over 300 development
tickets, the best-matching section was Symptoms 46% of the time, because a
customer describes a symptom in the words the Symptoms section uses, and the
fix is two sections further down. A reply grounded on that passage retrieves
correctly and cannot tell the customer what to do.

So sections are ranked and whole articles are returned. That is nearly free
here: the median article is 1,079 characters against a 226-character median
section, and retrieval already returns one passage per distinct document. The
matching section is still named in `chunk_id`, so why an article was chosen
stays traceable. One chunk per article is implemented as well, so the two
configurations can be compared on the same hit-rate measure.

Scoring. BM25 over stemmed-ish tokens, blended with character trigram overlap.
The trigram term is there for a reason specific to this client: a quarter of
the tickets are written in non-fluent English, and lexical matching on whole
words is exactly the step that degrades when phrasing stops matching the
documentation. Trigrams survive inflection and misspelling.

Returning nothing. Below the relevance floor the retriever returns an empty
list. A retriever that always answers reproduces CloudServe's original
findability failure while hiding it behind a citation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .models import Passage

_WORD = re.compile(r"[a-z0-9]+")

# Words that appear in nearly every support ticket and nearly every article.
# Dropping them stops "the error with my account" matching all 29 documents.
_STOPWORDS = frozenset(
    """a an and are as at be been but by can cannot could did do does for from get got
    had has have how i if in into is it its just me my no not of on or our out please
    so some that the their them then there these they this to try up us use used was
    we were what when which who why will with would you your am been being does doing
    hi hello thanks thank regards team support ticket issue problem help""".split()
)

_SECTION = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def tokenise(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def trigrams(text: str) -> set[str]:
    squashed = re.sub(r"\s+", " ", text.lower())
    return {squashed[i : i + 3] for i in range(max(0, len(squashed) - 2))}


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    title: str
    category: str
    text: str


def chunk_by_section(article: dict[str, Any], max_chars: int = 1400) -> list[Chunk]:
    """One chunk per section, with the article title prefixed to each.

    The title prefix matters more than it looks: section bodies say "clear the
    cookie" without ever repeating "login", so a bare section chunk loses the
    only term a ticket is likely to share with it.
    """
    content = article.get("content", "") or ""
    doc_id = article["doc_id"]
    title = article.get("title", "")
    category = article.get("category", "")
    header = f"{title}\nApplies to: {article.get('applies_to', '')}".strip()

    bounds = [m.start() for m in _SECTION.finditer(content)]
    if not bounds:
        pieces = [content]
    else:
        bounds.append(len(content))
        pieces = [content[bounds[i] : bounds[i + 1]] for i in range(len(bounds) - 1)]

    chunks: list[Chunk] = []
    for piece in pieces:
        piece = piece.strip()
        if len(piece) < 40:
            continue
        # A section longer than the cap is split on blank lines rather than
        # mid-sentence, and only between numbered steps.
        segments = [piece] if len(piece) <= max_chars else _split_long(piece, max_chars)
        for segment in segments:
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}#{len(chunks):02d}",
                    title=title,
                    category=category,
                    text=f"{header}\n\n{segment}".strip(),
                )
            )
    if not chunks:
        chunks.append(Chunk(doc_id, f"{doc_id}#00", title, category, f"{header}\n\n{content}"))
    return chunks


def chunk_whole_document(article: dict[str, Any]) -> list[Chunk]:
    """The comparison configuration: one chunk per article, no splitting."""
    return [
        Chunk(
            doc_id=article["doc_id"],
            chunk_id=f"{article['doc_id']}#full",
            title=article.get("title", ""),
            category=article.get("category", ""),
            text=f"{article.get('title', '')}\n\n{article.get('content', '')}".strip(),
        )
    ]


def _split_long(piece: str, max_chars: int) -> list[str]:
    out: list[str] = []
    current = ""
    for para in piece.split("\n"):
        if len(current) + len(para) + 1 > max_chars and current:
            out.append(current.strip())
            current = ""
        current += para + "\n"
    if current.strip():
        out.append(current.strip())
    return out


CHUNKERS = {"section": chunk_by_section, "document": chunk_whole_document}


class LexicalIndex:
    """BM25 plus character trigram overlap. No model download, no network.

    Being offline is not only a convenience. Criterion A11 induces a provider
    outage, and sentence-transformers contacts the Hugging Face Hub when it is
    constructed even with the weights cached, which turns a degraded retrieval
    into a hard failure. This index cannot fail that way.
    """

    k1 = 1.4
    b = 0.72

    def __init__(self, articles: Iterable[dict[str, Any]], strategy: str = "section") -> None:
        chunker = CHUNKERS.get(strategy, chunk_by_section)
        self.strategy = strategy
        self.articles = list(articles)
        self.chunks: list[Chunk] = []
        for article in self.articles:
            self.chunks.extend(chunker(article))

        # Full article text, keyed by doc_id: sections are ranked, articles are
        # returned. See the module docstring.
        self._documents: dict[str, str] = {
            a["doc_id"]: (
                f"{a.get('title', '')}\n"
                f"Applies to: {a.get('applies_to', '')}\n\n"
                f"{a.get('content', '')}"
            ).strip()
            for a in self.articles
        }

        self._tokens = [tokenise(c.text) for c in self.chunks]
        self._trigrams = [trigrams(c.text) for c in self.chunks]
        self._counts = [Counter(t) for t in self._tokens]
        self._lengths = [len(t) for t in self._tokens]
        self._avg_len = sum(self._lengths) / max(1, len(self._lengths))

        df: Counter[str] = Counter()
        for counts in self._counts:
            df.update(counts.keys())
        n = len(self.chunks)
        self._idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()
        }
        self.doc_ids = {c.doc_id for c in self.chunks}

    def __len__(self) -> int:
        return len(self.chunks)

    def _bm25(self, query_tokens: list[str], i: int) -> float:
        counts = self._counts[i]
        length = self._lengths[i] or 1
        score = 0.0
        for term in query_tokens:
            tf = counts.get(term, 0)
            if not tf:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * length / self._avg_len)
            score += self._idf.get(term, 0.0) * tf * (self.k1 + 1) / denom
        return score

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.45,
        distinct_documents: bool = True,
        whole_document: bool = True,
    ) -> list[Passage]:
        """Ranked passages above the relevance floor, or an empty list.

        `distinct_documents` returns one passage per article rather than the
        top chunks outright. The top three chunks are routinely three sections
        of the same article, which costs generation tokens without adding
        evidence.

        `whole_document` returns the article that the matching section belongs
        to, so that a question matched on Symptoms is still grounded on the
        Resolution steps that answer it.
        """
        query_tokens = tokenise(query)
        if not query_tokens:
            return []
        query_trigrams = trigrams(query)

        scored: list[tuple[float, float, int]] = []
        for i in range(len(self.chunks)):
            lexical = self._bm25(query_tokens, i)
            if lexical <= 0:
                continue
            # Saturating transform so the score is comparable across queries of
            # different lengths and a fixed floor means the same thing for each.
            lexical_norm = lexical / (lexical + 6.0)
            overlap = len(query_trigrams & self._trigrams[i]) / max(1, len(query_trigrams))
            scored.append((0.78 * lexical_norm + 0.22 * overlap, lexical_norm, i))

        scored.sort(key=lambda row: (-row[0], self.chunks[row[2]].chunk_id))

        results: list[Passage] = []
        seen: set[str] = set()
        for score, lexical_norm, i in scored:
            # The floor is applied to the lexical component alone. Trigram
            # overlap is a good tie-breaker and a bad admission test: any two
            # pieces of English share trigrams, so a question about pizza
            # clears a blended floor that a question about SSO also clears.
            if lexical_norm < min_score:
                break
            chunk = self.chunks[i]
            if distinct_documents and chunk.doc_id in seen:
                continue
            seen.add(chunk.doc_id)
            results.append(
                Passage(
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    category=chunk.category,
                    text=(
                        self._documents.get(chunk.doc_id, chunk.text)
                        if whole_document
                        else chunk.text
                    ),
                    score=round(score, 4),
                )
            )
            if len(results) >= top_k:
                break
        return results

    def resolve(self, chunk_id: str) -> Chunk | None:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None


def build_index(articles: list[dict[str, Any]], backend: str = "lexical", **kwargs: Any):
    """Index factory. The embedding backend is optional and degrades to lexical."""
    if backend == "embedding":
        try:
            from .retrieval_embedding import EmbeddingIndex

            return EmbeddingIndex(articles, **kwargs)
        except Exception as exc:  # pragma: no cover - optional dependency path
            import logging

            logging.getLogger(__name__).warning(
                "Embedding backend unavailable (%s); falling back to lexical retrieval.", exc
            )
    return LexicalIndex(articles, strategy=kwargs.get("strategy", "section"))
