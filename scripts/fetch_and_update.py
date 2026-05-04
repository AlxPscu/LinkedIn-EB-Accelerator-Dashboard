#!/usr/bin/env python3
"""
Nawy LinkedIn EB Dashboard — Daily Auto-Update Script
======================================================
Fetches post analytics from the LinkedIn API and updates index.html in-place.
Runs via GitHub Actions on a daily schedule, or can be triggered manually.

What gets auto-updated:
  ✓ KPI totals (Impressions, Reach, Followers, Reposts)
  ✓ Impressions bar chart
  ✓ Followers Gained bar chart
  ✓ Reactions & Reposts bar chart
  ✓ Posts tracked legend
  ✓ Data table (all numeric columns)
  ✓ Header post count + day counter
  ✓ i-meta analysis line
  ✓ Footer date

What still requires manual screenshot update:
  ✗ followers_gained per post  (LinkedIn API doesn't expose per-post follower attribution)
  ✗ page_views per post        (LinkedIn API doesn't expose per-post page view attribution)
  ✗ Video Viewer Demographics  (demographic breakdown only in Analytics UI)
  ✗ Insights section           (AI-authored, updated by Claude from screenshots)

Env vars required (set as GitHub Secrets):
  LINKEDIN_ACCESS_TOKEN  — OAuth bearer token with r_organization_social scope
  LINKEDIN_ORG_ID        — Numeric organisation ID (e.g. 12345678)
"""

import json
import os
import re
import sys
from datetime import date, datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' not installed. Run: pip install requests")

# ── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(SCRIPT_DIR)
REGISTRY     = os.path.join(SCRIPT_DIR, 'post_registry.json')
DASHBOARD    = os.path.join(ROOT_DIR, 'index.html')

# ── LinkedIn API ─────────────────────────────────────────────────────────────
TOKEN        = os.environ.get('LINKEDIN_ACCESS_TOKEN', '')
ORG_ID_RAW   = os.environ.get('LINKEDIN_ORG_ID', '')
API_BASE     = 'https://api.linkedin.com/rest'
LI_VERSION   = '202401'

CAMPAIGN_START = date(2026, 4, 26)
CAMPAIGN_END   = date(2026, 5, 29)
CAMPAIGN_DAYS  = 34


# ── LinkedIn API helpers ─────────────────────────────────────────────────────

def api_headers():
    return {
        'Authorization': f'Bearer {TOKEN}',
        'LinkedIn-Version': LI_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }


def fetch_post_stats(org_urn, post_urns):
    """
    Call GET /rest/organizationalEntityShareStatistics for a list of post URNs.
    Returns dict: { urn -> { impressions, reach, clicks, reactions,
                              comments, reposts, eng_rate } }

    Fields NOT available via this endpoint (must be updated manually):
      followers_gained, page_views, video demographics
    """
    if not TOKEN:
        print("⚠️  LINKEDIN_ACCESS_TOKEN not set — skipping API fetch, using registry values")
        return {}

    # Filter out placeholder URNs
    real_urns = [u for u in post_urns if not u.startswith('FILL_IN')]
    if not real_urns:
        print("⚠️  No valid URNs found in registry — add post URNs to scripts/post_registry.json")
        return {}

    params = {'q': 'organizationalEntity', 'organizationalEntity': org_urn}
    for i, urn in enumerate(real_urns):
        params[f'shares[{i}]'] = urn

    print(f"→ Calling LinkedIn API for {len(real_urns)} post(s)…")
    try:
        resp = requests.get(
            f'{API_BASE}/organizationalEntityShareStatistics',
            headers=api_headers(),
            params=params,
            timeout=30
        )
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return {}

    if resp.status_code == 401:
        print("❌ LinkedIn API 401 Unauthorized — access token is expired or invalid")
        print("   Renew it following the steps in README_AUTOMATION.md")
        return {}
    if resp.status_code == 403:
        print("❌ LinkedIn API 403 Forbidden — token is missing r_organization_social scope")
        return {}
    if not resp.ok:
        print(f"❌ LinkedIn API error {resp.status_code}: {resp.text[:300]}")
        return {}

    result = {}
    for elem in resp.json().get('elements', []):
        urn  = elem.get('share') or elem.get('ugcPost', '')
        ts   = elem.get('totalShareStatistics', {})
        impressions = ts.get('impressionCount', 0)
        reach       = ts.get('uniqueImpressionsCount', 0)
        clicks      = ts.get('clickCount', 0)
        reactions   = ts.get('likeCount', 0)
        comments    = ts.get('commentCount', 0)
        reposts     = ts.get('shareCount', 0)
        eng_raw     = float(ts.get('engagement', 0))
        eng_rate    = round(eng_raw * 100, 1)
        ctr         = round(clicks / impressions * 100, 1) if impressions else 0.0

        result[urn] = {
            'impressions': impressions,
            'reach':       reach,
            'clicks':      clicks,
            'reactions':   reactions,
            'comments':    comments,
            'reposts':     reposts,
            'eng_rate':    eng_rate,
            'ctr':         ctr,
        }

    print(f"✓ Received fresh stats for {len(result)} post(s)")
    return result


