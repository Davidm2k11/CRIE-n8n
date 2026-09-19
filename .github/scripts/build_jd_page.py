#!/usr/bin/env python3
"""Build the one-click-copy JD page from jd/<id>/job.json.

Usage: build_jd_page.py jd/<id>/job.json out.html
"""
import html, json, re, sys
from pathlib import Path

src = Path(sys.argv[1]); dst = Path(sys.argv[2])
data = json.loads(src.read_text(encoding="utf-8"))
job = data.get("job")
if not job:
    sys.exit("no posting parsed; per-source status: " + json.dumps(data.get("sources"), indent=1))
title = job.get("title") or "Job posting"
company = job.get("company") or ""
location = job.get("location") or ""
_parts = [x.strip() for x in location.split(",")]
location = ", ".join(x for i, x in enumerate(_parts) if x and (i == 0 or x != _parts[i - 1]))
desc = (job.get("description") or "").strip()
url = data["url"]

meta = []
for label, key in [("Posted", "posted"), ("Applicants", "applicants"),
                   ("Employment type", "employment_type"), ("Industry", "industry")]:
    if job.get(key):
        meta.append((label, job[key]))
for k, v in (job.get("criteria") or {}).items():
    meta.append((k, v))

# Plain text that the button copies: header block + description verbatim.
copy_text = "\n".join(filter(None, [title, company, location])) + "\n\n" + desc + "\n"

def render_description(text):
    """Paragraphs, bullet lists and short 'heading:' lines from the plain text."""
    out, para, items = [], [], []
    def flush_para():
        if para:
            t = " ".join(para).strip()
            if t:
                heading = (len(para) == 1 and len(t) <= 48 and len(t.split()) <= 6
                           and not t.endswith((",", ";")) and not t.startswith("-"))
                if heading:
                    out.append(f"<h3>{html.escape(t.rstrip(':.'))}</h3>")
                else:
                    out.append(f"<p>{html.escape(t)}</p>")
            para.clear()
    def flush_items():
        if items:
            out.append("<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>")
            items.clear()
    for line in text.split("\n"):
        s = line.strip()
        m = re.match(r"^(?:[-•*]|\d+[.)])\s+(.*)", s)
        if m:
            flush_para(); items.append(m.group(1))
        elif not s:
            flush_para(); flush_items()
        else:
            flush_items(); para.append(s)
    flush_para(); flush_items()
    return "\n".join(out)

meta_html = "".join(f'<div class="meta-item"><dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd></div>' for k, v in meta)
page_title = f"{company} {title}" if company else title
jd_all_json = json.dumps(copy_text, ensure_ascii=False).replace("</", "<\\/")
jd_desc_json = json.dumps(desc + "\n", ensure_ascii=False).replace("</", "<\\/")

