# _ops/ — why the underscore

This folder was `ops/` until 2026-08-25. It holds manifests owned by other terminals, not by the
site.

**It was renamed because this repo is the live website.** Every file here publishes to
lazarlalone.com within about a minute of a push, so `ops/resume-sync/process.manifest.yaml` was
readable by anyone at `https://lazarlalone.com/ops/resume-sync/process.manifest.yaml`. It holds
no credentials, but it published the resume source folder, the launchd job name and the log
paths on a marketing domain. Lazar's call on 2026-08-25 was that it should not stay public.

**Why a rename fixes it, and why nothing broke.** GitHub Pages runs Jekyll on this repo (there is
no `.nojekyll` file) and Jekyll does not copy paths beginning with an underscore into the
published site, so both URLs now return 404. `process-indexing/discover.py` finds manifests with
`rglob("process.manifest.yaml")` under `~/site-repo`, which is one of its SCAN_ROOTS, and rglob
does not care what the folder is called, so the registry still sees this file. The manifest's own
relative `docs:` path still resolves, because the new folder sits at the same depth.

**If you add a manifest here, keep it under this folder.** Anything placed at the repo root, or
in any folder without a leading underscore, is public the moment it is pushed. See MANDATE 2.3.1
in `~/Desktop/Personal Site Elements/MANDATE.md`.

**If anyone ever adds a `.nojekyll` file to this repo, everything in here becomes public in the
same push.** That is the one thing that would silently undo this.

---

## Standing defect: resume_sync has never run. Whoever owns it, this is for you.

Written by the site terminal on 2026-10-11, as it was being closed. The site terminal did NOT
touch `resume_sync.py`: MANDATE 6.2b says it is not ours. This note is here because this is the
folder the owning terminal reads.

**It has never worked, not once.** `~/Library/Logs/resume-sync.log` has said "no usable source"
on every single run since the log began. It exits 0, so nothing has ever flagged it. The site
served a July resume until a human copied the current one across by hand on 2026-09-18.

**Two independent causes. Fixing either one alone still leaves it broken.**

1. **macOS will not let a launchd agent read `~/Desktop`**, and it does not say so. The folder
   reads as EMPTY. Proved by submitting a probe through `launchctl` that found 0 files in the
   resume archive while the same code in a shell found 4. The fix is Full Disk Access for
   `/usr/bin/python3`, which only Lazar can grant, and it is written up for him in
   `~/Desktop/Personal Site Elements/HUMAN_HANDOFF.md` section 1.1. Alternatively, move the
   source folder out of Desktop, Documents and Downloads, which needs nobody's permission.
2. **The glob patterns are out of date.** `LANES` looks for `*_P.pdf` and `*_M.pdf`. The current
   files are named "Lazar LaLone - P v1.1.pdf" and "M v1.2.docx", which match neither, and every
   `_M` file that does match is marked SUPERSEDED or DO NOT SEND.

**Three traps for the rewrite:**

1. **"Newest file wins" is wrong and would embarrass him.** On 2026-09-18 the newest PDF in that
   folder was "Resume 9_4_26.pdf", byte-identical (same md5) to his Success Academy job
   application resume. A newest-wins rule publishes a resume written for one employer onto his
   public site.
2. **The real source of truth is `resume_content.py`**, in `~/Desktop/Resume Archive v2.0/Resume
   Build Tooling/`, with `render_pdf.py` rendering from it using that folder's own venv.
   Rendering from there sidesteps the whole naming problem. The PDFs in the archive are output.
3. **`LANES` lists no preview image for the brands lane, but `brands.html` shows one**
   (`record-brands-p1.webp`). A working sync would still leave that image stale. Previews are
   page one at 200dpi, resized to exactly 1000x1294, WEBP quality 80.

**And the general lesson, which is bigger than this job:** it failed silently for a month because
it exited 0 and wrote to a log nothing read. A scheduled job that cannot fail loudly is not
finished. The auto-memory note is `scheduled-jobs-cannot-read-desktop`.

---

## The analytics opt-out on index.html (moved here 2026-10-21)

This note sat as a comment in the public page source until 2026-10-21; it lives here now so visitors cannot read it.
The code checks for `notrack` to set the flag and for `track=0` or `untrack` to clear it (the old comment said `/?track=1`, which the code does not check).

Cloudflare Web Analytics, with a way to leave MYSELF out of the numbers.
Visiting /?notrack=1 once in a browser sets a flag and the beacon never loads
there again; /?track=1 undoes it. This has to exist because I open the site
constantly to edit and audit it, and on a site this size my own visits would
be most of the "direct" traffic, which is the very bucket that tells me
whether LinkedIn is working.
The flag is localStorage, NOT a cookie: the page says this site uses no
cookies and that stays literally true (the fortune already uses
sessionStorage the same way). Nothing is sent anywhere; it only decides
whether to load Cloudflare's cookieless beacon.