# ── Number formatting ────────────────────────────────────────────────────────

def fmt(n):
    """1,234 format"""
    return f"{int(n):,}"

def fmt_k(n):
    """16.6K format for bar chart labels"""
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(int(n))

def bar_h(val, max_val, floor=4):
    """Bar height as % of chart area, with a minimum floor so bars stay visible"""
    if max_val == 0:
        return floor
    return max(floor, round(val / max_val * 100, 1))


# ── HTML section builders ────────────────────────────────────────────────────

def build_kpis(posts):
    total_impr    = sum(p['metrics']['impressions']     for p in posts)
    total_reach   = sum(p['metrics']['reach']           for p in posts)
    total_follow  = sum(p['metrics']['followers_gained'] for p in posts)
    total_reposts = sum(p['metrics']['reposts']         for p in posts)

    dates = [p['date'] for p in posts]
    if len(dates) > 1:
        first_parts = dates[0].rsplit(' ', 1)
        last_parts  = dates[-1].rsplit(' ', 1)
        span = f"{dates[0]}–{last_parts[1]}" if first_parts[0] == last_parts[0] else f"{dates[0]}–{dates[-1]}"
    else:
        span = dates[0]

    return (
        f'  <div class="kpi"><div class="kpi-l">Total Impressions</div>'
        f'<div class="kpi-v">{fmt(total_impr)}</div>'
        f'<div class="kpi-s">{span}</div></div>\n'

        f'  <div class="kpi"><div class="kpi-l">Total Reach</div>'
        f'<div class="kpi-v">{fmt(total_reach)}</div>'
        f'<div class="kpi-s">unique members</div></div>\n'

        f'  <div class="kpi"><div class="kpi-l">Followers Gained</div>'
        f'<div class="kpi-v">{total_follow}</div>'
        f'<div class="kpi-s">new followers</div></div>\n'

        f'  <div class="kpi"><div class="kpi-l">Total Reposts</div>'
        f'<div class="kpi-v">{total_reposts}</div>'
        f'<div class="kpi-s">organic shares</div></div>'
    )


