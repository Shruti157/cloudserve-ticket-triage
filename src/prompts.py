"""Prompt registry.

Prompts are design artefacts, so they live in files with a version and the
requirement IDs they serve, not in string literals next to the call site. The
version string goes into the cache key and into every decision log record, so
a logged decision can be reproduced against the exact text that produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import ROOT

PROMPT_DIR = ROOT / "prompts"

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SECTION = re.compile(r"^\[(SYSTEM|USER)\]\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Prompt:
    id: str
    name: str
    version: str
    requirement_ids: tuple[str, ...]
    system: str
    user: str

    @property
    def label(self) -> str:
        """The string recorded in the decision log, e.g. 'PR-01 v1.3'."""
        return f"{self.id} v{self.version}"

    def render(self, **values: object) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system.format(**values)},
            {"role": "user", "content": self.user.format(**values)},
        ]


def _parse(text: str) -> Prompt:
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError("Prompt file is missing its --- front matter block.")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = text[match.end() :]
    parts = _SECTION.split(body)
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i]] = parts[i + 1].strip()

    return Prompt(
        id=meta["id"],
        name=meta.get("name", meta["id"]),
        version=meta.get("version", "0"),
        requirement_ids=tuple(
            r.strip() for r in meta.get("requirement_ids", "").split(",") if r.strip()
        ),
        system=sections.get("SYSTEM", ""),
        user=sections.get("USER", ""),
    )


@lru_cache(maxsize=None)
def load_prompt(prompt_id: str) -> Prompt:
    matches = sorted(PROMPT_DIR.glob(f"{prompt_id}_*.txt"))
    if not matches:
        raise FileNotFoundError(
            f"No prompt file for {prompt_id} in {PROMPT_DIR}. Prompts are part "
            f"of the repository; check out the whole tree rather than src/."
        )
    return _parse(matches[0].read_text(encoding="utf-8"))


def all_prompts() -> list[Prompt]:
    return [_parse(p.read_text(encoding="utf-8")) for p in sorted(PROMPT_DIR.glob("PR-*.txt"))]
