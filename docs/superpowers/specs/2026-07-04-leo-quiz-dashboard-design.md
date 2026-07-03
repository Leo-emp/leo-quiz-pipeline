# Leo Quiz Dashboard Design Spec

## Overview

A Vercel-hosted Next.js 15 dashboard for managing the LeoQuiz automated kids quiz video pipeline. Provides manual + automated video generation triggers, an approval queue for reviewing generated videos before posting, editable auto-generated captions/hashtags, scheduled posting to YouTube/TikTok, and pipeline monitoring.

**Repo:** `leo-quiz-dashboard` (new repo under `Leo-emp` GitHub account)
**Pipeline repo:** `leo-quiz-pipeline` (new repo under `Leo-emp` for the existing Python pipeline)
**Deploy:** Vercel
**Database:** Turso (SQLite)
**Storage:** Vercel Blob (videos + thumbnails)
**Auth:** Admin email/password login with session cookie
**Theme:** Dark indigo/purple glassmorphism (matching JobPilot space theme)

## Architecture

```
┌─────────────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Dashboard (Vercel) │ ←──→ │  Turso DB    │      │  Vercel Blob    │
│  Next.js 15 App     │      │  (SQLite)    │      │  (video/thumb)  │
└────────┬────────────┘      └──────────────┘      └────────▲────────┘
         │                                                   │
         │ workflow_dispatch                                 │ upload
         ▼                                                   │
┌─────────────────────┐                                      │
│  GitHub Actions     │──────────────────────────────────────┘
│  (leo-quiz-pipeline)│──── webhook callback to dashboard API
└─────────────────────┘
```

**Data flow:**
1. Dashboard triggers GitHub Actions workflow (manual or automated cron)
2. GitHub Action runs Python pipeline: Gemini content → Imagen images → silhouettes → ElevenLabs narration → audio mix → video assembly → thumbnail → metadata
3. Action uploads video + thumbnail to Vercel Blob
4. Action calls dashboard webhook API with Blob URLs, auto-generated captions/hashtags/tags, quiz pack data
5. Dashboard stores record in Turso, video appears in Approval Queue
6. User reviews, edits captions/hashtags, approves, and schedules posting time
7. Vercel Cron triggers upload GitHub Action at scheduled time
8. Upload Action downloads from Blob, uploads to YouTube/TikTok with metadata

## Authentication

Single admin user with email/password login page.

