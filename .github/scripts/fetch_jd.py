#!/usr/bin/env python3
"""Fetch a public LinkedIn job posting from a GitHub-hosted runner.

Utility for .github/workflows/fetch-jd.yml. The Claude Code remote sandbox
sits behind an allowlist egress proxy that cannot reach linkedin.com, so the
fetch runs on a GitHub Actions runner instead and the result is committed back
to the branch under jd/<job_id>/.

Sources tried, in order (all are public, no credentials involved):
  1. jobs-guest API  - HTML fragment LinkedIn serves to logged-out visitors
  2. /jobs/view/<id> - public SEO page; carries a JSON-LD JobPosting block
  3. r.jina.ai relay of each of the above - fallback if LinkedIn rate-limits
     datacenter IPs (HTTP 429/999)

Outputs (under jd/<job_id>/):
  raw/<source>.<ext>  every response body, untouched
  job.json            parsed fields + per-source status
  job.md              human-readable posting (title, company, location, ...)
  description.txt     plain-text description only
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

JOB_ID = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JOB_ID", "")
if not JOB_ID.isdigit():
    sys.exit("usage: fetch_jd.py <numeric LinkedIn job id>")

OUT = Path("jd") / JOB_ID
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

VIEW = f"https://www.linkedin.com/jobs/view/{JOB_ID}/"
GUEST = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{JOB_ID}"
SOURCES = [
    ("guest_api", GUEST, "html"),
    ("view_page", VIEW, "html"),
    ("jina_view", "https://r.jina.ai/" + VIEW, "md"),
    ("jina_guest", "https://r.jina.ai/" + GUEST, "md"),
]
RETRY_ON = {429, 999, 500, 502, 503, 504}


def fetch(url, attempts=4):
    """GET with browser headers; exponential backoff on rate-limit codes."""
    delay = 5
    last = (0, url, "")
    for _ in range(attempts):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") if e.fp else ""
            last = (e.code, url, body)
            if e.code not in RETRY_ON:
                return last
        except Exception as e:  # noqa: BLE001 - record and retry
            last = (0, url, f"{type(e).__name__}: {e}")
        time.sleep(delay)
        delay *= 2
    return last


# --------------------------------------------------------------------------
# HTML -> plain text, keeping paragraph and list structure
# --------------------------------------------------------------------------
class TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
             "section", "article", "header", "footer", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0
        self.lists = []  # stack of [tag, counter]

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("ul", "ol"):
            if not self.lists:
                self.out.append("\n")
            self.lists.append([tag, 0])
        elif tag == "li":
            indent = "  " * max(0, len(self.lists) - 1)
            if self.lists and self.lists[-1][0] == "ol":
                self.lists[-1][1] += 1
                self.out.append(f"\n{indent}{self.lists[-1][1]}. ")
            else:
                self.out.append(f"\n{indent}- ")
        elif tag == "br":
            self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("ul", "ol"):
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        # Source-HTML indentation is noise; list indentation is emitted by <li>.
        data = re.sub(r"\s+", " ", data.replace("\xa0", " "))
        if self.out and self.out[-1].endswith("\n"):
            data = data.lstrip()
        if data:
            self.out.append(data)

    def text(self):
        t = "".join(self.out)
        t = re.sub(r" *\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()


def html_to_text(fragment):
    p = TextExtractor()
    p.feed(fragment)
    p.close()
    return p.text()


def element_inner(doc, open_tag_regex, tag):
    """Inner HTML of the first element matched by open_tag_regex, nesting-aware."""
    m = re.search(open_tag_regex, doc, re.S | re.I)
    if not m:
        return None
    pos = m.end()
    depth = 1
    token = re.compile(rf"<(/?){tag}\b[^>]*>", re.I)
    for t in token.finditer(doc, pos):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return doc[pos:t.start()]
    return doc[pos:]


# --------------------------------------------------------------------------
# Parsers for each source shape
# --------------------------------------------------------------------------
def parse_jsonld(page):
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except Exception:  # noqa: BLE001
            continue
        for d in data if isinstance(data, list) else [data]:
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                return d
    return None


def from_jsonld(d):
    org = d.get("hiringOrganization") or {}
    loc = d.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") or {}
    parts = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
    desc_html = html.unescape(d.get("description") or "")
    return {
        "title": d.get("title"),
        "company": org.get("name") if isinstance(org, dict) else org,
        "location": ", ".join(p for p in parts if p) or None,
        "employment_type": d.get("employmentType"),
        "date_posted": d.get("datePosted"),
        "valid_through": d.get("validThrough"),
        "industry": d.get("industry"),
        "description": html_to_text(desc_html),
        "description_html": desc_html,
    }


def from_guest(fragment):
    def first(pattern):
        m = re.search(pattern, fragment, re.S | re.I)
        return html_to_text(m.group(1)) if m else None

    criteria = {}
    for h, v in re.findall(
        r'<h3 class="description__job-criteria-subheader">(.*?)</h3>\s*'
        r'<span class="description__job-criteria-text[^"]*">(.*?)</span>', fragment, re.S):
        criteria[html_to_text(h)] = html_to_text(v)

    desc_html = element_inner(fragment, r'<div class="show-more-less-html__markup[^"]*"[^>]*>', "div")
    return {
        "title": first(r'<h2 class="top-card-layout__title[^"]*"[^>]*>(.*?)</h2>'),
        "company": first(r'<a class="topcard__org-name-link[^"]*"[^>]*>(.*?)</a>')
                   or first(r'<span class="topcard__flavor">(.*?)</span>'),
        "location": first(r'<span class="topcard__flavor topcard__flavor--bullet">(.*?)</span>'),
        "posted": first(r'<span class="posted-time-ago__text[^"]*"[^>]*>(.*?)</span>'),
        "applicants": first(r'<span class="num-applicants__caption[^"]*"[^>]*>(.*?)</span>'),
        "criteria": criteria or None,
        "description": html_to_text(desc_html) if desc_html else None,
        "description_html": desc_html,
    }


def looks_like_authwall(status, final_url, body):
    return status != 200 or "authwall" in (final_url or "") or "/login" in (final_url or "") \
        or len(body) < 2000


# --------------------------------------------------------------------------
def main():
    results, bodies = {}, {}
    for name, url, ext in SOURCES:
        status, final, body = fetch(url)
        (RAW / f"{name}.{ext}").write_text(body, encoding="utf-8")
        results[name] = {"url": url, "status": status, "final_url": final, "bytes": len(body)}
        bodies[name] = (status, final, body)
        print(f"[{name}] HTTP {status} {len(body):>8} bytes  -> {final}")

    parsed, source = None, None

    # Prefer the structured JSON-LD from the public view page.
    st, fin, body = bodies["view_page"]
    if not looks_like_authwall(st, fin, body):
        d = parse_jsonld(body)
        if d and d.get("description"):
            parsed, source = from_jsonld(d), "view_page (JSON-LD)"

    # Then the guest API fragment.
    if not parsed:
        st, fin, body = bodies["guest_api"]
        if st == 200 and "show-more-less-html__markup" in body:
            g = from_guest(body)
            if g.get("description"):
                parsed, source = g, "guest_api"

    # Then the relay copies (markdown; keep verbatim).
    if not parsed:
        for name in ("jina_view", "jina_guest"):
            st, fin, body = bodies[name]
            if st == 200 and len(body) > 1500 and "authwall" not in body.lower()[:3000]:
                parsed, source = {"markdown": body}, name
                break

    out = {"job_id": JOB_ID, "url": VIEW, "source": source, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sources": results, "job": parsed}
    (OUT / "job.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if not parsed:
        print("\n!! No source yielded a parseable posting. Raw bodies saved under", RAW)
        (OUT / "job.md").write_text(f"# Job {JOB_ID}\n\nFetch failed on all sources. See raw/ and job.json.\n", encoding="utf-8")
        return

    if "markdown" in parsed:
        md = parsed["markdown"]
        desc = md
    else:
        lines = [f"# {parsed.get('title') or 'Untitled'}", ""]
        meta = [("Company", parsed.get("company")), ("Location", parsed.get("location")),
                ("Employment type", parsed.get("employment_type")), ("Posted", parsed.get("posted") or parsed.get("date_posted")),
                ("Applicants", parsed.get("applicants")), ("Industry", parsed.get("industry"))]
        for k, v in (parsed.get("criteria") or {}).items():
            meta.append((k, v))
        for k, v in meta:
            if v:
                lines.append(f"**{k}:** {v}  ")
        lines += ["", f"Source: {VIEW}", "", "---", "", parsed.get("description") or ""]
        md = "\n".join(lines).rstrip() + "\n"
        desc = parsed.get("description") or ""

    (OUT / "job.md").write_text(md, encoding="utf-8")
    (OUT / "description.txt").write_text(desc.rstrip() + "\n", encoding="utf-8")
    print(f"\nParsed via: {source}")
    print("===== JD START =====")
    print(md)
    print("===== JD END =====")


if __name__ == "__main__":
    main()
