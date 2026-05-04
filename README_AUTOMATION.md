# Automation Setup Guide
## Nawy LinkedIn EB Accelerator Dashboard

---

## What this does

A GitHub Actions workflow runs at **10:00 AM Cairo time every day** and:

1. Reads `scripts/post_registry.json` for the list of tracked posts
2. Calls the LinkedIn API to pull fresh analytics for each post
3. Updates `index.html` (KPIs, charts, table, counters, date)
4. Commits and pushes — the dashboard at the live URL updates within ~60 seconds

**No manual action needed once set up.**

---

## One-time setup (15 minutes)

### Step 1 — Get your LinkedIn Organization ID

1. Go to `linkedin.com/company/nawy`
2. Click **Admin tools → Super admin view**
3. Look at the URL: `linkedin.com/company/12345678/admin/` — the number is your Org ID
4. Copy the number only (e.g. `12345678`)

### Step 2 — Get a LinkedIn API Access Token

You need a token with `r_organization_social` scope. Two ways:

**Option A — LinkedIn Developer App (recommended, lasts 60 days)**

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and create an app
2. Under **Products**, request access to **Marketing Developer Platform**
3. Once approved, go to the **Auth** tab → **OAuth 2.0 tools**
4. Generate a token with these scopes: `r_organization_social`, `rw_organization_admin`
5. Copy the access token

**Option B — Use LinkedIn's token generator (quick test only)**

1. Go to [linkedin.com/developers/tools/oauth](https://www.linkedin.com/developers/tools/oauth)
2. Select your app, tick `r_organization_social`, generate
3. Token lasts 60 days

### Step 3 — Add secrets to GitHub

1. Go to `github.com/AlxPscu/LinkedIn-EB-Accelerator-Dashboard`
2. **Settings → Secrets and variables → Actions → New repository secret**
3. Add these two secrets:

| Secret name | Value |
|-------------|-------|
| `LINKEDIN_ACCESS_TOKEN` | The token from Step 2 |
| `LINKEDIN_ORG_ID` | The number from Step 1 (e.g. `12345678`) |

### Step 4 — Add post URNs to the registry

For each tracked post, find its LinkedIn URN:

1. Open the post on LinkedIn
2. Click the **three-dot menu (⋯)** → **Copy link**
3. The link looks like: `https://www.linkedin.com/feed/update/urn:li:ugcPost:7123456789012345678/`
4. The URN is `urn:li:ugcPost:7123456789012345678`

Open `scripts/post_registry.json` and replace `"FILL_IN_URN_FOR_APR26"` etc. with the real URNs.

### Step 5 — Trigger the first run

Go to **Actions → Daily LinkedIn Analytics Update → Run workflow** to test it immediately.

---

## Adding a new post

When a new EB post is published:

1. Open `scripts/post_registry.json` (edit directly on GitHub or send to Claude)
2. Add a new entry to the `posts` array:

```json
{
  "urn": "urn:li:ugcPost:XXXXXXXXXXXXXXXX",
  "date": "May 5",
  "date_iso": "2026-05-05",
  "caption": "First line of the post caption",
  "type": "Video",
  "color": "#FF5E00",
  "tag_bg": "#FFF2EB",
  "tag_color": "#FF5E00",
  "metrics": {
    "impressions": 0,
    "reach": 0,
    "clicks": 0,
    "reactions": 0,
    "comments": 0,
    "reposts": 0,
    "eng_rate": 0,
    "ctr": 0,
    "followers_gained": 0,
    "page_views": 0
  }
}
```

**Color guide by post type:**

| Type | color | tag_bg | tag_color |
|------|-------|--------|-----------|
| Video | `#FF5E00` | `#FFF2EB` | `#FF5E00` |
| Carousel | `#015C9A` | `#E5F1F9` | `#015C9A` |
| Ambassador | `#5ECCC0` | `#E8F9F8` | `#2E9D94` |
| Image | `#8B5CF6` | `#EDE9FE` | `#7C3AED` |

The automation picks it up on the next daily run. Or trigger manually from the Actions tab.

---

## Renewing the LinkedIn token (every 60 days)

1. Generate a new token following Step 2 above
2. Go to **Settings → Secrets → LINKEDIN_ACCESS_TOKEN → Update**
3. Paste the new token and save

Set a reminder in your calendar for 55 days from when you first set it up.

---

## What the automation does NOT update (still manual)

These require a screenshot and the Claude workflow:

- **Followers gained per post** — LinkedIn API doesn't expose per-post follower attribution
- **Page views per post** — same limitation
- **Video viewer demographics** — only shown in the LinkedIn Analytics UI
- **Insights & Recommendations section** — AI-authored by Claude from screenshots

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Action fails with `401 Unauthorized` | Token expired | Renew token (Step 2) and update Secret |
| Action fails with `403 Forbidden` | Wrong scope | Regenerate token with `r_organization_social` scope |
| Action runs but metrics don't change | URNs not set | Add real URNs to `post_registry.json` |
| Action doesn't run at 10 AM | GitHub Actions clock uses UTC | Workflow runs at 08:00 UTC = 10:00 Cairo time |

---

## Manual trigger

Any team member with repo access can trigger an update at any time:  
**GitHub → Actions → Daily LinkedIn Analytics Update → Run workflow → Run workflow**