- Admin email and bcrypt-hashed password stored in environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`)
- Login page at `/login` with email + password form
- Successful login sets an encrypted HTTP-only session cookie (using `iron-session`)
- All other routes protected by middleware that checks for valid session
- Session expires after 7 days, configurable
- No registration — single admin user only

## Pages

### 1. Dashboard (`/`)

Overview stats and recent activity.

**Stats cards (top row):**
- Videos generated (today / this week / all time)
- Pending approval count (badge with number)
- Next scheduled generation (countdown)
- Next scheduled post (countdown)

**Activity feed (below):**
- Chronological list of recent events: "Video generated: Guess the Animal", "Video approved", "Video uploaded to YouTube", "Generation failed"
- Each entry shows timestamp, action icon, message, and link to the video
- Last 20 events, with "View all" link to history

### 2. Generate (`/generate`)

Two sections: manual trigger and automation status.

**Manual Generate card:**
- Category dropdown (animals, dinosaurs, space, vehicles, fruits, flags, or "auto" for today's rotation)
- Rounds count input (default 5)
- "Generate Video" button
- After clicking: progress indicator showing GitHub Action status (queued → in_progress → completed → callback received)
- Status polled every 10 seconds via GitHub Actions API

**Auto Schedule card:**
- Toggle switch: auto-generation on/off
- Daily time picker (hour/minute UTC)
- Weekly compilation day picker
- Category rotation display (Mon=animals, Tue=dinosaurs, etc.)
- "Next run" countdown timer
- Save button persists to `schedule_config` table

### 3. Approval Queue (`/queue`)

List of videos with status `pending`, sorted newest first.

**Each video card shows:**
- Video player (inline, using Vercel Blob URL)
- Thumbnail preview beside the player
- Category badge (color-coded)
- Trigger type badge (manual / automated)
- Generated timestamp
- Quiz rounds summary (answers list)

**Editable metadata fields (pre-filled by Gemini):**
- Title (text input)
- Description (textarea)
- Tags (tag input with add/remove)
- Hashtags (tag input with add/remove)
- Platform selector (YouTube / TikTok / Both)

**Action buttons:**
- "Approve & Post Now" — sets status to `approved`, immediately triggers upload Action
- "Approve & Schedule" — opens date/time picker, sets status to `scheduled` with `scheduled_at`
- "Reject" — sets status to `rejected`, moves to history
- "Regenerate" — triggers a new generation for the same category

### 4. History (`/history`)

All past videos, searchable and filterable.

**Filters (top bar):**
- Status: all / pending / approved / scheduled / uploaded / rejected / failed
- Category: all / animals / dinosaurs / space / vehicles / fruits / flags
- Trigger: all / manual / automated
- Date range picker
- Search by title

**Table/grid view:**
- Thumbnail, title, category, status badge, trigger type, created date, posted date
- Click to expand: full metadata, video player, quiz round details
- Bulk actions: select multiple → approve / reject

### 5. Settings (`/settings`)

System configuration.

**Schedule section:**
- Same controls as the Auto Schedule card on Generate page (single source of truth)
- Scheduled posts calendar: week view showing upcoming scheduled videos

**API Status section:**
- Green/red indicators for: Gemini API key, ElevenLabs API key, GitHub token, Vercel Blob token
- "Test Connection" button for each

**Pipeline section:**
- Link to GitHub Actions runs page
- History.json stats (total answers used per category, never-repeat pool size)

## Data Model (Turso/SQLite)

### `videos` table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | ULID, e.g. `01J4X...` |
| category | TEXT NOT NULL | animals/dinosaurs/space/vehicles/fruits/flags |
| status | TEXT NOT NULL | generating/pending/approved/scheduled/uploaded/rejected/failed |
| trigger_type | TEXT NOT NULL | manual/automated |
| title | TEXT | Auto-generated, editable |
| description | TEXT | Auto-generated, editable |
| tags | TEXT | JSON array of strings |
| hashtags | TEXT | JSON array of strings |
| video_url | TEXT | Vercel Blob URL |
| thumbnail_url | TEXT | Vercel Blob URL |
| metadata_json | TEXT | Full quiz pack JSON (rounds, answers, facts, prompts) |
| github_run_id | TEXT | GitHub Actions run ID for status polling |
| rounds_count | INTEGER | Number of quiz rounds |
| platform | TEXT DEFAULT 'both' | youtube/tiktok/both |
| scheduled_at | TEXT | ISO timestamp for scheduled posting (nullable) |
| created_at | TEXT NOT NULL | ISO timestamp |
| reviewed_at | TEXT | When approved/rejected (nullable) |
| uploaded_at | TEXT | When posted to platform (nullable) |

### `schedule_config` table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Always 1 (single row) |
| auto_enabled | INTEGER DEFAULT 0 | 0=off, 1=on |
| daily_hour_utc | INTEGER DEFAULT 6 | 0-23 |
| daily_minute_utc | INTEGER DEFAULT 0 | 0-59 |
| weekly_day | INTEGER DEFAULT 6 | 0=Mon, 6=Sun |
| weekly_hour_utc | INTEGER DEFAULT 8 | 0-23 |
| updated_at | TEXT | Last config change |

### `activity_log` table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | ULID |
| action | TEXT NOT NULL | generated/approved/rejected/scheduled/uploaded/failed |
| video_id | TEXT | FK to videos.id (nullable for system events) |
| message | TEXT NOT NULL | Human-readable event description |
| created_at | TEXT NOT NULL | ISO timestamp |

## API Routes

### Pipeline Integration
- `POST /api/webhook/pipeline-complete` — Called by GitHub Action after video generation. Receives: video_id, blob URLs, metadata, captions, hashtags. Updates video record, logs activity. Protected by webhook secret.
- `POST /api/generate` — Triggers GitHub Actions workflow_dispatch. Creates video record with status `generating`. Returns video_id.
- `GET /api/videos/[id]/status` — Polls GitHub Actions API for workflow run status. Returns current step.

### CRUD
- `GET /api/videos` — List videos with filters (status, category, trigger_type, date range). Paginated.
- `GET /api/videos/[id]` — Single video detail.
- `PATCH /api/videos/[id]` — Update title, description, tags, hashtags, platform, scheduled_at.
- `POST /api/videos/[id]/approve` — Set status to approved. Optionally include scheduled_at for scheduled posting.
- `POST /api/videos/[id]/reject` — Set status to rejected.
- `POST /api/videos/[id]/upload` — Trigger upload GitHub Action for this video.

### Schedule
- `GET /api/schedule` — Current schedule config.
- `PUT /api/schedule` — Update schedule config.

### Auth
- `POST /api/auth/login` — Email + password → session cookie.
- `POST /api/auth/logout` — Clear session.
- `GET /api/auth/session` — Check current session.

### Activity
- `GET /api/activity` — Recent activity log entries (last 50).

## GitHub Actions Integration

### Modified `daily.yml` (in leo-quiz-pipeline repo)

After the existing pipeline steps, add:
1. Upload video + thumbnail to Vercel Blob using `@vercel/blob` CLI or curl
2. POST to dashboard webhook with: video_id, blob URLs, quiz_pack.json contents, metadata_youtube.json contents
3. Webhook secret passed as `DASHBOARD_WEBHOOK_SECRET` GitHub Secret

### New `upload.yml` (in leo-quiz-pipeline repo)

Triggered by workflow_dispatch with inputs: video_id, video_blob_url, metadata (title, description, tags), platform.
1. Download video from Vercel Blob URL
2. Upload to YouTube (using stored OAuth refresh token) and/or TikTok
3. POST result back to dashboard webhook (uploaded URL or error)

## Vercel Cron

One cron job:
- `POST /api/cron/check-scheduled` — Runs every 15 minutes. Finds videos where `status = 'scheduled'` and `scheduled_at <= now()`. Triggers the upload GitHub Action for each. Protected by `CRON_SECRET`.

## Visual Design

**Theme:** Dark indigo/purple glassmorphism (consistent with JobPilot space theme)
- Background: deep indigo gradient (#0f0b2e → #1a1145)
- Cards: semi-transparent glass (#ffffff08 bg, subtle border glow)
- Primary accent: indigo-500 (#6366f1)
- Secondary accent: purple-500 (#a855f7)
- Success: emerald-500
- Warning: amber-500
- Error: rose-500
- Text: white primary, gray-400 secondary

**Sidebar:** Fixed left, dark glass panel, Leo mascot icon at top, nav items with hover/active glow animations.

**Cards:** Rounded-xl, glass background, subtle border, shadow glow on hover.

**Status badges:** Color-coded pills — generating (blue pulse), pending (amber), approved (emerald), scheduled (purple), uploaded (teal), rejected (rose), failed (red).

**Typography:** System font stack, semibold headings, clean spacing. All font sizes mobile-readable (min 14px body, 18px headings).

**Responsive:** Desktop-first sidebar layout, collapses to bottom nav on mobile.

## Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS 4
- **Database:** Turso (@libsql/client)
- **Storage:** Vercel Blob (@vercel/blob)
- **Auth:** iron-session (encrypted cookies)
- **Icons:** Lucide React
- **Date handling:** date-fns
- **ID generation:** ulid

## Environment Variables

```
# Auth
ADMIN_EMAIL=
ADMIN_PASSWORD_HASH=
SESSION_SECRET=