def build_charts(posts):
    # ── Chart 1: Impressions ──────────────────────────────────────────────
    impr_vals = [p['metrics']['impressions'] for p in posts]
    max_impr  = max(impr_vals) if impr_vals else 1

    impr_bars = ''
    for p, v in zip(posts, impr_vals):
        h    = bar_h(v, max_impr)
        bg   = p['color'] if v == max_impr else '#D7CFC7'
        impr_bars += (
            f'      <div class="bar-col">'
            f'<div class="bar-val">{fmt_k(v)}</div>'
            f'<div class="bar" style="height:{h}%;background:{bg};width:100%;"></div>'
            f'<span class="bar-lbl">{p["date"]}</span></div>\n'
        )

    # ── Chart 2: Followers Gained ─────────────────────────────────────────
    fol_vals = [p['metrics']['followers_gained'] for p in posts]
    max_fol  = max(fol_vals) if fol_vals else 1

    fol_bars = ''
    for p, v in zip(posts, fol_vals):
        h  = bar_h(v, max_fol)
        bg = '#44D580' if v == max_fol else '#C8F5DC'
        fol_bars += (
            f'      <div class="bar-col">'
            f'<div class="bar-val">{v}</div>'
            f'<div class="bar" style="height:{h}%;background:{bg};width:100%;"></div>'
            f'<span class="bar-lbl">{p["date"]}</span></div>\n'
        )

    # ── Chart 3: Reactions & Reposts ──────────────────────────────────────
    react_vals  = [p['metrics']['reactions'] for p in posts]
    repost_vals = [p['metrics']['reposts']   for p in posts]
    max_react   = max(react_vals)  if react_vals  else 1
    max_repost  = max(repost_vals) if repost_vals else 1

    rr_bars = ''
    for p, r, rp in zip(posts, react_vals, repost_vals):
        rh  = bar_h(r,  max_react)
        rph = bar_h(rp, max_repost)
        rr_bars += (
            f'      <div class="bar-col">\n'
            f'        <div class="bar-group" style="height:100%;align-items:flex-end;">\n'
            f'          <div class="bar" style="height:{rh}%;background:#FF5E00;"></div>\n'
            f'          <div class="bar" style="height:{rph}%;background:#015C9A;"></div>\n'
            f'        </div>\n'
            f'        <span class="bar-lbl">{p["date"]}</span>\n'
            f'      </div>\n'
        )

    return (
        f'  <div class="card">\n'
        f'    <div class="card-l">Impressions by Post</div>\n'
        f'    <div class="bar-chart">\n'
        f'{impr_bars}'
        f'    </div>\n'
        f'  </div>\n\n'

        f'  <div class="card">\n'
        f'    <div class="card-l">Followers Gained</div>\n'
        f'    <div class="bar-chart">\n'
        f'{fol_bars}'
        f'    </div>\n'
        f'  </div>\n\n'

        f'  <div class="card">\n'
        f'    <div class="card-l">Reactions &amp; Reposts</div>\n'
        f'    <div class="bar-chart">\n'
        f'{rr_bars}'
        f'    </div>\n'
        f'    <div class="leg-row">\n'
        f'      <div class="leg-i"><div class="leg-d" style="background:#FF5E00;"></div>Reactions</div>\n'
        f'      <div class="leg-i"><div class="leg-d" style="background:#015C9A;"></div>Reposts</div>\n'
        f'    </div>\n'
        f'  </div>'
    )


def build_postleg(posts):
    rows = ''
    for p in posts:
        rows += (
            f'  <div class="post-item">'
            f'<div class="dot" style="background:{p["color"]};"></div>'
            f'<span class="post-date">{p["date"]}</span>'
            f'<span class="post-cap">{p["caption"]}</span>'
            f'<span class="tag" style="background:{p["tag_bg"]};color:{p["tag_color"]};">'
            f'{p["type"]}</span></div>\n'
        )
    return rows.rstrip()


def build_table_rows(posts):
    rows = ''
    for p in posts:
        m  = p['metrics']
        is_carousel = p.get('type') == 'Carousel'
        eng_str = f'{m["eng_rate"]}%{"*" if is_carousel else ""}'

        rows += (
            f'      <tr>'
            f'<td class="td-dt">{p["date"]}</td>'
            f'<td class="td-cap">{p["caption"]}</td>'
            f'<td><span class="tag" style="background:{p["tag_bg"]};color:{p["tag_color"]};">'
            f'{p["type"]}</span></td>'
            f'<td class="td-b">{fmt(m["impressions"])}</td>'
            f'<td>{fmt(m["reach"])}</td>'
            f'<td class="td-eng">{eng_str}</td>'
            f'<td>{fmt(m["clicks"])}</td>'
            f'<td class="td-m">{m["ctr"]}%</td>'
            f'<td>{m["reactions"]}</td>'
            f'<td>{m["comments"]}</td>'
            f'<td class="td-rep">{m["reposts"]}</td>'
            f'<td class="td-fol">{m["followers_gained"]}</td>'
            f'<td class="td-m">{m["page_views"]}</td>'
            f'</tr>\n'
        )
    return rows.rstrip()


# ── Section replacement ───────────────────────────────────────────────────────

def replace_section(html, marker, new_content):
    """Replace content between <!-- AUTO_{marker}_START --> and <!-- AUTO_{marker}_END -->"""
    pattern = rf'(<!-- AUTO_{marker}_START -->)(.*?)(<!-- AUTO_{marker}_END -->)'
    replacement = rf'\1\n{new_content}\n\3'
    new_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if n == 0:
        print(f"  ⚠️  Marker AUTO_{marker} not found in HTML — section skipped")
    return new_html


