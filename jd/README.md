# jd/

Output folder for `.github/workflows/fetch-jd.yml` (not part of the CRIE baseline).

Fastest path, from any checkout of the repo:

    .github/scripts/jd.sh https://www.linkedin.com/jobs/view/<id>/ [out.html]

It writes the id to `REQUEST` on the utility branch, pushes, waits for the runner's
result commit, pulls it, and builds the one-click-copy page at `out.html`.

- `REQUEST` - first line is the numeric LinkedIn job id to fetch (lines below it
  are ignored). Changing it and pushing triggers the workflow, which commits the
  result back with `[skip ci]`.
- `<job_id>/` - one folder per fetched posting: `raw/` (every response body),
  `job.json` (parsed fields + per-source status), `job.md`, `description.txt`.