# Database
TURSO_DATABASE_URL=
TURSO_AUTH_TOKEN=

# Storage
BLOB_READ_WRITE_TOKEN=

# GitHub Integration
GITHUB_TOKEN=              # PAT with workflow trigger permissions
GITHUB_REPO_OWNER=Leo-emp
GITHUB_REPO_NAME=leo-quiz-pipeline

# Webhook
DASHBOARD_WEBHOOK_SECRET=  # Shared secret for pipeline callback

# Cron
CRON_SECRET=
```

## Project Structure

```
leo-quiz-dashboard/
├── app/
│   ├── layout.tsx              # Root layout with sidebar
│   ├── page.tsx                # Dashboard overview
│   ├── login/
│   │   └── page.tsx            # Login page
│   ├── generate/
│   │   └── page.tsx            # Manual generate + auto schedule
│   ├── queue/
│   │   └── page.tsx            # Approval queue
│   ├── history/
│   │   └── page.tsx            # Video history
│   ├── settings/
│   │   └── page.tsx            # Settings
│   └── api/
│       ├── auth/
│       │   ├── login/route.ts
│       │   ├── logout/route.ts
│       │   └── session/route.ts
│       ├── generate/route.ts
│       ├── videos/
│       │   ├── route.ts        # GET list
│       │   └── [id]/
│       │       ├── route.ts    # GET, PATCH
│       │       ├── approve/route.ts
│       │       ├── reject/route.ts
│       │       └── upload/route.ts
│       ├── schedule/route.ts
│       ├── activity/route.ts
│       ├── webhook/
│       │   └── pipeline-complete/route.ts
│       └── cron/
│           └── check-scheduled/route.ts
├── lib/
│   ├── db.ts                   # Turso client + query helpers
│   ├── schema.sql              # Table definitions
│   ├── auth.ts                 # Session helpers (iron-session)
│   ├── github.ts               # GitHub Actions API helpers
│   ├── blob.ts                 # Vercel Blob helpers
│   └── types.ts                # TypeScript types
├── components/
│   ├── sidebar.tsx
│   ├── stats-card.tsx
│   ├── video-card.tsx
│   ├── video-player.tsx
│   ├── metadata-editor.tsx
│   ├── schedule-form.tsx
│   ├── activity-feed.tsx
│   ├── status-badge.tsx
│   ├── category-badge.tsx
│   └── date-time-picker.tsx
├── middleware.ts                # Auth check on all routes except /login
├── tailwind.config.ts
├── package.json
└── vercel.json                 # Cron config
```
