# LeoQuiz Pro Upgrade — Design Spec

## Overview

Transform LeoQuiz from a single-short-per-day pipeline into a **multi-format, multi-platform content engine** matching the top kids quiz channels (Quiz Kingdom, Quiz Blitz, Monkey Quiz). Five upgrades:

1. **Daily Long-form Generator** — 60 rounds, 16:9, ~10 minutes
2. **Weekly Mega Quiz Generator** — 100-120 rounds, 16:9, 15-20 minutes
3. **Multi-platform Upload** — YouTube + TikTok + Instagram Reels + Facebook Reels
4. **A/B Thumbnail Testing** — 3 variants per video, track CTR, learn best style
5. **Analytics Dashboard** — cross-platform stats, charts, category performance

## Content Strategy (Matching Top Performers)

### Daily Output (1 trigger → 2 videos)

| Format | Rounds | Round Duration | Timer | Total Length | Aspect Ratio |
|--------|--------|---------------|-------|-------------|-------------|
| Short | 6 | 10s | 3s countdown | ~66s | 9:16 vertical |
| Long-form | 60 | 8s | 5s countdown | ~10 min | 16:9 landscape |

Both are **fresh content** for the same category (e.g., Monday = animals → 6-round short + 60-round long-form, all animals). NOT a compilation of shorts. Shorts are 6 rounds (66s) to meet TikTok's 1-minute minimum for Creator Rewards Program monetization while staying under YouTube Shorts' 3-minute cap and Instagram's 90-second Reels limit.

### Weekly Output (separate trigger)

| Format | Rounds | Round Duration | Timer | Total Length | Aspect Ratio |
|--------|--------|---------------|-------|-------------|-------------|
| Mega Quiz | 100-120 | 6-8s | 5s countdown | 15-20 min | 16:9 landscape |

The mega quiz is either "mixed" (all categories) or the week's best-performing category. Triggered separately on Sundays.

### Platform Distribution

Every video gets posted to all 4 platforms. Same video file, different metadata.

| | YouTube | TikTok | Instagram | Facebook |
|---|---|---|---|---|
| Daily Short (9:16) | Shorts | Post | Reel | Reel |
| Daily Long-form (16:9) | Video | Post | Reel | Video |
| Weekly Mega (16:9) | Video | Post | Reel | Video |

**Total uploads: 8/day + 4/week = ~60 uploads/week across all platforms.**

---

## Feature 1: Long-form & Mega Quiz Generator

### Architecture

Create a new `longform_assembler.py` module (separate from `video_assembler.py` which handles 9:16 shorts). The long-form renderer shares quiz content generation, image generation, silhouette extraction, and narration with the short pipeline, but has its own:

- **16:9 landscape layout** (1920×1080)
- **Faster round pacing** (8s per round for daily, 6-8s for mega)
- **Section title cards** between category groups (e.g., "🦁 ANIMALS ROUND!")
- **Running score counter** visible throughout (top-right corner)
- **Difficulty progression** — rounds ordered Easy → Medium → Hard
- **Progress indicator** — "Question 23 / 60" displayed
- **Section transitions** — category-themed wipe between sections

### Long-form Round Timing (8 seconds per round)

| Phase | Start | Duration | What happens |
|-------|-------|----------|-------------|
| Question + silhouette | 0.0s | 0.5s | Silhouette slides in, question text appears |
| Timer countdown | 0.5s | 5.0s | 5-second visible timer bar, tick SFX |
| Reveal | 5.5s | 1.0s | Answer image reveals, ding + confetti |
| Fun fact | 6.5s | 1.5s | Quick fun fact overlay |

### Mega Quiz Round Timing (7 seconds per round)

Same structure as long-form but compressed:

| Phase | Start | Duration | What happens |
|-------|-------|----------|-------------|
| Question + silhouette | 0.0s | 0.3s | Fast slide-in |
| Timer countdown | 0.3s | 4.5s | 4.5-second timer |
| Reveal | 4.8s | 0.8s | Quick reveal |
| Fun fact | 5.6s | 1.4s | Brief fact |

### Long-form Layout (16:9)

