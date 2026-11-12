"""CloudServe intelligent support system.

A version guard lives here rather than in the README, because a README assertion
about the interpreter does not survive `python3 -m venv` on a machine whose
python3 is 3.9. Getting it wrong should produce a sentence, not a TypeError on a
union type annotation three imports later.
"""

import sys

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"This project needs Python 3.10 or newer; this interpreter is "
        f"{sys.version_info.major}.{sys.version_info.minor}. Create the virtual "
        f"environment with an explicit version, for example "
        f"`python3.11 -m venv .venv`, then `source .venv/bin/activate` and "
        f"reinstall with `pip install -r requirements.txt`."
    )

__version__ = "1.0.0"
