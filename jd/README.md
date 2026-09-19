# jd/

Output folder for `.github/workflows/fetch-jd.yml` (not part of the CRIE baseline).

- `REQUEST` - the numeric LinkedIn job id to fetch. Change it and commit through
  the GitHub API or web UI; the push triggers the workflow. Pushes from the
  Claude sandbox's git proxy do not raise push events, so use the API path.
- `<job_id>/` - one folder per fetched posting: `raw/` (every response body),
  `job.json` (parsed fields + per-source status), `job.md`, `description.txt`.
