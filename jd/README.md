# jd/

Output folder for `.github/workflows/fetch-jd.yml` (not part of the CRIE baseline).

- `REQUEST` - first line is the numeric LinkedIn job id to fetch (lines below it
  are ignored, so notes are fine). Change it and push; the push triggers the
  workflow, which commits the result back with `[skip ci]`.
- `<job_id>/` - one folder per fetched posting: `raw/` (every response body),
  `job.json` (parsed fields + per-source status), `job.md`, `description.txt`.