```
┌─────────────────────────────────────────────────┐
│  GUESS THE ANIMAL! 🦁          Score: 15/23     │
│                                Q 23/60          │
│                                                  │
│         ┌──────────────────┐                     │
│         │                  │                     │
│         │   SILHOUETTE     │       LEO           │
│         │   (centered)     │       MASCOT        │
│         │                  │                     │
│         └──────────────────┘                     │
│                                                  │
│     "Which animal has the longest neck?"          │
│                                                  │
│  ██████████████████░░░░░  5s                     │
│  ● ● ● ● ○ ○ ○ ○ ○ ○  progress dots             │
└─────────────────────────────────────────────────┘
```

### Section Title Card (shown between category groups in mega quiz)

```
┌─────────────────────────────────────────────────┐
│                                                  │
│              🦕 DINOSAUR ROUND! 🦕               │
│                                                  │
│              Questions 21-40                     │
│              Can you guess them all?             │
│                                                  │
└─────────────────────────────────────────────────┘
```

Displayed for 2 seconds with category gradient background, zoom-in animation, and category-specific BGM preview.

### Long-form Intro (3 seconds)

- Leo mascot waving + channel name
- "60 QUESTIONS!" or "100 QUESTIONS!" hype text with bounce animation
- Category badge (or "MEGA MIX" for mega quiz)
- Energetic jingle

### Long-form Outro (5 seconds)

- Final score display: "You got 45 / 60!" with star rating
- Leo mascot celebrating (excited pose)
- Subscribe + Like CTA with animated bell icon
- "New quiz every day!" text
- Outro jingle

### Pipeline Integration

`main.py` gets a new `video_format` parameter:

```python
def run_pipeline(category=None, num_rounds=None, video_format="short", output_dir=None):
```

- `video_format="short"` → 6 rounds, 9:16, ~66s (TikTok monetization eligible)
- `video_format="long"` → 60 rounds, 16:9, ~10 min
- `video_format="mega"` → 100 rounds, 16:9, ~15-20 min

When the dashboard triggers "daily generation", it fires TWO GitHub Actions runs: one short + one long-form, same category. The mega is a separate weekly trigger.

### Config Additions

```python
# Long-form timing (8s per round)
LONGFORM_ROUND_DURATION = 8.0
LONGFORM_ROUNDS = 60
LONGFORM_TIMER_SECONDS = 5
LONGFORM_INTRO_DURATION = 3.0
LONGFORM_OUTRO_DURATION = 5.0
LONGFORM_SECTION_CARD_DURATION = 2.0

# Mega quiz timing (7s per round)
MEGA_ROUND_DURATION = 7.0
MEGA_ROUNDS = 100
MEGA_TIMER_SECONDS = 4
MEGA_INTRO_DURATION = 4.0
MEGA_OUTRO_DURATION = 6.0
```

---

## Feature 2: Multi-Platform Upload

### Platform APIs

| Platform | API | Auth Method | Upload Method |
|----------|-----|-------------|--------------|
| YouTube | Data API v3 | OAuth 2.0 (existing) | Resumable upload |
| TikTok | Content Posting API v2 | OAuth 2.0 | Direct post (≤50MB) or chunk upload |
| Instagram | Graph API (Reels) | Facebook OAuth (long-lived token) | URL-based publish (video must be publicly accessible) |
| Facebook | Graph API (Reels/Video) | Facebook OAuth (Page token) | Resumable upload |

### OAuth Flows

Each platform follows the same connect-once pattern already built for YouTube:

1. User clicks "Connect [Platform]" in dashboard settings
2. Redirected to platform OAuth consent screen
3. Callback saves refresh_token + access_token to Vercel Blob as JSON
4. Token auto-refreshes before expiry on each upload
5. Dashboard shows connected status + account name

**Token storage pattern** (Vercel Blob, same as YouTube):

```
tokens/youtube.json    → { refresh_token, access_token, expires_at, account_name }
tokens/tiktok.json     → { refresh_token, access_token, expires_at, account_name }
tokens/instagram.json  → { access_token, expires_at, account_name, ig_user_id }
tokens/facebook.json   → { page_access_token, expires_at, page_name, page_id }
```

Instagram and Facebook share the same Meta developer app but store separate tokens. Instagram uses long-lived user tokens (60 days, auto-refreshable). Facebook uses Page tokens (non-expiring once obtained from long-lived user token).

