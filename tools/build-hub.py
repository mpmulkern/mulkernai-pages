#!/usr/bin/env python3
"""
Build index.html (the hub) for pages.mulkernai.com.

WHY THIS IS A GENERATOR AND NOT A HAND-WRITTEN FILE
---------------------------------------------------
sitemap.xml on this repo rotted because it was written from a generation log
and then simply stopped being updated (last write 2026-07-16; the 2026-07-28
run added 20 pages and never touched it). A hand-listed hub has the identical
failure mode: the next TrafficForge run adds pages, the hub does not know, and
the orphan problem this hub exists to fix comes straight back.

So the page list is DERIVED from the repo file list at build time. Re-run this
script after any run that adds or removes pages and commit the result.

TODO (agreed with tf-engineer, 31 Jul 2026): when the verified-page manifest
from the post-publish verification gate exists, replace discover_pages() with
a read of that manifest. Per tf-engineer's Tier 1 item 2
(findings/03-trafficforge-template-geo.md §3), sitemap.xml, this hub and the
internal "Related Pages" links should all three derive from that ONE manifest
rather than each having its own logic -- which is exactly how sitemap.xml and
the internal links ended up independently wrong in different ways. Only
discover_pages() should need to change; everything below is already a pure
function of the page list.

Usage:  python3 tools/build-hub.py            # writes index.html
        python3 tools/build-hub.py --check    # prints what it would emit
"""

import os
import re
import sys
import html
import json
import collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE = {"index.html", "404.html"}

# Roles that MAS actually sells today. Each maps to its live subdomain, which
# is the canonical destination for that role's head term -- pages here are
# supporting content and must point at the subdomain, never compete with it.
SUBDOMAIN = {
    "CFO": "https://cfo.mulkernai.com",
    "CMO": "https://cmo.mulkernai.com",
    "COO": "https://coo.mulkernai.com",
    "CEO": "https://ceo.mulkernai.com",
}

# Roles deliberately NOT surfaced on the hub.
#
# CTO: eight complete pages are live, but cto.mulkernai.com is NXDOMAIN and it
# is an open operator question whether MAS sells a fractional-CTO suite at all
# (Suki, Phase 6 handoff §3). Promoting eight pages for a product that may not
# exist is worse than leaving them orphaned. When Mike answers:
#   YES -> move "CTO" out of HELD_BACK into SUBDOMAIN with its new subdomain,
#          re-run this script, commit. That is the entire change.
#   NO  -> leave as is. They stay unlisted and unlinked.
HELD_BACK = {"CTO"}

SECTION_TITLE = {
    "CFO": "Fractional CFO",
    "CMO": "Fractional CMO",
    "COO": "Fractional COO",
    "CEO": "Fractional CEO",
    "CAIO": "Chief AI Officer",
    "C-SUITE": "Agentic AI for the C-suite",
}

SECTION_ORDER = ["CFO", "CMO", "COO", "CEO", "CAIO", "C-SUITE"]


def discover_pages(repo=REPO):
    """Return [(slug, title, description), ...] derived from the repo files.

    This is the seam to replace with a manifest read. See module docstring.
    """
    out = []
    for name in sorted(os.listdir(repo)):
        if not name.endswith(".html") or name in EXCLUDE:
            continue
        raw = open(os.path.join(repo, name), encoding="utf-8", errors="replace").read()
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
        desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', raw, re.I)
        title = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else ""
        if not title:
            # No usable title: skip rather than emit a blank link. A page with
            # no h1 is a defect to fix at source, not to paper over here.
            print(f"  WARN no <h1>, skipped: {name}", file=sys.stderr)
            continue
        out.append((name[:-5], title, (desc.group(1).strip() if desc else "")))
    return out


def classify(slug):
    s = slug.lower()
    for r in ("cfo", "cto", "cmo", "coo", "ceo"):
        if re.search(rf"\b{r}\b", s.replace("-", " ")):
            return r.upper()
    if "chief-ai-officer" in s:
        return "CAIO"
    if "c-suite" in s:
        return "C-SUITE"
    return "OTHER"


