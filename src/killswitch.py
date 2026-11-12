"""The kill switch.

A file whose presence halts automatic answering and whose contents are the
reason. A file rather than an environment variable, because an environment
variable needs a restart and a restart is a deployment under another name —
and the point of a kill switch is that it works when a deployment is the
thing you cannot do.

It is read once per ticket at the pipeline edge and the result is passed into
the router as an argument. Reading it inside the router would make routing
depend on the clock, and A5 is checked by running the same ticket twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KillSwitchState:
    active: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.active


def read(path: str | Path) -> KillSwitchState:
    path = Path(path)
    if not path.exists():
        return KillSwitchState(active=False)
    try:
        reason = path.read_text(encoding="utf-8").strip()
    except OSError:
        reason = ""
    return KillSwitchState(active=True, reason=reason or "No reason recorded.")


def engage(path: str | Path, reason: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason.strip() + "\n", encoding="utf-8")


def release(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