### Upload Flow

```
Video approved in dashboard
  → POST /api/videos/[id]/upload
    → For each connected platform:
        1. Refresh token if expired
        2. Upload video file
        3. Set platform-specific metadata (title, description, tags/hashtags)
        4. Set "Made for Kids" / COPPA flag
        5. Record upload URL + timestamp in DB
        6. Log activity
    → All uploads run in parallel (Promise.allSettled)
    → Partial failures don't block other platforms
```

### Pipeline Changes (`uploader.py`)

Complete the existing `upload_tiktok()` stub. Add `upload_instagram()` and `upload_facebook()`. Each function:

- Takes `video_path`, `metadata_path`, `token_path` (Vercel Blob JSON)
- Handles token refresh internally
- Returns platform URL on success, empty string on failure
- Sets COPPA/Made-for-Kids flag (required for kids content)

### Metadata Generation (`metadata.py`)

Add two new platform generators alongside existing YouTube and TikTok:

```python
def generate_metadata(quiz_pack, platform):
    # platform: "youtube" | "tiktok" | "instagram" | "facebook"
```

**Instagram metadata:**
- Caption: engagement-style ("Can YOU guess all 5? 🤔 Comment your score!")
- Hashtags: max 30, mix of broad (#kidsgame #quiztime) and niche (#guesstheanimal)
- No tags field (IG doesn't support SEO tags)

**Facebook metadata:**
- Title: shareable format ("How Many Animals Can Your Kids Guess? 🦁")
- Description: parent-targeted ("Play along with your little ones!")
- No hashtags (FB algorithm doesn't weight them)

### Dashboard Changes

**Settings page additions:**
- "Connect TikTok" button + OAuth flow
- "Connect Instagram" button + OAuth flow (Meta Business Suite)
- "Connect Facebook Page" button + OAuth flow (same Meta app)
- Connection status indicator for each (green dot = connected)
- "Disconnect" button per platform

**Upload page:**
- Show which platforms are connected
- Upload progress per platform (uploading / success / failed)
- Platform URLs after upload (clickable links)

**Types update:**

```typescript
export type Platform = "youtube" | "tiktok" | "instagram" | "facebook" | "all";

export interface Video {
  // ... existing fields ...
  youtube_url: string | null;
  tiktok_url: string | null;
  instagram_url: string | null;
  facebook_url: string | null;
}
```

### Dashboard API Routes

New routes needed:

```
GET  /api/auth/tiktok          → Start TikTok OAuth
GET  /api/auth/tiktok/callback → Handle TikTok OAuth callback
GET  /api/auth/meta            → Start Meta OAuth (covers Instagram + Facebook)
GET  /api/auth/meta/callback   → Handle Meta OAuth callback
GET  /api/auth/status          → Return connection status for all platforms
POST /api/auth/disconnect      → Disconnect a specific platform (delete token)
GET  /api/tokens/tiktok        → Get/refresh TikTok token
GET  /api/tokens/meta          → Get/refresh Meta token
```

---

## Feature 3: A/B Thumbnail Testing

### Variant Generation

Generate 3 thumbnail variants per video, each with a distinct visual strategy:

**Variant A — "Split Reveal" (current design):**
- Diagonal split: silhouettes on left, one reveal on right
- "CAN YOU GUESS?" glow text header
- "6 ROUNDS!" badge

**Variant B — "Giant Mystery":**
- Single large silhouette centered (biggest possible)
- Giant "?" emoji overlaid on silhouette
- Bright yellow/red border for contrast
- "GUESS THE [CATEGORY]!" text at bottom
- No reveal shown (maximum curiosity)

**Variant C — "Grid Challenge":**
- 2×2 grid of 4 silhouettes
- Each silhouette has a number (1, 2, 3, 4)
- "HOW MANY CAN YOU GUESS?" header
- Leo mascot in corner pointing at grid
- Category color gradient background

### Storage

All 3 thumbnails stored in Vercel Blob alongside the video:

```
thumbnails/{video_id}_variant_a.png
thumbnails/{video_id}_variant_b.png
thumbnails/{video_id}_variant_c.png
```

### Upload Strategy

- YouTube: Upload Variant A by default (can be changed via YouTube Studio later)
- Track which variant was uploaded per platform per video
- Dashboard shows all 3 variants side-by-side in approval queue

### CTR Tracking

After 48 hours, pull YouTube Analytics thumbnail CTR for each video:

```python
# YouTube Analytics API
youtube_analytics.reports().query(
    ids="channel==MINE",
    startDate=upload_date,
    endDate=upload_date + 2_days,
    metrics="impressions,clicks,annotationClickThroughRate",
    filters=f"video=={video_id}"
)
```

Store CTR data in Turso:

```sql
CREATE TABLE IF NOT EXISTS thumbnail_tests (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    variant TEXT NOT NULL,          -- 'a', 'b', 'c'
    platform TEXT NOT NULL,         -- 'youtube'
    uploaded_at TEXT,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0.0,
    checked_at TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);
```

### Win Tracking

After enough data (10+ videos with CTR), calculate win rate per variant per category:

```sql
-- Which variant wins most often for animals?
SELECT variant, COUNT(*) as wins
FROM thumbnail_tests
WHERE video_id IN (SELECT id FROM videos WHERE category = 'animals')
  AND ctr = (
    SELECT MAX(ctr) FROM thumbnail_tests t2
    WHERE t2.video_id = thumbnail_tests.video_id
  )
GROUP BY variant
ORDER BY wins DESC;
```

Dashboard shows: "Variant B wins 65% of the time for Animals" — admin can then set a default variant preference per category.

### Pipeline Changes (`thumbnail.py`)

Add two new generator functions:

```python
def generate_thumbnail_variant_b(quiz_pack, silhouette_paths, output_path):
    """Giant mystery silhouette variant."""

def generate_thumbnail_variant_c(quiz_pack, silhouette_paths, output_path):
    """2x2 grid challenge variant."""
```

The main `generate_thumbnail()` becomes Variant A. A new wrapper generates all 3:

```python
def generate_all_thumbnails(quiz_pack, image_paths, silhouette_paths, output_dir):
    """Generate 3 A/B test thumbnail variants."""
    generate_thumbnail(quiz_pack, image_paths, silhouette_paths, output_dir / "thumb_a.png")
    generate_thumbnail_variant_b(quiz_pack, silhouette_paths, output_dir / "thumb_b.png")
    generate_thumbnail_variant_c(quiz_pack, silhouette_paths, output_dir / "thumb_c.png")
```

---

## Feature 4: Analytics Dashboard

### Data Collection

A daily cron job pulls stats from each connected platform's API and stores them in Turso.

**YouTube Data API v3 + Analytics API:**
- Views, watch time (minutes), likes, comments, shares
- Subscriber gain/loss
- Thumbnail impressions + CTR
- Traffic sources

**TikTok Business API:**
- Views, likes, comments, shares, saves
- Follower gain
- Average watch time

**Instagram Insights API:**
- Views (plays), likes, comments, saves, shares
- Reach, impressions
- Follower gain

**Facebook Insights API:**
- Views (3-second views + 1-minute views), likes, comments, shares
- Page follower gain
- Post reach

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS video_analytics (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_video_id TEXT,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    watch_time_minutes REAL DEFAULT 0.0,
    impressions INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0.0,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS channel_analytics (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    date TEXT NOT NULL,
    subscribers INTEGER DEFAULT 0,
    total_views INTEGER DEFAULT 0,
    new_videos INTEGER DEFAULT 0,
    fetched_at TEXT NOT NULL,
    UNIQUE(platform, date)
);
```

### Dashboard Page (`/analytics`)

**Overview Cards (top row):**
- Total views (all platforms, all time)
- Total subscribers/followers (per platform)
- Videos published this week
- Average CTR

**Charts:**

1. **Daily Views Trend** — line chart, last 30 days, one line per platform (color-coded)
2. **Category Performance** — bar chart comparing avg views per category
3. **Platform Comparison** — stacked bar showing views split across YouTube/TikTok/IG/FB
4. **Best Posting Times** — heatmap grid (day × hour) showing when views peak
5. **Top 10 Videos** — table with thumbnail, title, views, likes, platform

**Period Selector:** 7d | 30d | 90d | All Time

**Filters:** Platform filter (all / YouTube / TikTok / Instagram / Facebook), Category filter

### Dashboard API Routes

```
GET /api/analytics/overview     → Summary cards data
GET /api/analytics/views        → Daily views time series (query: period, platform)
GET /api/analytics/categories   → Category performance breakdown
GET /api/analytics/top-videos   → Top performing videos list
POST /api/analytics/refresh     → Manually trigger stats pull from all platforms
```

### Cron Job

Add to Vercel cron (`vercel.json`):

```json
{
  "crons": [
    { "path": "/api/cron/check-scheduled", "schedule": "*/5 * * * *" },
    { "path": "/api/cron/pull-analytics", "schedule": "0 6 * * *" }
  ]
}
```

Runs daily at 6 AM UTC. Pulls stats for all uploaded videos from the last 7 days (recent videos' stats change most), plus channel-level metrics.

---

## Feature 5: Dashboard Generate Page Updates

### Updated Generate Controls

The generate page currently has category selector + "Generate" button. Update to:

**Format selector:**
- Short only (9:16, 5 rounds, ~56s)
- Long-form only (16:9, 60 rounds, ~10 min)
- Mega quiz (16:9, 100 rounds, ~15-20 min)
- **Daily bundle (recommended)** — generates Short + Long-form simultaneously

**Category selector:** (existing, unchanged)

**Platform selector:**
- All connected platforms (default)
- Or pick specific platforms

**Trigger behavior:**
- "Daily bundle" fires 2 GitHub Actions workflow_dispatch: one `format=short`, one `format=long`
- "Mega quiz" fires 1 workflow_dispatch with `format=mega`
- Each run calls back to the dashboard webhook when complete

### Updated Scheduler

The schedule config gets a new field for long-form:

```sql
ALTER TABLE schedule_config ADD COLUMN generate_longform BOOLEAN DEFAULT 1;
ALTER TABLE schedule_config ADD COLUMN mega_day INTEGER DEFAULT 6;  -- Sunday
ALTER TABLE schedule_config ADD COLUMN mega_hour_utc INTEGER DEFAULT 10;
```

When `auto_enabled = true`:
- Daily cron triggers both short + long-form (if `generate_longform = true`)
- Weekly cron triggers mega quiz on `mega_day` at `mega_hour_utc`

---

## GitHub Actions Workflow Updates

The existing `generate-video.yml` workflow accepts `category` via workflow_dispatch. Add `format` input:

```yaml
on:
  workflow_dispatch:
    inputs:
      category:
        description: 'Quiz category'
        required: true
        type: choice
        options: [animals, dinosaurs, space, vehicles, fruits, flags]
      format:
        description: 'Video format'
        required: true
        type: choice
        options: [short, long, mega]
        default: short
      video_id:
        description: 'Dashboard video record ID'
        required: true
        type: string
```

The workflow calls:

```bash
python main.py --category ${{ inputs.category }} --format ${{ inputs.format }}
```

---

## File Map

### Pipeline (Python) — New Files

| File | Purpose |
|------|---------|
| `longform_assembler.py` | 16:9 landscape video renderer (section cards, score, progress) |
| `tests/test_longform_assembler.py` | Tests for long-form renderer |
| `tests/test_uploader.py` | Tests for multi-platform uploaders |

### Pipeline (Python) — Modified Files

| File | Changes |
|------|---------|
| `config.py` | Long-form + mega timing constants, platform configs |
| `main.py` | `video_format` parameter, dual output logic |
| `uploader.py` | Complete TikTok, add Instagram + Facebook uploaders |
| `metadata.py` | Instagram + Facebook metadata generators |
| `thumbnail.py` | Variant B + C generators, `generate_all_thumbnails()` |
| `compiler.py` | Remove or repurpose (mega quiz replaces weekly compilation) |
| `scheduler.py` | Daily short+long, weekly mega triggers |

### Dashboard (Next.js) — New Files

| File | Purpose |
|------|---------|
| `app/analytics/page.tsx` | Analytics dashboard page with charts |
| `app/api/analytics/overview/route.ts` | Analytics summary endpoint |
| `app/api/analytics/views/route.ts` | Daily views time series endpoint |
| `app/api/analytics/categories/route.ts` | Category performance endpoint |
| `app/api/analytics/top-videos/route.ts` | Top videos endpoint |
| `app/api/analytics/refresh/route.ts` | Manual analytics pull trigger |
| `app/api/cron/pull-analytics/route.ts` | Daily analytics cron job |
| `app/api/auth/tiktok/route.ts` | TikTok OAuth start |
| `app/api/auth/tiktok/callback/route.ts` | TikTok OAuth callback |
| `app/api/auth/meta/route.ts` | Meta OAuth start (IG + FB) |
| `app/api/auth/meta/callback/route.ts` | Meta OAuth callback |
| `app/api/tokens/tiktok/route.ts` | TikTok token management |
| `app/api/tokens/meta/route.ts` | Meta token management |
| `components/analytics-charts.tsx` | Chart components for analytics page |
| `components/platform-connect.tsx` | Platform connection UI component |

### Dashboard (Next.js) — Modified Files

| File | Changes |
|------|---------|
| `lib/types.ts` | Platform type expansion, analytics types, thumbnail test types |
| `lib/db.ts` | Analytics + thumbnail_tests queries |
| `lib/schema.sql` | New tables (video_analytics, channel_analytics, thumbnail_tests) |
| `lib/tokens.ts` | TikTok + Meta token refresh functions |
| `app/generate/page.tsx` | Format selector, daily bundle option |
| `app/settings/page.tsx` | TikTok/Instagram/Facebook connect buttons |
| `app/queue/page.tsx` | Show 3 thumbnail variants, platform upload status |
| `app/api/generate/route.ts` | Format param, dual workflow dispatch |
| `app/api/videos/[id]/upload/route.ts` | Multi-platform upload logic |
| `app/api/auth/status/route.ts` | Return all platform connection statuses |
| `app/api/auth/disconnect/route.ts` | Support disconnecting any platform |
| `vercel.json` | Add pull-analytics cron |

---

## Environment Variables (New)

### Pipeline (.env)

```
TIKTOK_ACCESS_TOKEN=       # Set by dashboard OAuth
INSTAGRAM_ACCESS_TOKEN=    # Set by dashboard OAuth
FACEBOOK_PAGE_TOKEN=       # Set by dashboard OAuth
FACEBOOK_PAGE_ID=          # Set by dashboard OAuth
```

### Dashboard (Vercel)

```
TIKTOK_CLIENT_KEY=         # From TikTok Developer Portal
TIKTOK_CLIENT_SECRET=      # From TikTok Developer Portal
META_APP_ID=               # From Meta Developer Console
META_APP_SECRET=           # From Meta Developer Console
```

YouTube credentials (existing): `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`

---

## Manual Setup Actions (User Must Do)

1. **TikTok Developer App** — Create app at developers.tiktok.com, request Content Posting API access, set redirect URI to `https://[dashboard-url]/api/auth/tiktok/callback`
2. **Meta Developer App** — Create app at developers.facebook.com, add Instagram Graph API + Facebook Login products, set redirect URI to `https://[dashboard-url]/api/auth/meta/callback`
3. **Facebook Page** — Create a Facebook Page for LeoQuiz (needed for FB Reels posting)
4. **Instagram Business Account** — Convert IG account to Business/Creator, link to Facebook Page
5. **YouTube Analytics API** — Enable YouTube Analytics API in Google Cloud Console (same project as upload API)
6. **Set env vars** — Add TikTok + Meta credentials to Vercel environment variables

---

## Testing Strategy

### Pipeline Tests

- `test_longform_assembler.py` — layout rendering, section cards, score counter, round timing
- `test_thumbnail.py` — add tests for Variant B and C generators
- `test_uploader.py` — mock API calls for TikTok/Instagram/Facebook uploads
- `test_metadata.py` — Instagram and Facebook metadata format validation
- `test_config.py` — long-form and mega timing constant validation

### Dashboard Tests

- Analytics API routes — mock platform API responses, verify data aggregation
- OAuth flows — mock token exchange, verify Blob storage
- Thumbnail test tracking — verify CTR data storage and win calculation
- Generate page — verify format selector triggers correct workflow_dispatch inputs