page = f"""<title>{html.escape(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&display=swap">
<style>
  :root {{
    --bg: #F2F4F7; --surface: #FFFFFF; --ink: #161B22; --muted: #5C6675; --line: #DDE2E9;
    --accent: #0E6F6A; --accent-ink: #FFFFFF; --accent-soft: #E1F1EF; --ok: #1F7A3D;
    --shadow: 0 1px 2px rgba(22,27,34,.06), 0 8px 24px -12px rgba(22,27,34,.18);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #0F1317; --surface: #171C22; --ink: #E7EBF0; --muted: #98A2B0; --line: #2A323C;
      --accent: #3FC6B9; --accent-ink: #072B28; --accent-soft: #163330; --ok: #5BD48A;
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0F1317; --surface: #171C22; --ink: #E7EBF0; --muted: #98A2B0; --line: #2A323C;
    --accent: #3FC6B9; --accent-ink: #072B28; --accent-soft: #163330; --ok: #5BD48A;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Source Sans 3", "Segoe UI", system-ui, sans-serif; font-size: 17px; line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding-inline: 16px; padding-block: 0 56px; }}
  .bar {{
    position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5;
    background: var(--bg); background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line); margin-inline: -16px; padding: 12px 16px;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
  }}
  .bar .who {{ min-width: 0; font-size: 14px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .bar .who strong {{ color: var(--ink); font-weight: 600; }}
  .copy {{
    flex: none; display: inline-flex; align-items: center; gap: 8px;
    background: var(--accent); color: var(--accent-ink); border: 0; border-radius: 8px;
    font: inherit; font-weight: 600; font-size: 15px; padding: 10px 16px; cursor: pointer;
    box-shadow: var(--shadow); transition: transform .08s ease, background .2s ease;
  }}
  .copy:hover {{ transform: translateY(-1px); }}
  .copy:active {{ transform: translateY(0); }}
  .copy:focus-visible {{ outline: 3px solid var(--accent-soft); outline-offset: 2px; }}
  .copy svg {{ width: 18px; height: 18px; }}
  .copy.done {{ background: var(--ok); color: #fff; }}
  header.title {{ padding-block: 36px 8px; }}
  .eyebrow {{ font-size: 12.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin: 0 0 10px; }}
  h1 {{
    font-family: "Bricolage Grotesque", "Source Sans 3", system-ui, sans-serif; font-weight: 700;
    font-size: clamp(28px, 5.2vw, 40px); line-height: 1.08; letter-spacing: -.015em; margin: 0 0 8px; text-wrap: balance;
  }}
  .company {{ font-size: 20px; margin: 0; color: var(--ink); }}
  .company span {{ color: var(--muted); }}
  dl.meta {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px 20px;
    margin: 22px 0 0; padding: 18px 20px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  }}
  .meta-item {{ min-width: 0; }}
  dl.meta dt {{ font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin: 0 0 2px; }}
  dl.meta dd {{ margin: 0; font-weight: 600; overflow-wrap: anywhere; }}
  article {{ margin-top: 32px; }}
  article h2 {{ font-family: "Bricolage Grotesque", system-ui, sans-serif; font-size: 22px; margin: 0 0 14px; letter-spacing: -.01em; }}
  article h3 {{ font-size: 17px; font-weight: 600; margin: 24px 0 6px; }}
  article p {{ margin: 0 0 14px; max-width: 68ch; overflow-wrap: anywhere; }}
  article ul {{ margin: 0 0 16px; padding-left: 22px; max-width: 68ch; }}
  article li {{ margin: 0 0 6px; }}
  .foot {{ margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 14px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; }}
  .foot a {{ color: var(--accent); text-decoration: none; }}
  .foot a:hover {{ text-decoration: underline; }}
  .ghost {{ background: transparent; color: var(--accent); border: 1px solid var(--line); box-shadow: none; padding: 6px 12px; font-size: 14px; }}
  .ghost.done {{ background: var(--accent-soft); color: var(--ok); }}
  .toast {{
    position: fixed; left: 50%; bottom: calc(24px + env(safe-area-inset-bottom, 0px)); transform: translateX(-50%) translateY(8px);
    background: var(--ink); color: var(--bg); padding: 10px 16px; border-radius: 999px; font-size: 14px; font-weight: 600;
    opacity: 0; pointer-events: none; transition: opacity .18s ease, transform .18s ease; z-index: 10;
  }}
  .toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
  @media (prefers-reduced-motion: reduce) {{ .copy, .toast {{ transition: none; }} }}
  @media (max-width: 480px) {{ .bar .who {{ display: none; }} .bar {{ justify-content: flex-end; }} .copy {{ width: 100%; justify-content: center; }} }}
</style>

<div class="wrap">
  <div class="bar">
    <div class="who"><strong>{html.escape(title)}</strong>{(' · ' + html.escape(company)) if company else ''}</div>
    <button class="copy" id="copy-all" type="button" aria-live="polite">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
      <span>Copy job description</span>
    </button>
  </div>

  <header class="title">
    <p class="eyebrow">LinkedIn job {html.escape(data['job_id'])}</p>
    <h1>{html.escape(title)}</h1>
    <p class="company">{html.escape(company)}{(' <span>· ' + html.escape(location) + '</span>') if location else ''}</p>
    {('<dl class="meta">' + meta_html + '</dl>') if meta else ''}
  </header>

  <article>
    <h2>About the job</h2>
    {render_description(desc)}
  </article>

  <div class="foot">
    <a href="{html.escape(url)}" target="_blank" rel="noopener">View on LinkedIn ↗</a>
    <span>Fetched {html.escape(data.get('fetched_at', ''))}</span>
    <button class="copy ghost" id="copy-desc" type="button">Copy description only</button>
  </div>
</div>
<div class="toast" id="toast" role="status">Copied to clipboard</div>

<script type="application/json" id="jd-all">{jd_all_json}</script>
<script type="application/json" id="jd-desc">{jd_desc_json}</script>
<script>
(function () {{
  var all = JSON.parse(document.getElementById('jd-all').textContent);
  var only = JSON.parse(document.getElementById('jd-desc').textContent);
  var toast = document.getElementById('toast'); var t;

  function fallbackCopy(text) {{
    var ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.top = '-1000px';
    document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
    var ok = false; try {{ ok = document.execCommand('copy'); }} catch (e) {{}}
    document.body.removeChild(ta); return ok;
  }}
  function copy(text) {{
    if (navigator.clipboard && window.isSecureContext) {{
      return navigator.clipboard.writeText(text).then(function () {{ return true; }}, function () {{ return fallbackCopy(text); }});
    }}
    return Promise.resolve(fallbackCopy(text));
  }}
  function wire(id, text, doneLabel) {{
    var btn = document.getElementById(id); var label = btn.querySelector('span') || btn; var orig = label.textContent;
    btn.addEventListener('click', function () {{
      copy(text).then(function (ok) {{
        label.textContent = ok ? doneLabel : 'Copy failed — select the text';
        btn.classList.toggle('done', ok);
        toast.textContent = ok ? 'Copied to clipboard' : 'Clipboard blocked — select and copy manually';
        toast.classList.add('show'); clearTimeout(t);
        t = setTimeout(function () {{ toast.classList.remove('show'); label.textContent = orig; btn.classList.remove('done'); }}, 2200);
      }});
    }});
  }}
  wire('copy-all', all, 'Copied');
  wire('copy-desc', only, 'Copied');
}})();
</script>
"""
dst.write_text(page, encoding="utf-8")
print(f"wrote {dst} ({len(page)} bytes); copy payload {len(copy_text)} chars")
