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
