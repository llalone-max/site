#!/usr/bin/env python3
"""resume_sync.py: keep the live site's record PDFs and preview image in sync
with Lazar LaLone's newest resumes, with no manual copying.

Source of truth is the Current Resumes folder on the Desktop:

    newest *_P.pdf  ->  record-healthcare.pdf   (+ record-healthcare-p1.webp preview)
    newest *_M.pdf  ->  record-brands.pdf        (brands panel has no preview image)

Files whose name flags them as not-for-use are skipped: "SUPERSEDED",
"DO NOT SEND", and "OLD" (case-insensitive). The AI lane no longer has a
record, so record-ai.* is never written or touched.

Behavior:
  - Idempotent: a file is only rewritten when its bytes differ. A run where
    nothing changed does nothing and exits 0.
  - Commits only when something actually changed, then git pull --rebase
    (the meter GitHub Action also pushes to main) and git push.
  - Fail-soft: logs clearly and exits non-zero on error without leaving the
    repo in a half-rebased or half-committed state.

Dependencies: Python stdlib + Pillow (already used in this project) + pdftoppm
(poppler, already installed).
"""

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image

# --- configuration -----------------------------------------------------------

SRC_DIR = Path(
    "/Users/lazarlalone/Desktop/Resume Archive v2.0/"
    "Current Resumes - All Current Versions"
)
REPO = Path(__file__).resolve().parent

# Name markers that mean "do not use this file". SUPERSEDED is required by the
# spec; DO NOT SEND and OLD are the same class of "not for use" marker (the
# DO NOT SEND files are known-broken 2-page Word exports), so shipping one to
# the live site would be a mistake.
EXCLUDE_MARKERS = ("superseded", "do not send", "old")

# Preview dimensions must match what the page already references
# (healthcare.html: <img width="1000" height="1294">).
PREVIEW_W, PREVIEW_H = 1000, 1294

# Each lane: source glob, destination PDF, preview WEBP (or None if the panel
# does not use a preview image).
LANES = [
    ("*_P.pdf", "record-healthcare.pdf", "record-healthcare-p1.webp"),
    ("*_M.pdf", "record-brands.pdf", None),
]

# Git identity used for the automated commit (repo user.name is unset, and
# launchd runs have no interactive git config), passed inline so the script is
# self-contained.
GIT_NAME = "Lazar LaLone"
GIT_EMAIL = "lazarlalone@gmail.com"

COMMIT_MSG = "resume: sync newest _P/_M to the site"


# --- helpers -----------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] resume_sync: {msg}", flush=True)


def excluded(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in EXCLUDE_MARKERS)


def newest_source(glob: str):
    """Newest non-excluded PDF matching glob, or None."""
    cands = [p for p in SRC_DIR.glob(glob) if p.is_file() and not excluded(p.name)]
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def render_preview(pdf_path: Path) -> bytes:
    """Render page 1 of pdf_path to WEBP bytes at the page's preview size."""
    with tempfile.TemporaryDirectory() as td:
        prefix = os.path.join(td, "page")
        subprocess.run(
            ["pdftoppm", "-png", "-f", "1", "-l", "1", "-r", "200",
             "-singlefile", str(pdf_path), prefix],
            check=True, capture_output=True,
        )
        img = Image.open(prefix + ".png").convert("RGB")
        img = img.resize((PREVIEW_W, PREVIEW_H), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=80, method=6)
        return buf.getvalue()


def write_if_changed(dest: Path, data: bytes) -> bool:
    """Write data to dest only if it differs. Return True if written."""
    if dest.exists() and dest.read_bytes() == data:
        return False
    dest.write_bytes(data)
    return True


def git(*args, check=True):
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True, check=check,
    )


# --- main --------------------------------------------------------------------

def sync() -> list[str]:
    """Sync all lanes. Return repo-relative paths of files that changed."""
    changed: list[str] = []

    for glob, dest_name, preview_name in LANES:
        src = newest_source(glob)
        if src is None:
            log(f"no usable source for {glob} (all missing/superseded/broken); "
                f"leaving {dest_name} unchanged")
            continue

        log(f"{glob}: newest usable source is {src.name!r}")
        dest = REPO / dest_name
        pdf_bytes = src.read_bytes()
        pdf_changed = write_if_changed(dest, pdf_bytes)
        if pdf_changed:
            log(f"updated {dest_name} (bytes differed)")
            changed.append(dest_name)
        else:
            log(f"{dest_name} already current, no change")

        if preview_name:
            preview = REPO / preview_name
            if pdf_changed or not preview.exists():
                webp = render_preview(src)
                if write_if_changed(preview, webp):
                    log(f"regenerated {preview_name}")
                    changed.append(preview_name)
            else:
                log(f"{preview_name} up to date (source pdf unchanged)")

    return changed


def commit_and_push(files: list[str]) -> None:
    git("add", "--", *files)
    # Nothing staged (e.g. identical bytes slipped through) -> nothing to do.
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        log("staging produced no diff; nothing to commit")
        return

    git("-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_EMAIL}",
        "commit", "-m", COMMIT_MSG)
    log("committed changes")

    # The meter Action also pushes to main; rebase our commit on top first.
    pull = git("pull", "--rebase", "origin", "main", check=False)
    if pull.returncode != 0:
        log(f"git pull --rebase failed; aborting rebase to stay clean:\n{pull.stderr}")
        git("rebase", "--abort", check=False)
        raise RuntimeError("pull --rebase failed")

    push = git("push", "origin", "main", check=False)
    if push.returncode != 0:
        # Commit is local only; not a broken half-state. Next run will retry.
        log(f"git push failed (commit stays local, will retry next run):\n{push.stderr}")
        raise RuntimeError("push failed")
    log("pushed to origin/main")


def main() -> int:
    if not SRC_DIR.is_dir():
        log(f"source folder not found: {SRC_DIR}")
        return 1
    try:
        changed = sync()
    except subprocess.CalledProcessError as e:
        log(f"render/copy step failed: {e}\n{getattr(e, 'stderr', b'')!r}")
        return 1

    if not changed:
        log("nothing changed; exiting 0 (no-op)")
        return 0

    log(f"changed files: {', '.join(changed)}")
    try:
        commit_and_push(changed)
    except Exception as e:  # noqa: BLE001 - fail soft, log and signal error
        log(f"git step failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