def build(pages):
    groups = collections.defaultdict(list)
    for slug, title, desc in pages:
        role = classify(slug)
        if role in HELD_BACK or role == "OTHER":
            continue
        groups[role].append((slug, title, desc))

    shown = sum(len(v) for v in groups.values())
    parts = []
    for role in SECTION_ORDER:
        items = sorted(groups.get(role, []), key=lambda r: r[1].lower())
        if not items:
            continue
        heading = html.escape(SECTION_TITLE.get(role, role))
        sub = SUBDOMAIN.get(role)
        lead = ""
        if sub:
            lead = (
                f'      <p class="sec-lead">Looking for the product itself? '
                f'<a href="{sub}">{heading}</a>.</p>\n'
            )
        li = "\n".join(
            '        <li><a href="/{slug}">{title}</a>{d}</li>'.format(
                slug=html.escape(s),
                title=html.escape(t),
                d=(f'<span class="d">{html.escape(d)}</span>' if d else ""),
            )
            for s, t, d in items
        )
        parts.append(
            f'    <section id="{role.lower()}">\n'
            f'      <h2>{heading} <span class="count">{len(items)}</span></h2>\n'
            f"{lead}"
            f"      <ul>\n{li}\n      </ul>\n"
            f"    </section>"
        )

    nav = " · ".join(
        f'<a href="#{r.lower()}">{html.escape(SECTION_TITLE.get(r, r))}</a>'
        for r in SECTION_ORDER
        if groups.get(r)
    )

    # Organization is a bare @id REFERENCE to the single MAS org node on
    # office.mulkernai.com. Do NOT declare name/url/logo/sameAs here: this host
    # previously declared a SECOND organisation (LocalBusiness,
    # @id=pages.mulkernai.com/#organization) and that split is what we are
    # undoing. No `logo` anywhere -- there is no real logo asset in the estate
    # (pages.mulkernai.com/assets/logo.png is a 6-byte stub, not an image).
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Guides and resources",
        "url": "https://pages.mulkernai.com/",
        "description": (
            "Guides on agentic AI fractional CFO, CMO, COO and CEO services "
            "from Mulkern AI Systems."
        ),
        "publisher": {"@id": "https://office.mulkernai.com/#org"},
        "isPartOf": {"@id": "https://office.mulkernai.com/#org"},
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Guides and resources | Mulkern AI Systems</title>
<meta name="description" content="Guides on agentic AI fractional CFO, CMO, COO and CEO services from Mulkern AI Systems.">
<link rel="canonical" href="https://pages.mulkernai.com/">
<script type="application/ld+json">{json.dumps(ld, indent=2)}</script>
<style>
:root{{--ac:#2563eb;--bg:#fff;--surf:#f8f9fa;--border:#e9ecef;--text:#1a1a2e;--muted:#6c757d;--r:10px}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
     background:var(--bg);color:var(--text);line-height:1.6}}
header{{border-bottom:1px solid var(--border);padding:18px 24px;display:flex;gap:16px;
       align-items:center;justify-content:space-between;flex-wrap:wrap}}
.logo-text{{font-weight:700;font-size:1.05rem;letter-spacing:-.01em}}
header a{{color:var(--text);text-decoration:none;font-weight:600;font-size:.9rem}}
main{{max-width:940px;margin:0 auto;padding:44px 24px 88px}}
h1{{font-size:2.05rem;line-height:1.2;margin:0 0 12px;letter-spacing:-.02em}}
.intro{{color:var(--muted);margin:0 0 26px;max-width:62ch}}
.jump{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);
      padding:13px 16px;margin:0 0 40px;font-size:.9rem}}
.jump a{{color:var(--ac);text-decoration:none}}
section{{margin:0 0 44px;scroll-margin-top:20px}}
h2{{font-size:1.28rem;margin:0 0 6px;letter-spacing:-.01em}}
.count{{color:var(--muted);font-weight:400;font-size:.9rem}}
.sec-lead{{margin:0 0 14px;font-size:.9rem;color:var(--muted)}}
.sec-lead a{{color:var(--ac)}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:9px}}
li{{border:1px solid var(--border);border-radius:var(--r);padding:12px 14px}}
li a{{color:var(--text);text-decoration:none;font-weight:600;font-size:.95rem}}
li a:hover{{color:var(--ac)}}
.d{{display:block;color:var(--muted);font-weight:400;font-size:.86rem;margin-top:3px}}
footer{{border-top:1px solid var(--border);padding:22px 24px;text-align:center;
       color:var(--muted);font-size:.85rem}}
footer a{{color:var(--muted)}}
@media(min-width:760px){{ul{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<header>
  <span class="logo-text">Mulkern AI Systems</span>
  <a href="https://office.mulkernai.com">Visit Mulkern AI Systems &rarr;</a>
</header>
<main>
  <h1>Guides and resources</h1>
  <p class="intro">Practical guides on agentic AI for finance, marketing, operations and
     executive leadership &mdash; covering {shown} topics across industries, company stages
     and regions.</p>
  <nav class="jump">Jump to: {nav}</nav>
{chr(10).join(parts)}
</main>
<footer>
  <span>&copy; 2026 Mulkern AI Systems &middot;
  <a href="https://office.mulkernai.com">About</a> &middot;
  <a href="https://office.mulkernai.com/privacy/">Privacy</a></span>
</footer>
</body>
</html>
"""


def main():
    pages = discover_pages()
    out = build(pages)
    held = collections.Counter(
        classify(s) for s, _, _ in pages if classify(s) in HELD_BACK
    )
    listed = out.count('<li><a href="/')
    print(f"discovered {len(pages)} pages, listed {listed}")
    if held:
        print(f"held back (not listed): {dict(held)}")
    if "--check" in sys.argv:
        print(out[:600])
        return
    path = os.path.join(REPO, "index.html")
    open(path, "w", encoding="utf-8").write(out)
    print(f"wrote {path} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
