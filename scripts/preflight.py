"""Confirm the installation before anything long is started.

Run: python -m scripts.preflight

Four checks, each reporting which one failed and what to do about it. This
exists because roughly half of all setup problems are a virtual environment
that is not active in the terminal being used, and the symptom of that is an
unrelated error several steps later.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ok(label: str, detail: str = "") -> bool:
    print(f"  [ ok ] {label}" + (f" — {detail}" if detail else ""))
    return True


def fail(label: str, detail: str) -> bool:
    print(f"  [FAIL] {label}\n         {detail}")
    return False


def main() -> int:
    print("Preflight\n")
    results = []

    version = sys.version_info
    if version < (3, 10):
        results.append(
            fail(
                f"Python {version.major}.{version.minor}",
                "This project needs 3.10 or newer. Create the environment with an "
                "explicit version: python3.11 -m venv .venv && source .venv/bin/activate",
            )
        )
    else:
        results.append(
            ok(f"Python {version.major}.{version.minor}.{version.micro}", sys.executable)
        )

    try:
        import fastapi  # noqa: F401
        import prometheus_client  # noqa: F401
        import requests  # noqa: F401
        from dotenv import load_dotenv  # noqa: F401

        results.append(ok("Dependencies installed"))
    except ImportError as exc:
        results.append(
            fail("Dependencies", f"{exc}. Run: pip install -r requirements.txt")
        )
        print("\nStopping: nothing further can be checked without the dependencies.")
        return 1

    from src.config import load_config
    from src.ingest import CorpusMissingError, load_corpus

    config = load_config()

    try:
        articles = load_corpus(config.corpus_path)
        from src.retrieval import LexicalIndex

        index = LexicalIndex(articles, strategy="section")
        passages = index.search("I cannot sign in, it says invalid credentials")
        if not passages or passages[0].doc_id != "DOC-AUTH-001":
            results.append(
                fail(
                    "Retrieval",
                    "The index built but a known question returned the wrong article. "
                    "Check that data/documentation.json is the file from the project pack.",
                )
            )
        else:
            results.append(
                ok(
                    "Retrieval",
                    f"{len(articles)} articles, {len(index)} section chunks; "
                    f"a known question returned {passages[0].doc_id}",
                )
            )
    except CorpusMissingError as exc:
        results.append(fail("Corpus", str(exc)))

    if not config.has_credentials:
        results.append(
            fail(
                "Model provider",
                f"No API key. Copy .env.example to .env and set "
                f"{'OPENROUTER_API_KEY' if config.provider == 'openrouter' else 'GROQ_API_KEY'}. "
                f"A free key is at https://console.groq.com/keys. The system will still run "
                f"without one, but every ticket will escalate.",
            )
        )
    else:
        from src.llm import LLMClient, ModelUnavailable

        try:
            completion = LLMClient(config).complete(
                [{"role": "system", "content": "Reply with one word."},
                 {"role": "user", "content": "Say: ready"}],
                prompt_version="preflight-v1",
                max_tokens=300,
                use_cache=False,
            )
            results.append(
                ok(
                    f"Model provider ({config.provider})",
                    f"{config.model_name} replied {completion.text[:40]!r}",
                )
            )
        except ModelUnavailable as exc:
            results.append(
                fail(
                    f"Model provider ({config.provider})",
                    f"{exc}\n         Check the key, and check the model name against the "
                    f"provider's live model list — retired models return 404.",
                )
            )

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed.")
    if passed == len(results):
        print(
            "\nReady. Next:\n"
            "  python -m evaluation.harness --input data/validation_tickets.json "
            "--output evaluation/results/"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
