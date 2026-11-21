"""Render the submission markdown to PDF and package the archive.

The report and the workbooks are written as markdown so they can be diffed and
reviewed like anything else in the repository, but the Submission Guide asks
for PDFs with specific filenames. This turns one into the other.

Chrome does the rendering because it is the only HTML engine already present
on a machine with a browser, and it has to be served over HTTP rather than
opened as a file:// URL, which Chrome's headless mode treats inconsistently.

    python -m scripts.build_submission            # PDFs only
    python -m scripts.build_submission --archive  # PDFs, then the zip

Needs `markdown`, which is not a runtime dependency and is deliberately not in
requirements.txt: nothing the graded system does requires it.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMISSION = ROOT / "submission"
AUTHOR = "ShrutiMittal"

# The guide names two files exactly. Everything else keeps its own name.
RENAMES = {"Effort_Log": f"{AUTHOR}_Effort_Log"}

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

CSS = """
@page { size: A4; margin: 19mm 17mm 20mm 17mm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11.5pt;
       line-height: 1.52; color: #111; }
h1 { font-size: 21pt; border-bottom: 2px solid #333; padding-bottom: 6px; }
h2 { font-size: 15pt; margin-top: 26pt; border-bottom: 1px solid #bbb;
     padding-bottom: 3px; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin-top: 16pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt;
        margin: 12px 0 16px; page-break-inside: avoid; }
th, td { border: 1px solid #999; padding: 5px 6px; text-align: left;
         vertical-align: top; }
th { background: #eee; }
pre { background: #f5f5f5; border: 1px solid #ddd; padding: 9px; font-size: 9pt;
      line-height: 1.3; white-space: pre-wrap; page-break-inside: avoid;
      font-family: Menlo, monospace; }
code { font-family: Menlo, monospace; font-size: 9.5pt; background: #f2f2f2;
       padding: 0 2px; }
pre code { background: none; font-size: 9pt; }
blockquote { border-left: 3px solid #bbb; margin-left: 0; padding-left: 12px;
             color: #333; font-style: italic; }
hr { border: none; border-top: 1px solid #ccc; margin: 20px 0; }
p { text-align: justify; margin: 9px 0; }
"""


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    sys.exit(
        "No Chrome or Chromium found. Install one, or convert "
        "submission/**/*.md to PDF by whatever means you have."
    )


def page_count(pdf: Path) -> int:
    import re

    return len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))


def render(sources: list[Path], staging: Path, chrome: str, port: int) -> list[Path]:
    try:
        import markdown
    except ImportError:
        sys.exit("pip install markdown")

    for source in sources:
        body = markdown.markdown(
            source.read_text(),
            extensions=["tables", "fenced_code", "toc", "sane_lists"],
        )
        (staging / f"{source.stem}.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{source.stem}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>"
        )

    handler = functools.partial(QuietHandler, directory=str(staging))
    with socketserver.TCPServer(("127.0.0.1", port), handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        written = []
        for source in sources:
            name = RENAMES.get(source.stem, source.stem)
            out = source.with_name(f"{name}.pdf")
            subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={out}",
                    f"http://127.0.0.1:{port}/{source.stem}.html",
                ],
                check=True,
                capture_output=True,
            )
            written.append(out)
        server.shutdown()
    return written


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # noqa: D102
        pass


def package(pdfs: list[Path]) -> Path:
    """Four top-level folders, nothing nested inside another folder."""
    archive = ROOT / f"{AUTHOR}_Capstone_Submission.zip"
    folders = ["01_Video", "02_Report", "03_Workbooks", "04_Source_Code"]

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in folders:
            zf.writestr(f"{folder}/", "")
        for pdf in pdfs:
            folder = "02_Report" if pdf.parent.name == "02_Report" else "03_Workbooks"
            zf.write(pdf, f"{folder}/{pdf.name}")
        for rel in tracked:
            # The repository goes in whole, minus the submission folder, whose
            # PDFs are already placed above and whose markdown would duplicate
            # them.
            if rel.startswith("submission/"):
                continue
            zf.write(ROOT / rel, f"04_Source_Code/{rel}")

    video = SUBMISSION / "01_Video"
    if not any(video.glob("*")) if video.exists() else True:
        print("\n  01_Video is empty. The archive is incomplete until it is not.")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="store_true", help="also write the zip")
    parser.add_argument("--port", type=int, default=8777)
    args = parser.parse_args()

    sources = sorted(SUBMISSION.glob("0[23]_*/*.md"))
    if not sources:
        sys.exit(f"No markdown found under {SUBMISSION}")

    with tempfile.TemporaryDirectory() as tmp:
        pdfs = render(sources, Path(tmp), find_chrome(), args.port)

    for pdf in pdfs:
        print(f"  {page_count(pdf):3d} pages  {pdf.relative_to(ROOT)}")

    report = next((p for p in pdfs if "Capstone_Report" in p.name), None)
    if report and not 20 <= page_count(report) <= 30:
        print(
            f"\n  The report is {page_count(report)} pages. "
            "The guide asks for 20 to 30, excluding appendices."
        )

    if args.archive:
        archive = package(pdfs)
        print(f"\n  {archive.relative_to(ROOT)} "
              f"({round(archive.stat().st_size / 1_048_576, 1)} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