def update_header(html, post_count, today):
    """Update 'N posts tracked' and 'Day X of 34' badge in header"""
    # Posts tracked count
    html = re.sub(
        r'(\d+) posts tracked',
        f'{post_count} posts tracked',
        html
    )
    # Day counter badge
    elapsed = max(1, (today - CAMPAIGN_START).days + 1)
    remaining = max(0, (CAMPAIGN_END - today).days)
    html = re.sub(
        r'Day \d+ of \d+ · \d+ days remaining',
        f'Day {elapsed} of {CAMPAIGN_DAYS} · {remaining} days remaining',
        html
    )
    return html


def update_imeta(html, post_count, today, posts):
    """Update the analysis date line below the Insights header"""
    dates = [p['date'] for p in posts]
    if len(dates) > 1:
        first_parts = dates[0].rsplit(' ', 1)
        last_parts  = dates[-1].rsplit(' ', 1)
        span = f"{dates[0]}–{last_parts[1]}" if first_parts[0] == last_parts[0] else f"{dates[0]}–{dates[-1]}"
    else:
        span = dates[0]
    today_str = today.strftime('%-d %b %Y').replace('  ', ' ')  # e.g. "4 May 2026"

    new_meta = (
        f'<div class="i-meta">Analysis · {today_str} · '
        f'{post_count} post{"s" if post_count != 1 else ""} · {span}</div>'
    )
    html = re.sub(
        r'<div class="i-meta">.*?</div>',
        new_meta,
        html
    )
    return html


def update_footer_date(html, today):
    today_str = today.strftime('%-d %b %Y').replace('  ', ' ')
    html = re.sub(
        r'Updated [A-Za-z0-9 ,]+',
        f'Updated {today_str}',
        html
    )
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"\n{'='*60}")
    print(f"  Nawy LinkedIn EB Dashboard — Auto-Update")
    print(f"  {today.strftime('%A, %d %B %Y')}")
    print(f"{'='*60}\n")

    # Load registry
    with open(REGISTRY, 'r') as f:
        registry = json.load(f)

    posts_cfg = registry['posts']
    print(f"→ Registry has {len(posts_cfg)} post(s)")

    # Build org URN
    org_urn = f"urn:li:organization:{ORG_ID_RAW}" if ORG_ID_RAW else ''

    # Fetch fresh stats from LinkedIn API
    post_urns  = [p['urn'] for p in posts_cfg]
    fresh_data = fetch_post_stats(org_urn, post_urns)

    # Merge: apply fresh API data over registry values where available
    changed = False
    for post in posts_cfg:
        api = fresh_data.get(post['urn'])
        if not api:
            continue
        m = post['metrics']
        # Fields the API provides
        api_fields = ['impressions', 'reach', 'clicks', 'reactions',
                      'comments', 'reposts', 'eng_rate', 'ctr']
        for field in api_fields:
            if field in api and m.get(field) != api[field]:
                print(f"  {post['date']} {field}: {m.get(field)} → {api[field]}")
                m[field] = api[field]
                changed = True
        # followers_gained and page_views intentionally NOT overwritten here

    # Save updated registry
    with open(REGISTRY, 'w') as f:
        json.dump(registry, f, indent=2)

    if not changed and fresh_data:
        print("✓ No metric changes detected — dashboard is already current")
    elif changed:
        print(f"✓ Updated {sum(1 for p in posts_cfg if p['urn'] in fresh_data)} post(s)")

    # Always write the HTML (date, day counter always change)
    print("\n→ Updating index.html…")
    with open(DASHBOARD, 'r', encoding='utf-8') as f:
        html = f.read()

    html = replace_section(html, 'KPI',      build_kpis(posts_cfg))
    html = replace_section(html, 'CHARTS',   build_charts(posts_cfg))
    html = replace_section(html, 'POSTLEG',  build_postleg(posts_cfg))
    html = replace_section(html, 'TABLE',    build_table_rows(posts_cfg))
    html = update_header(html, len(posts_cfg), today)
    html = update_imeta(html, len(posts_cfg), today, posts_cfg)
    html = update_footer_date(html, today)

    with open(DASHBOARD, 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ index.html updated")
    print("\n  Dashboard will go live at:")
    print("  https://alxpscu.github.io/LinkedIn-EB-Accelerator-Dashboard/\n")


if __name__ == '__main__':
    main()
