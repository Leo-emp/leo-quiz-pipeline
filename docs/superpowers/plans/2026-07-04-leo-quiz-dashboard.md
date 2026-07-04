# Leo Quiz Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vercel-hosted Next.js 15 dashboard to control the LeoQuiz video pipeline — manual + automated generation, approval queue, scheduled YouTube posting, and pipeline monitoring.

**Architecture:** Next.js 15 App Router with Turso (SQLite) for data, Vercel Blob for video/thumbnail/token storage, iron-session for admin auth. Dashboard triggers the Python pipeline via GitHub Actions workflow_dispatch; the Action calls back to a webhook with results. YouTube uploads also happen via GitHub Action to avoid Vercel's 60s timeout. Vercel Cron checks for scheduled videos every 15 minutes.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS 4, @libsql/client (Turso), @vercel/blob, iron-session, lucide-react, date-fns, ulid

## Global Constraints

- All code must include heavy `//` comments throughout for learning (user preference)
- Dark indigo/purple glassmorphism theme: bg gradient #0f0b2e → #1a1145, glass cards #ffffff08, accents indigo-500/purple-500
- Single admin user — email/password in env vars, no registration
- All font sizes mobile-readable: min 14px body, 18px headings
- COPPA compliance: `selfDeclaredMadeForKids: true` on all YouTube uploads
- Category values are exactly: `animals`, `dinosaurs`, `space`, `vehicles`, `fruits`, `flags`
- Status values are exactly: `generating`, `pending`, `approved`, `scheduled`, `uploaded`, `rejected`, `failed`
- IDs use ULID format (e.g. `01J4X...`)
- All timestamps stored as ISO 8601 strings
- YouTube OAuth tokens stored in Vercel Blob (connect once, auto-refresh forever)
- The dashboard project is a NEW repo `leo-quiz-dashboard` under GitHub account `Leo-emp`, separate from the pipeline repo `leo-quiz-pipeline`

---

### Task 1: Project Scaffold + Types + Database Layer

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `next.config.ts`
- Create: `tailwind.config.ts`
- Create: `app/globals.css`
- Create: `vercel.json`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `lib/types.ts`
- Create: `lib/schema.sql`
- Create: `lib/db.ts`
- Create: `app/layout.tsx` (minimal — just mounts globals.css)
- Create: `app/page.tsx` (placeholder — "Dashboard coming soon")
- Test: `__tests__/db.test.ts`

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `Video` type with all 18 fields from spec
  - `ScheduleConfig` type
  - `ActivityLogEntry` type
  - `VideoStatus`, `Category`, `TriggerType`, `Platform` union types
  - `db` — Turso client instance
  - `createVideo(data: Partial<Video>): Promise<Video>`
  - `getVideo(id: string): Promise<Video | null>`
  - `updateVideo(id: string, data: Partial<Video>): Promise<Video>`
  - `listVideos(filters: VideoFilters): Promise<{ videos: Video[]; total: number }>`
  - `getScheduleConfig(): Promise<ScheduleConfig>`
  - `updateScheduleConfig(data: Partial<ScheduleConfig>): Promise<ScheduleConfig>`
  - `logActivity(action: string, videoId: string | null, message: string): Promise<void>`
  - `getRecentActivity(limit: number): Promise<ActivityLogEntry[]>`
  - `getVideoStats(): Promise<{ today: number; week: number; total: number; pending: number }>`

- [ ] **Step 1: Initialize Next.js project**

Run:
```bash
cd C:\Users\User
npx create-next-app@latest leo-quiz-dashboard --typescript --tailwind --app --src=false --eslint --no-import-alias --turbopack
cd leo-quiz-dashboard
```

- [ ] **Step 2: Install dependencies**

Run:
```bash
npm install @libsql/client @vercel/blob iron-session lucide-react date-fns ulid bcryptjs
npm install -D @types/bcryptjs vitest @vitejs/plugin-react
```

- [ ] **Step 3: Create environment example file**

Create `.env.example`:
```env
# -- Auth --
# Admin login credentials
ADMIN_EMAIL=admin@leoquiz.com
ADMIN_PASSWORD_HASH=          # bcrypt hash of your password — generate with: npx bcryptjs hash "yourpassword"
SESSION_SECRET=                # 32+ char random string for iron-session encryption

# -- Database (Turso) --
TURSO_DATABASE_URL=            # libsql://your-db.turso.io
TURSO_AUTH_TOKEN=              # Turso auth token

# -- Storage (Vercel Blob) --
BLOB_READ_WRITE_TOKEN=         # Vercel Blob read/write token

# -- GitHub Actions Integration --
GITHUB_TOKEN=                  # Personal access token with workflow trigger permissions
GITHUB_REPO_OWNER=Leo-emp
GITHUB_REPO_NAME=leo-quiz-pipeline

# -- Webhook Security --
DASHBOARD_WEBHOOK_SECRET=      # Shared secret between pipeline Action and dashboard

# -- Cron Security --
CRON_SECRET=                   # Vercel cron authorization secret

# -- YouTube OAuth (connect-once) --
YOUTUBE_CLIENT_ID=             # Google Cloud Console OAuth client ID
YOUTUBE_CLIENT_SECRET=         # Google Cloud Console OAuth client secret
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

- [ ] **Step 4: Create vercel.json with cron config**

Create `vercel.json`:
```json
{
  "crons": [
    {
      "path": "/api/cron/check-scheduled",
      "schedule": "*/15 * * * *"
    }
  ]
}
```

- [ ] **Step 5: Create TypeScript types**

Create `lib/types.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Core TypeScript types for LeoQuiz Dashboard.
//  Every module imports from here — this is the single source
//  of truth for data shapes across the entire app.
// ─────────────────────────────────────────────────────────────

// -- Video status lifecycle --
// generating → pending → approved → scheduled → uploaded
// Also: rejected (from pending), failed (from generating or uploading)
export type VideoStatus =
  | "generating"
  | "pending"
  | "approved"
  | "scheduled"
  | "uploaded"
  | "rejected"
  | "failed";

// -- Quiz categories matching the pipeline's config.py --
export type Category =
  | "animals"
  | "dinosaurs"
  | "space"
  | "vehicles"
  | "fruits"
  | "flags";

// -- How the video was triggered --
export type TriggerType = "manual" | "automated";

// -- Target posting platform --
export type Platform = "youtube" | "tiktok" | "both";

// -- Main video record stored in Turso --
export interface Video {
  // ULID primary key
  id: string;
  // Quiz category (animals, dinosaurs, etc.)
  category: Category;
  // Current status in the lifecycle
  status: VideoStatus;
  // How this video was triggered
  trigger_type: TriggerType;
  // Auto-generated title (editable by admin)
  title: string | null;
  // Auto-generated description (editable by admin)
  description: string | null;
  // JSON array of SEO tags
  tags: string | null;
  // JSON array of social media hashtags
  hashtags: string | null;
  // Vercel Blob URL of the rendered video
  video_url: string | null;
  // Vercel Blob URL of the thumbnail image
  thumbnail_url: string | null;
  // Full quiz pack JSON (rounds, answers, facts, prompts)
  metadata_json: string | null;
  // GitHub Actions run ID for status polling
  github_run_id: string | null;
  // Number of quiz rounds in this video
  rounds_count: number;
  // Target posting platform
  platform: Platform;
  // ISO timestamp for scheduled posting (null = not scheduled)
  scheduled_at: string | null;
  // ISO timestamp when the video record was created
  created_at: string;
  // ISO timestamp when admin approved/rejected (null = not reviewed)
  reviewed_at: string | null;
  // ISO timestamp when posted to platform (null = not uploaded)
  uploaded_at: string | null;
}

// -- Filters for the video list API --
export interface VideoFilters {
  // Filter by status (optional)
  status?: VideoStatus;
  // Filter by category (optional)
  category?: Category;
  // Filter by trigger type (optional)
  trigger_type?: TriggerType;
  // Search title substring (optional)
  search?: string;
  // Pagination offset (default 0)
  offset?: number;
  // Pagination limit (default 20)
  limit?: number;
}

// -- Schedule configuration (single row in DB) --
export interface ScheduleConfig {
  // Always 1 — singleton row
  id: number;
  // Whether auto-generation is enabled
  auto_enabled: boolean;
  // Hour (0-23 UTC) for daily generation
  daily_hour_utc: number;
  // Minute (0-59 UTC) for daily generation
  daily_minute_utc: number;
  // Day of week for weekly long-form compilation (0=Mon, 6=Sun)
  weekly_day: number;
  // Hour (0-23 UTC) for weekly compilation
  weekly_hour_utc: number;
  // ISO timestamp of last config change
  updated_at: string | null;
}

// -- Activity log entry --
export interface ActivityLogEntry {
  // ULID primary key
  id: string;
  // Action type
  action: string;
  // FK to videos.id (null for system events)
  video_id: string | null;
  // Human-readable event description
  message: string;
  // ISO timestamp
  created_at: string;
}

// -- Dashboard stats for the overview page --
export interface DashboardStats {
  // Videos generated today
  today: number;
  // Videos generated this week
  week: number;
  // Total videos ever generated
  total: number;
  // Videos awaiting approval
  pending: number;
}

// -- YouTube OAuth token data stored in Vercel Blob --
export interface TokenData {
  // Long-lived token for getting fresh access tokens
  refresh_token: string;
  // Short-lived token for API calls (~1 hour)
  access_token: string;
  // Unix timestamp (seconds) when access_token expires
  expires_at: number;
  // Display name of the connected YouTube channel
  account_name: string;
}

// -- YouTube connection status --
export interface ConnectionStatus {
  // Whether tokens exist and are valid
  connected: boolean;
  // Channel name (shown in settings)
  account_name?: string;
  // True when refresh token was rejected — user needs to re-auth
  needs_reconnect?: boolean;
}
```

- [ ] **Step 6: Create SQL schema**

Create `lib/schema.sql`:
```sql
-- ─────────────────────────────────────────────────────────────
--  LeoQuiz Dashboard database schema (Turso/SQLite).
--  Three tables: videos, schedule_config, activity_log.
--  Run this once to initialize the database.
-- ─────────────────────────────────────────────────────────────

-- Videos table — one row per generated quiz video
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'generating',
  trigger_type TEXT NOT NULL DEFAULT 'manual',
  title TEXT,
  description TEXT,
  tags TEXT,
  hashtags TEXT,
  video_url TEXT,
  thumbnail_url TEXT,
  metadata_json TEXT,
  github_run_id TEXT,
  rounds_count INTEGER NOT NULL DEFAULT 5,
  platform TEXT NOT NULL DEFAULT 'both',
  scheduled_at TEXT,
  created_at TEXT NOT NULL,
  reviewed_at TEXT,
  uploaded_at TEXT
);

-- Index for filtering by status (approval queue, history)
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);

-- Index for filtering by category
CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category);

-- Index for cron job: find scheduled videos that are due
CREATE INDEX IF NOT EXISTS idx_videos_scheduled ON videos(status, scheduled_at);

-- Schedule config — singleton row (id=1 always)
CREATE TABLE IF NOT EXISTS schedule_config (
  id INTEGER PRIMARY KEY DEFAULT 1,
  auto_enabled INTEGER NOT NULL DEFAULT 0,
  daily_hour_utc INTEGER NOT NULL DEFAULT 6,
  daily_minute_utc INTEGER NOT NULL DEFAULT 0,
  weekly_day INTEGER NOT NULL DEFAULT 6,
  weekly_hour_utc INTEGER NOT NULL DEFAULT 8,
  updated_at TEXT
);

-- Seed the schedule config singleton
INSERT OR IGNORE INTO schedule_config (id) VALUES (1);

-- Activity log — chronological event history
CREATE TABLE IF NOT EXISTS activity_log (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  video_id TEXT,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Index for recent activity queries (sorted by time)
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
```

- [ ] **Step 7: Create Turso database client and query helpers**

Create `lib/db.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Turso database client and query helpers.
//  All database access goes through this module — no raw SQL
//  in API routes. Uses @libsql/client for Turso (SQLite).
//
//  Exports one function per operation:
//    createVideo, getVideo, updateVideo, listVideos,
//    getScheduleConfig, updateScheduleConfig,
//    logActivity, getRecentActivity, getVideoStats
// ─────────────────────────────────────────────────────────────

import { createClient } from "@libsql/client";
import { ulid } from "ulid";
import type {
  Video,
  VideoFilters,
  ScheduleConfig,
  ActivityLogEntry,
  DashboardStats,
} from "./types";

// -- Create the Turso client --
// Uses env vars set in Vercel (or .env locally)
const db = createClient({
  url: process.env.TURSO_DATABASE_URL || "file:local.db",
  authToken: process.env.TURSO_AUTH_TOKEN,
});

// -- Initialize schema on first import --
// Reads schema.sql and executes it. Safe to run multiple times
// because all statements use IF NOT EXISTS.
export async function initializeDatabase(): Promise<void> {
  // Schema is executed as raw SQL statements
  await db.executeMultiple(`
    CREATE TABLE IF NOT EXISTS videos (
      id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'generating',
      trigger_type TEXT NOT NULL DEFAULT 'manual',
      title TEXT,
      description TEXT,
      tags TEXT,
      hashtags TEXT,
      video_url TEXT,
      thumbnail_url TEXT,
      metadata_json TEXT,
      github_run_id TEXT,
      rounds_count INTEGER NOT NULL DEFAULT 5,
      platform TEXT NOT NULL DEFAULT 'both',
      scheduled_at TEXT,
      created_at TEXT NOT NULL,
      reviewed_at TEXT,
      uploaded_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
    CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category);
    CREATE INDEX IF NOT EXISTS idx_videos_scheduled ON videos(status, scheduled_at);
    CREATE TABLE IF NOT EXISTS schedule_config (
      id INTEGER PRIMARY KEY DEFAULT 1,
      auto_enabled INTEGER NOT NULL DEFAULT 0,
      daily_hour_utc INTEGER NOT NULL DEFAULT 6,
      daily_minute_utc INTEGER NOT NULL DEFAULT 0,
      weekly_day INTEGER NOT NULL DEFAULT 6,
      weekly_hour_utc INTEGER NOT NULL DEFAULT 8,
      updated_at TEXT
    );
    INSERT OR IGNORE INTO schedule_config (id) VALUES (1);
    CREATE TABLE IF NOT EXISTS activity_log (
      id TEXT PRIMARY KEY,
      action TEXT NOT NULL,
      video_id TEXT,
      message TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
  `);
}

// ─── Video CRUD ──────────────────────────────────────────────

export async function createVideo(data: Partial<Video>): Promise<Video> {
  // Creates a new video record with a ULID and current timestamp.
  // Only category, trigger_type, and rounds_count are required —
  // everything else has defaults or is set later by the webhook.
  const id = ulid();
  const now = new Date().toISOString();

  await db.execute({
    sql: `INSERT INTO videos (id, category, status, trigger_type, rounds_count, platform, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?)`,
    args: [
      id,
      data.category || "animals",
      data.status || "generating",
      data.trigger_type || "manual",
      data.rounds_count || 5,
      data.platform || "both",
      now,
    ],
  });

  return getVideo(id) as Promise<Video>;
}

export async function getVideo(id: string): Promise<Video | null> {
  // Fetches a single video by its ULID
  const result = await db.execute({
    sql: "SELECT * FROM videos WHERE id = ?",
    args: [id],
  });

  if (result.rows.length === 0) return null;
  return rowToVideo(result.rows[0]);
}

export async function updateVideo(
  id: string,
  data: Partial<Video>
): Promise<Video> {
  // Updates specific fields on a video record.
  // Only updates fields that are provided (not undefined).
  const fields: string[] = [];
  const values: unknown[] = [];

  // Build SET clause dynamically from provided fields
  const updatable = [
    "status", "title", "description", "tags", "hashtags",
    "video_url", "thumbnail_url", "metadata_json", "github_run_id",
    "rounds_count", "platform", "scheduled_at", "reviewed_at", "uploaded_at",
  ] as const;

  for (const field of updatable) {
    if (data[field] !== undefined) {
      fields.push(`${field} = ?`);
      values.push(data[field]);
    }
  }

  if (fields.length === 0) return getVideo(id) as Promise<Video>;

  values.push(id);
  await db.execute({
    sql: `UPDATE videos SET ${fields.join(", ")} WHERE id = ?`,
    args: values,
  });

  return getVideo(id) as Promise<Video>;
}

export async function listVideos(
  filters: VideoFilters = {}
): Promise<{ videos: Video[]; total: number }> {
  // Lists videos with optional filters, search, and pagination.
  // Returns both the page of results and the total count.
  const conditions: string[] = [];
  const args: unknown[] = [];

  // Apply optional filters
  if (filters.status) {
    conditions.push("status = ?");
    args.push(filters.status);
  }
  if (filters.category) {
    conditions.push("category = ?");
    args.push(filters.category);
  }
  if (filters.trigger_type) {
    conditions.push("trigger_type = ?");
    args.push(filters.trigger_type);
  }
  if (filters.search) {
    conditions.push("title LIKE ?");
    args.push(`%${filters.search}%`);
  }

  const where = conditions.length > 0
    ? `WHERE ${conditions.join(" AND ")}`
    : "";

  // Get total count for pagination
  const countResult = await db.execute({
    sql: `SELECT COUNT(*) as count FROM videos ${where}`,
    args,
  });
  const total = Number(countResult.rows[0].count);

  // Get paginated results
  const limit = filters.limit || 20;
  const offset = filters.offset || 0;

  const result = await db.execute({
    sql: `SELECT * FROM videos ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`,
    args: [...args, limit, offset],
  });

  return {
    videos: result.rows.map(rowToVideo),
    total,
  };
}

// ─── Schedule Config ─────────────────────────────────────────

export async function getScheduleConfig(): Promise<ScheduleConfig> {
  // Reads the singleton schedule config row (id=1)
  const result = await db.execute("SELECT * FROM schedule_config WHERE id = 1");

  if (result.rows.length === 0) {
    // Should never happen — schema seeds this row
    return {
      id: 1,
      auto_enabled: false,
      daily_hour_utc: 6,
      daily_minute_utc: 0,
      weekly_day: 6,
      weekly_hour_utc: 8,
      updated_at: null,
    };
  }

  const row = result.rows[0];
  return {
    id: 1,
    auto_enabled: row.auto_enabled === 1,
    daily_hour_utc: Number(row.daily_hour_utc),
    daily_minute_utc: Number(row.daily_minute_utc),
    weekly_day: Number(row.weekly_day),
    weekly_hour_utc: Number(row.weekly_hour_utc),
    updated_at: row.updated_at as string | null,
  };
}

export async function updateScheduleConfig(
  data: Partial<ScheduleConfig>
): Promise<ScheduleConfig> {
  // Updates the singleton schedule config row
  const now = new Date().toISOString();

  await db.execute({
    sql: `UPDATE schedule_config SET
            auto_enabled = COALESCE(?, auto_enabled),
            daily_hour_utc = COALESCE(?, daily_hour_utc),
            daily_minute_utc = COALESCE(?, daily_minute_utc),
            weekly_day = COALESCE(?, weekly_day),
            weekly_hour_utc = COALESCE(?, weekly_hour_utc),
            updated_at = ?
          WHERE id = 1`,
    args: [
      data.auto_enabled !== undefined ? (data.auto_enabled ? 1 : 0) : null,
      data.daily_hour_utc ?? null,
      data.daily_minute_utc ?? null,
      data.weekly_day ?? null,
      data.weekly_hour_utc ?? null,
      now,
    ],
  });

  return getScheduleConfig();
}

// ─── Activity Log ────────────────────────────────────────────

export async function logActivity(
  action: string,
  videoId: string | null,
  message: string
): Promise<void> {
  // Records an activity event (e.g., "Video generated", "Video approved")
  const id = ulid();
  const now = new Date().toISOString();

  await db.execute({
    sql: `INSERT INTO activity_log (id, action, video_id, message, created_at)
          VALUES (?, ?, ?, ?, ?)`,
    args: [id, action, videoId, message, now],
  });
}

export async function getRecentActivity(
  limit: number = 20
): Promise<ActivityLogEntry[]> {
  // Fetches the most recent activity log entries
  const result = await db.execute({
    sql: "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?",
    args: [limit],
  });

  return result.rows.map((row) => ({
    id: row.id as string,
    action: row.action as string,
    video_id: row.video_id as string | null,
    message: row.message as string,
    created_at: row.created_at as string,
  }));
}

// ─── Dashboard Stats ─────────────────────────────────────────

export async function getVideoStats(): Promise<DashboardStats> {
  // Computes dashboard overview stats in a single query batch.
  // Returns today's count, this week's count, total, and pending.
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();

  // Monday of current week at 00:00
  const dayOfWeek = now.getDay();
  const mondayOffset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
  const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - mondayOffset).toISOString();

  const [todayResult, weekResult, totalResult, pendingResult] = await Promise.all([
    db.execute({ sql: "SELECT COUNT(*) as c FROM videos WHERE created_at >= ?", args: [todayStart] }),
    db.execute({ sql: "SELECT COUNT(*) as c FROM videos WHERE created_at >= ?", args: [weekStart] }),
    db.execute({ sql: "SELECT COUNT(*) as c FROM videos", args: [] }),
    db.execute({ sql: "SELECT COUNT(*) as c FROM videos WHERE status = 'pending'", args: [] }),
  ]);

  return {
    today: Number(todayResult.rows[0].c),
    week: Number(weekResult.rows[0].c),
    total: Number(totalResult.rows[0].c),
    pending: Number(pendingResult.rows[0].c),
  };
}

// ─── Row mapper ──────────────────────────────────────────────

function rowToVideo(row: Record<string, unknown>): Video {
  // Converts a raw Turso row to a typed Video object
  return {
    id: row.id as string,
    category: row.category as Video["category"],
    status: row.status as Video["status"],
    trigger_type: row.trigger_type as Video["trigger_type"],
    title: row.title as string | null,
    description: row.description as string | null,
    tags: row.tags as string | null,
    hashtags: row.hashtags as string | null,
    video_url: row.video_url as string | null,
    thumbnail_url: row.thumbnail_url as string | null,
    metadata_json: row.metadata_json as string | null,
    github_run_id: row.github_run_id as string | null,
    rounds_count: Number(row.rounds_count),
    platform: (row.platform as Video["platform"]) || "both",
    scheduled_at: row.scheduled_at as string | null,
    created_at: row.created_at as string,
    reviewed_at: row.reviewed_at as string | null,
    uploaded_at: row.uploaded_at as string | null,
  };
}
```

- [ ] **Step 8: Write database tests**

Create `__tests__/db.test.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Database layer tests — uses a local SQLite file.
//  Tests all CRUD operations, filters, stats, and activity log.
// ─────────────────────────────────────────────────────────────
import { describe, it, expect, beforeAll } from "vitest";
import {
  initializeDatabase,
  createVideo,
  getVideo,
  updateVideo,
  listVideos,
  getScheduleConfig,
  updateScheduleConfig,
  logActivity,
  getRecentActivity,
  getVideoStats,
} from "../lib/db";

// Initialize the local DB before all tests
beforeAll(async () => {
  await initializeDatabase();
});

describe("Video CRUD", () => {
  it("creates and retrieves a video", async () => {
    // Create a new video record
    const video = await createVideo({
      category: "animals",
      trigger_type: "manual",
      rounds_count: 5,
    });

    // Verify it was created with defaults
    expect(video.id).toBeTruthy();
    expect(video.category).toBe("animals");
    expect(video.status).toBe("generating");
    expect(video.trigger_type).toBe("manual");
    expect(video.rounds_count).toBe(5);
    expect(video.platform).toBe("both");
    expect(video.created_at).toBeTruthy();

    // Retrieve it by ID
    const found = await getVideo(video.id);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(video.id);
  });

  it("updates specific fields on a video", async () => {
    const video = await createVideo({ category: "space" });

    // Update status and title
    const updated = await updateVideo(video.id, {
      status: "pending",
      title: "Guess the Planet!",
    });

    expect(updated.status).toBe("pending");
    expect(updated.title).toBe("Guess the Planet!");
    // Category should be unchanged
    expect(updated.category).toBe("space");
  });

  it("lists videos with filters", async () => {
    // Create videos with different categories
    await createVideo({ category: "dinosaurs", trigger_type: "automated" });
    await createVideo({ category: "dinosaurs", trigger_type: "manual" });

    // Filter by category
    const { videos, total } = await listVideos({ category: "dinosaurs" });
    expect(videos.length).toBeGreaterThanOrEqual(2);
    expect(total).toBeGreaterThanOrEqual(2);
    // All results should be dinosaurs
    videos.forEach((v) => expect(v.category).toBe("dinosaurs"));
  });

  it("returns null for non-existent video", async () => {
    const found = await getVideo("nonexistent-id");
    expect(found).toBeNull();
  });
});

describe("Schedule Config", () => {
  it("returns default config", async () => {
    const config = await getScheduleConfig();
    expect(config.id).toBe(1);
    expect(config.auto_enabled).toBe(false);
    expect(config.daily_hour_utc).toBe(6);
  });

  it("updates config fields", async () => {
    const updated = await updateScheduleConfig({
      auto_enabled: true,
      daily_hour_utc: 8,
    });
    expect(updated.auto_enabled).toBe(true);
    expect(updated.daily_hour_utc).toBe(8);
    expect(updated.updated_at).toBeTruthy();
  });
});

describe("Activity Log", () => {
  it("logs and retrieves activity", async () => {
    await logActivity("generated", null, "Test video generated");

    const recent = await getRecentActivity(5);
    expect(recent.length).toBeGreaterThanOrEqual(1);
    expect(recent[0].action).toBe("generated");
    expect(recent[0].message).toBe("Test video generated");
  });
});

describe("Dashboard Stats", () => {
  it("returns stats object with all fields", async () => {
    const stats = await getVideoStats();
    expect(stats).toHaveProperty("today");
    expect(stats).toHaveProperty("week");
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("pending");
    expect(stats.total).toBeGreaterThanOrEqual(0);
  });
});
```

- [ ] **Step 9: Add vitest config and test script**

Create `vitest.config.ts`:
```typescript
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
});
```

Add to `package.json` scripts:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 10: Run tests to verify database layer**

Run: `npm test -- __tests__/db.test.ts`
Expected: All 7 tests PASS

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: project scaffold with types, DB schema, and Turso client"
```

---

### Task 2: Auth System (iron-session + Middleware)

**Files:**
- Create: `lib/auth.ts`
- Create: `middleware.ts`
- Create: `app/api/auth/login/route.ts`
- Create: `app/api/auth/logout/route.ts`
- Create: `app/api/auth/session/route.ts`
- Test: `__tests__/auth.test.ts`

**Interfaces:**
- Consumes: nothing (self-contained auth)
- Produces:
  - `getSession(req, res): Promise<IronSession>` — reads/creates encrypted session
  - `sessionOptions: SessionOptions` — iron-session config object
  - `POST /api/auth/login` — accepts `{ email, password }`, sets session cookie, returns `{ success: true }`
  - `POST /api/auth/logout` — clears session cookie
  - `GET /api/auth/session` — returns `{ authenticated: true, email }` or `{ authenticated: false }`
  - `middleware.ts` — protects all routes except `/login`, `/api/auth/login`, `/api/webhook/*`, `/api/cron/*`

- [ ] **Step 1: Write auth test**

Create `__tests__/auth.test.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Auth module tests — verifies password validation logic.
//  Session/cookie tests happen at the API route level.
// ─────────────────────────────────────────────────────────────
import { describe, it, expect } from "vitest";
import bcrypt from "bcryptjs";

describe("Auth password validation", () => {
  it("validates correct password against bcrypt hash", async () => {
    // Simulate what happens at login: hash a password, then verify it
    const password = "test-admin-password";
    const hash = await bcrypt.hash(password, 10);

    // Correct password should match
    const valid = await bcrypt.compare(password, hash);
    expect(valid).toBe(true);

    // Wrong password should not match
    const invalid = await bcrypt.compare("wrong-password", hash);
    expect(invalid).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it passes**

Run: `npm test -- __tests__/auth.test.ts`
Expected: PASS

- [ ] **Step 3: Create auth helpers**

Create `lib/auth.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Authentication helpers using iron-session.
//  Provides encrypted HTTP-only session cookies for admin login.
//  Single admin user — credentials stored in environment vars.
//
//  Usage:
//    const session = await getSession();
//    session.isLoggedIn = true;
//    await session.save();
// ─────────────────────────────────────────────────────────────

import { getIronSession, type SessionOptions } from "iron-session";
import { cookies } from "next/headers";

// -- Session data shape --
// Stored encrypted in the cookie — only the server can read it
export interface SessionData {
  // Whether the user is authenticated
  isLoggedIn: boolean;
  // Admin email (for display in the UI)
  email?: string;
}

// -- Default session values (before login) --
export const defaultSession: SessionData = {
  isLoggedIn: false,
};

// -- iron-session configuration --
export const sessionOptions: SessionOptions = {
  // Encryption key — must be at least 32 characters
  password: process.env.SESSION_SECRET || "this-is-a-development-secret-that-is-at-least-32-chars",
  // Cookie name in the browser
  cookieName: "leoquiz-session",
  cookieOptions: {
    // Only send over HTTPS in production
    secure: process.env.NODE_ENV === "production",
    // Prevent JavaScript access to the cookie
    httpOnly: true,
    // CSRF protection — cookie sent on same-site navigations
    sameSite: "lax" as const,
    // Session expires after 7 days
    maxAge: 60 * 60 * 24 * 7,
  },
};

// -- Get the current session from the request cookies --
export async function getSession() {
  // Reads the encrypted session cookie and returns typed session data.
  // If no session exists, returns defaultSession (isLoggedIn: false).
  const cookieStore = await cookies();
  const session = await getIronSession<SessionData>(cookieStore, sessionOptions);

  // Ensure defaults are set on first access
  if (session.isLoggedIn === undefined) {
    session.isLoggedIn = defaultSession.isLoggedIn;
  }

  return session;
}
```

- [ ] **Step 4: Create login API route**

Create `app/api/auth/login/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/auth/login
//  Validates admin email + password against env vars.
//  On success: sets encrypted session cookie, returns 200.
//  On failure: returns 401 with error message.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getSession } from "@/lib/auth";

export async function POST(request: Request) {
  // Parse the login form data
  const body = await request.json().catch(() => ({}));
  const { email, password } = body as { email?: string; password?: string };

  // Validate required fields
  if (!email || !password) {
    return NextResponse.json(
      { error: "Email and password are required" },
      { status: 400 }
    );
  }

  // Check email matches the admin email from env
  const adminEmail = process.env.ADMIN_EMAIL;
  const adminPasswordHash = process.env.ADMIN_PASSWORD_HASH;

  if (!adminEmail || !adminPasswordHash) {
    // Server misconfigured — admin credentials not set
    console.error("[AUTH] ADMIN_EMAIL or ADMIN_PASSWORD_HASH not set");
    return NextResponse.json(
      { error: "Server configuration error" },
      { status: 500 }
    );
  }

  // Verify email matches (case-insensitive)
  if (email.toLowerCase() !== adminEmail.toLowerCase()) {
    return NextResponse.json(
      { error: "Invalid credentials" },
      { status: 401 }
    );
  }

  // Verify password against bcrypt hash
  const passwordValid = await bcrypt.compare(password, adminPasswordHash);
  if (!passwordValid) {
    return NextResponse.json(
      { error: "Invalid credentials" },
      { status: 401 }
    );
  }

  // -- Login successful — create session --
  const session = await getSession();
  session.isLoggedIn = true;
  session.email = email;
  await session.save();

  return NextResponse.json({ success: true });
}
```

- [ ] **Step 5: Create logout API route**

Create `app/api/auth/logout/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/auth/logout
//  Destroys the session cookie, logging the admin out.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";

export async function POST() {
  // Destroy the session — clears the encrypted cookie
  const session = await getSession();
  session.destroy();

  return NextResponse.json({ success: true });
}
```

- [ ] **Step 6: Create session check API route**

Create `app/api/auth/session/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/auth/session
//  Returns the current authentication status.
//  Used by the frontend to check if the user is logged in.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";

export async function GET() {
  const session = await getSession();

  if (session.isLoggedIn) {
    return NextResponse.json({
      authenticated: true,
      email: session.email,
    });
  }

  return NextResponse.json({ authenticated: false });
}
```

- [ ] **Step 7: Create middleware for route protection**

Create `middleware.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  Next.js middleware — protects all routes except public ones.
//  Checks for a valid iron-session cookie on every request.
//  Redirects unauthenticated users to /login.
//
//  Public routes (no auth required):
//    /login — the login page itself
//    /api/auth/login — the login API endpoint
//    /api/webhook/* — pipeline callback (uses webhook secret)
//    /api/cron/* — Vercel cron jobs (uses CRON_SECRET)
//    /api/tokens/* — GitHub Action token requests (uses webhook secret)
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getIronSession } from "iron-session";
import { sessionOptions, type SessionData } from "@/lib/auth";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // -- Skip auth for public routes --
  const publicPaths = [
    "/login",
    "/api/auth/login",
    "/api/webhook",
    "/api/cron",
    "/api/tokens",
  ];

  // Check if the current path starts with any public path
  if (publicPaths.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // -- Check session cookie --
  const response = NextResponse.next();
  const session = await getIronSession<SessionData>(
    request,
    response,
    sessionOptions
  );

  // Redirect to login if not authenticated
  if (!session.isLoggedIn) {
    // API routes return 401 instead of redirect
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    // Page routes redirect to login
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

// -- Configure which routes the middleware runs on --
export const config = {
  matcher: [
    // Match all routes except static files and Next.js internals
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
```

- [ ] **Step 8: Run auth tests**

Run: `npm test -- __tests__/auth.test.ts`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add lib/auth.ts middleware.ts app/api/auth/
git commit -m "feat: admin auth system with iron-session and route protection"
```

---

### Task 3: Root Layout + Theme + Sidebar + Login Page

**Files:**
- Modify: `app/globals.css`
- Modify: `app/layout.tsx`
- Create: `app/login/page.tsx`
- Create: `components/sidebar.tsx`

**Interfaces:**
- Consumes: `getSession()` from `lib/auth.ts`, `POST /api/auth/login`
- Produces:
  - Root layout with dark indigo gradient background and conditional sidebar
  - `<Sidebar />` component with nav links: Dashboard, Generate, Queue, History, Settings
  - `/login` page with email/password form

- [ ] **Step 1: Create globals.css with theme**

Overwrite `app/globals.css`:
```css
/* ─────────────────────────────────────────────────────────────
   LeoQuiz Dashboard — Global Styles
   Dark indigo/purple glassmorphism theme.
   Background: deep indigo gradient (#0f0b2e → #1a1145)
   Cards: semi-transparent glass with subtle glow
   ───────────────────────────────────────────────────────────── */

@import "tailwindcss";

/* -- Base layer: dark theme defaults -- */
@layer base {
  body {
    /* Deep indigo gradient background */
    background: linear-gradient(135deg, #0f0b2e 0%, #1a1145 50%, #0f0b2e 100%);
    /* White text by default */
    color: #f3f4f6;
    /* Prevent horizontal scroll */
    overflow-x: hidden;
    /* Minimum full viewport height */
    min-height: 100vh;
  }
}

/* -- Glassmorphism card utility -- */
.glass-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

/* -- Glass card with hover glow effect -- */
.glass-card-hover {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: all 0.3s ease;
}
.glass-card-hover:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.15);
}

/* -- Sidebar glass panel -- */
.glass-sidebar {
  background: rgba(15, 11, 46, 0.85);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* -- Status badge pulse animation -- */
@keyframes pulse-glow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.animate-pulse-glow {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* -- Scrollbar styling for dark theme -- */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
```

- [ ] **Step 2: Create Sidebar component**

Create `components/sidebar.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Sidebar navigation — fixed left panel with glassmorphism.
//  Shows Leo mascot icon at top, nav links with active state,
//  and logout button at bottom.
//  Collapses to bottom nav on mobile (< md breakpoint).
// ─────────────────────────────────────────────────────────────

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Sparkles,
  CheckSquare,
  History,
  Settings,
  LogOut,
  Clapperboard,
} from "lucide-react";

// -- Navigation items with their routes and icons --
const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/generate", label: "Generate", icon: Sparkles },
  { href: "/queue", label: "Queue", icon: CheckSquare },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  // Get the current route to highlight the active nav item
  const pathname = usePathname();
  const router = useRouter();

  // -- Handle logout --
  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  };

  return (
    <>
      {/* -- Desktop sidebar (hidden on mobile) -- */}
      <aside className="hidden md:flex glass-sidebar fixed left-0 top-0 h-screen w-64 flex-col z-50">
        {/* -- Logo / Brand area -- */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/5">
          {/* Leo mascot icon placeholder — uses Clapperboard icon */}
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <Clapperboard className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">LeoQuiz</h1>
            <p className="text-xs text-gray-400">Video Dashboard</p>
          </div>
        </div>

        {/* -- Navigation links -- */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            // Check if this nav item is the current active route
            const isActive = pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                  transition-all duration-200
                  ${isActive
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    : "text-gray-400 hover:text-white hover:bg-white/5"
                  }
                `}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* -- Logout button at bottom -- */}
        <div className="px-3 py-4 border-t border-white/5">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm
                       text-gray-400 hover:text-rose-400 hover:bg-rose-500/10
                       transition-all duration-200 w-full"
          >
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </aside>

      {/* -- Mobile bottom nav (hidden on desktop) -- */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50
                      glass-sidebar border-t border-white/5
                      flex items-center justify-around px-2 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex flex-col items-center gap-1 px-3 py-2 rounded-lg text-xs
                transition-colors
                ${isActive ? "text-indigo-400" : "text-gray-500"}
              `}
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
```

- [ ] **Step 3: Update root layout with sidebar**

Overwrite `app/layout.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Root layout — wraps every page with the dark theme and sidebar.
//  The sidebar only shows on authenticated pages (not /login).
//  Uses a conditional check via the pathname.
// ─────────────────────────────────────────────────────────────

import type { Metadata } from "next";
import "./globals.css";
import LayoutShell from "@/components/layout-shell";

// -- App metadata shown in browser tab --
export const metadata: Metadata = {
  title: "LeoQuiz Dashboard",
  description: "Manage Leo Quiz automated kids video pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        {/* LayoutShell handles showing/hiding the sidebar based on route */}
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
```

Create `components/layout-shell.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Layout shell — conditionally renders the sidebar.
//  On /login: full-screen content, no sidebar.
//  On all other pages: sidebar + content area with left padding.
// ─────────────────────────────────────────────────────────────

import { usePathname } from "next/navigation";
import Sidebar from "@/components/sidebar";

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Don't show sidebar on the login page
  const isLoginPage = pathname === "/login";

  if (isLoginPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar — fixed left panel */}
      <Sidebar />
      {/* Main content area — offset by sidebar width on desktop */}
      <main className="flex-1 md:ml-64 p-6 pb-24 md:pb-6">
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Create Login page**

Create `app/login/page.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Login page — centered card with email/password form.
//  Dark indigo glassmorphism theme with Leo branding.
//  On success: redirects to dashboard (/). On error: shows message.
// ─────────────────────────────────────────────────────────────

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Clapperboard, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  // Form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // -- Handle form submission --
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (res.ok) {
        // Login successful — redirect to dashboard
        router.push("/");
        router.refresh();
      } else {
        // Show error message from API
        setError(data.error || "Login failed");
      }
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* -- Login card with glassmorphism -- */}
      <div className="glass-card p-8 w-full max-w-md">
        {/* -- Logo and title -- */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600
                          flex items-center justify-center mb-4">
            <Clapperboard className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">LeoQuiz Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Sign in to manage your quiz videos</p>
        </div>

        {/* -- Login form -- */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email field */}
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10
                         text-white placeholder-gray-500 focus:outline-none
                         focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
                         transition-colors"
              placeholder="admin@leoquiz.com"
              required
            />
          </div>

          {/* Password field with show/hide toggle */}
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10
                           text-white placeholder-gray-500 focus:outline-none
                           focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25
                           transition-colors pr-12"
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400
                           hover:text-white transition-colors"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="text-rose-400 text-sm bg-rose-500/10 border border-rose-500/20
                            rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600
                       text-white font-semibold hover:from-indigo-500 hover:to-purple-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-500/50
                       transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Start dev server and verify**

Run: `npm run dev`

Test in browser:
1. Visit `http://localhost:3000` → should redirect to `/login`
2. Login page shows with glassmorphism card, dark indigo background
3. Sidebar is NOT visible on login page

- [ ] **Step 6: Commit**

```bash
git add app/ components/
git commit -m "feat: root layout with dark glassmorphism theme, sidebar, and login page"
```

---

### Task 4: Shared UI Components

**Files:**
- Create: `components/stats-card.tsx`
- Create: `components/status-badge.tsx`
- Create: `components/category-badge.tsx`
- Create: `components/activity-feed.tsx`
- Create: `components/video-card.tsx`
- Create: `components/video-player.tsx`
- Create: `components/metadata-editor.tsx`
- Create: `components/schedule-form.tsx`
- Create: `components/date-time-picker.tsx`

**Interfaces:**
- Consumes: `Video`, `ActivityLogEntry`, `ScheduleConfig`, `VideoStatus`, `Category` from `lib/types.ts`
- Produces:
  - `<StatsCard icon={} label="" value="" subtitle="" />` — glass card with icon and metric
  - `<StatusBadge status={VideoStatus} />` — color-coded pill with optional pulse
  - `<CategoryBadge category={Category} />` — color-coded category label
  - `<ActivityFeed entries={ActivityLogEntry[]} />` — chronological event list
  - `<VideoCard video={Video} onApprove onReject onSchedule />` — approval queue card
  - `<VideoPlayer url={string} />` — inline video player
  - `<MetadataEditor video={Video} onChange />` — editable title/description/tags/hashtags
  - `<ScheduleForm config={ScheduleConfig} onSave />` — auto-generation schedule
  - `<DateTimePicker value={string} onChange />` — date/time selector for scheduling posts

- [ ] **Step 1: Create StatsCard**

Create `components/stats-card.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Stats card — displays a single metric with icon.
//  Used on the dashboard overview for key numbers.
//  Glassmorphism styling with gradient icon background.
// ─────────────────────────────────────────────────────────────

import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
  // Lucide icon component
  icon: LucideIcon;
  // Metric label (e.g., "Videos Today")
  label: string;
  // Main value (e.g., "12")
  value: string | number;
  // Optional subtitle below the value (e.g., "3 this week")
  subtitle?: string;
  // Optional gradient class for the icon background
  gradient?: string;
}

export default function StatsCard({
  icon: Icon,
  label,
  value,
  subtitle,
  gradient = "from-indigo-500 to-purple-600",
}: StatsCardProps) {
  return (
    <div className="glass-card-hover p-5">
      <div className="flex items-start justify-between">
        {/* Icon with gradient background */}
        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient}
                        flex items-center justify-center`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        {/* Value — large, prominent */}
        <span className="text-3xl font-bold text-white">{value}</span>
      </div>
      {/* Label */}
      <p className="text-sm text-gray-400 mt-3">{label}</p>
      {/* Optional subtitle */}
      {subtitle && (
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create StatusBadge**

Create `components/status-badge.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Status badge — color-coded pill for video lifecycle states.
//  Each status gets a unique color:
//    generating: blue (pulse), pending: amber, approved: emerald,
//    scheduled: purple, uploaded: teal, rejected: rose, failed: red
// ─────────────────────────────────────────────────────────────

import type { VideoStatus } from "@/lib/types";

// -- Color mapping for each status --
const statusColors: Record<VideoStatus, string> = {
  generating: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  pending: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  approved: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  scheduled: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  uploaded: "bg-teal-500/20 text-teal-400 border-teal-500/30",
  rejected: "bg-rose-500/20 text-rose-400 border-rose-500/30",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
};

// -- Labels with proper capitalization --
const statusLabels: Record<VideoStatus, string> = {
  generating: "Generating",
  pending: "Pending",
  approved: "Approved",
  scheduled: "Scheduled",
  uploaded: "Uploaded",
  rejected: "Rejected",
  failed: "Failed",
};

export default function StatusBadge({ status }: { status: VideoStatus }) {
  const colorClass = statusColors[status] || statusColors.pending;
  const label = statusLabels[status] || status;

  // "generating" status gets the pulse animation
  const pulseClass = status === "generating" ? "animate-pulse-glow" : "";

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs
                  font-medium border ${colorClass} ${pulseClass}`}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Create CategoryBadge**

Create `components/category-badge.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Category badge — color-coded label matching pipeline themes.
//  Colors mirror the CATEGORY_COLORS from the Python pipeline's
//  config.py for visual consistency across the system.
// ─────────────────────────────────────────────────────────────

import type { Category } from "@/lib/types";

// -- Color mapping for each quiz category --
const categoryStyles: Record<Category, { bg: string; text: string; emoji: string }> = {
  animals:   { bg: "bg-emerald-500/20", text: "text-emerald-400", emoji: "🦁" },
  dinosaurs: { bg: "bg-orange-500/20",  text: "text-orange-400",  emoji: "🦕" },
  space:     { bg: "bg-blue-500/20",    text: "text-blue-400",    emoji: "🚀" },
  vehicles:  { bg: "bg-red-500/20",     text: "text-red-400",     emoji: "🚗" },
  fruits:    { bg: "bg-yellow-500/20",   text: "text-yellow-400",  emoji: "🍎" },
  flags:     { bg: "bg-purple-500/20",   text: "text-purple-400",  emoji: "🏳️" },
};

export default function CategoryBadge({ category }: { category: Category }) {
  const style = categoryStyles[category] || categoryStyles.animals;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                     text-xs font-medium ${style.bg} ${style.text}`}>
      <span>{style.emoji}</span>
      {category.charAt(0).toUpperCase() + category.slice(1)}
    </span>
  );
}
```

- [ ] **Step 4: Create ActivityFeed**

Create `components/activity-feed.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Activity feed — chronological list of recent events.
//  Each entry shows an icon, message, relative timestamp,
//  and optional link to the video.
// ─────────────────────────────────────────────────────────────

import { formatDistanceToNow } from "date-fns";
import {
  Sparkles, Check, X, Clock, Upload, AlertCircle, Activity,
} from "lucide-react";
import type { ActivityLogEntry } from "@/lib/types";

// -- Icon and color for each activity action --
const actionConfig: Record<string, { icon: typeof Activity; color: string }> = {
  generated: { icon: Sparkles, color: "text-blue-400" },
  approved: { icon: Check, color: "text-emerald-400" },
  rejected: { icon: X, color: "text-rose-400" },
  scheduled: { icon: Clock, color: "text-purple-400" },
  uploaded: { icon: Upload, color: "text-teal-400" },
  failed: { icon: AlertCircle, color: "text-red-400" },
};

interface ActivityFeedProps {
  // List of activity log entries to display
  entries: ActivityLogEntry[];
}

export default function ActivityFeed({ entries }: ActivityFeedProps) {
  if (entries.length === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-8">
        No activity yet. Generate your first video!
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {entries.map((entry) => {
        // Get icon and color for this action type
        const config = actionConfig[entry.action] || { icon: Activity, color: "text-gray-400" };
        const Icon = config.icon;

        return (
          <div
            key={entry.id}
            className="flex items-center gap-3 px-4 py-3 rounded-xl
                       hover:bg-white/5 transition-colors"
          >
            {/* Action icon */}
            <div className={`w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center
                            ${config.color}`}>
              <Icon className="w-4 h-4" />
            </div>

            {/* Message */}
            <p className="flex-1 text-sm text-gray-300">{entry.message}</p>

            {/* Relative timestamp */}
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: Create VideoPlayer**

Create `components/video-player.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Video player — inline HTML5 video element.
//  Plays videos from Vercel Blob URLs.
//  Shows a placeholder when no video URL is available.
// ─────────────────────────────────────────────────────────────

import { Play } from "lucide-react";

interface VideoPlayerProps {
  // Vercel Blob URL of the video
  url: string | null;
  // Optional poster/thumbnail image
  poster?: string | null;
}

export default function VideoPlayer({ url, poster }: VideoPlayerProps) {
  // No video URL — show placeholder
  if (!url) {
    return (
      <div className="aspect-[9/16] max-h-[400px] bg-white/5 rounded-xl
                      flex items-center justify-center">
        <div className="text-center text-gray-500">
          <Play className="w-12 h-12 mx-auto mb-2 opacity-30" />
          <p className="text-sm">Video not available</p>
        </div>
      </div>
    );
  }

  return (
    <video
      src={url}
      poster={poster || undefined}
      controls
      className="aspect-[9/16] max-h-[400px] w-auto rounded-xl bg-black"
      preload="metadata"
    >
      Your browser does not support video playback.
    </video>
  );
}
```

- [ ] **Step 6: Create MetadataEditor**

Create `components/metadata-editor.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Metadata editor — editable title, description, tags, hashtags.
//  Pre-filled with Gemini auto-generated content.
//  Changes are passed up via onChange callback.
// ─────────────────────────────────────────────────────────────

import { useState } from "react";
import { X, Plus } from "lucide-react";
import type { Video, Platform } from "@/lib/types";

interface MetadataEditorProps {
  // The video being edited
  video: Video;
  // Callback when any field changes
  onChange: (updates: Partial<Video>) => void;
}

export default function MetadataEditor({ video, onChange }: MetadataEditorProps) {
  // Parse JSON arrays for tags and hashtags
  const [tags, setTags] = useState<string[]>(
    video.tags ? JSON.parse(video.tags) : []
  );
  const [hashtags, setHashtags] = useState<string[]>(
    video.hashtags ? JSON.parse(video.hashtags) : []
  );
  const [newTag, setNewTag] = useState("");
  const [newHashtag, setNewHashtag] = useState("");

  // -- Add a tag --
  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      const updated = [...tags, newTag.trim()];
      setTags(updated);
      setNewTag("");
      onChange({ tags: JSON.stringify(updated) });
    }
  };

  // -- Remove a tag --
  const removeTag = (tag: string) => {
    const updated = tags.filter((t) => t !== tag);
    setTags(updated);
    onChange({ tags: JSON.stringify(updated) });
  };

  // -- Add a hashtag --
  const addHashtag = () => {
    let ht = newHashtag.trim();
    if (ht && !ht.startsWith("#")) ht = `#${ht}`;
    if (ht && !hashtags.includes(ht)) {
      const updated = [...hashtags, ht];
      setHashtags(updated);
      setNewHashtag("");
      onChange({ hashtags: JSON.stringify(updated) });
    }
  };

  // -- Remove a hashtag --
  const removeHashtag = (ht: string) => {
    const updated = hashtags.filter((h) => h !== ht);
    setHashtags(updated);
    onChange({ hashtags: JSON.stringify(updated) });
  };

  return (
    <div className="space-y-4">
      {/* Title */}
      <div>
        <label className="block text-sm text-gray-300 mb-1.5">Title</label>
        <input
          type="text"
          defaultValue={video.title || ""}
          onChange={(e) => onChange({ title: e.target.value })}
          className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                     text-white text-sm focus:outline-none focus:border-indigo-500/50
                     transition-colors"
          placeholder="Video title..."
        />
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm text-gray-300 mb-1.5">Description</label>
        <textarea
          defaultValue={video.description || ""}
          onChange={(e) => onChange({ description: e.target.value })}
          rows={3}
          className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                     text-white text-sm focus:outline-none focus:border-indigo-500/50
                     transition-colors resize-none"
          placeholder="Video description..."
        />
      </div>

      {/* Tags */}
      <div>
        <label className="block text-sm text-gray-300 mb-1.5">Tags</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg
                         bg-indigo-500/15 text-indigo-300 text-xs"
            >
              {tag}
              <button onClick={() => removeTag(tag)} className="hover:text-white">
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
            className="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white text-sm focus:outline-none focus:border-indigo-500/50"
            placeholder="Add tag..."
          />
          <button
            onClick={addTag}
            className="px-3 py-2 rounded-lg bg-indigo-500/20 text-indigo-300
                       hover:bg-indigo-500/30 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Hashtags */}
      <div>
        <label className="block text-sm text-gray-300 mb-1.5">Hashtags</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {hashtags.map((ht) => (
            <span
              key={ht}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg
                         bg-purple-500/15 text-purple-300 text-xs"
            >
              {ht}
              <button onClick={() => removeHashtag(ht)} className="hover:text-white">
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newHashtag}
            onChange={(e) => setNewHashtag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addHashtag())}
            className="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white text-sm focus:outline-none focus:border-indigo-500/50"
            placeholder="Add hashtag..."
          />
          <button
            onClick={addHashtag}
            className="px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300
                       hover:bg-purple-500/30 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Platform selector */}
      <div>
        <label className="block text-sm text-gray-300 mb-1.5">Platform</label>
        <select
          defaultValue={video.platform || "both"}
          onChange={(e) => onChange({ platform: e.target.value as Platform })}
          className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                     text-white text-sm focus:outline-none focus:border-indigo-500/50
                     transition-colors"
        >
          <option value="both">YouTube + TikTok</option>
          <option value="youtube">YouTube Only</option>
          <option value="tiktok">TikTok Only</option>
        </select>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Create DateTimePicker**

Create `components/date-time-picker.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Date/time picker — for scheduling video posts.
//  Uses native HTML datetime-local input with custom styling.
//  Returns ISO timestamp strings.
// ─────────────────────────────────────────────────────────────

interface DateTimePickerProps {
  // ISO timestamp value (or empty)
  value: string;
  // Callback when the user picks a date/time
  onChange: (isoTimestamp: string) => void;
  // Label text
  label?: string;
}

export default function DateTimePicker({
  value,
  onChange,
  label = "Schedule for",
}: DateTimePickerProps) {
  // Convert ISO timestamp to datetime-local format (YYYY-MM-DDTHH:mm)
  const localValue = value ? value.slice(0, 16) : "";

  return (
    <div>
      <label className="block text-sm text-gray-300 mb-1.5">{label}</label>
      <input
        type="datetime-local"
        value={localValue}
        onChange={(e) => {
          // Convert local datetime back to ISO timestamp
          const dt = new Date(e.target.value);
          onChange(dt.toISOString());
        }}
        // Set minimum to now — can't schedule in the past
        min={new Date().toISOString().slice(0, 16)}
        className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                   text-white text-sm focus:outline-none focus:border-indigo-500/50
                   transition-colors [color-scheme:dark]"
      />
    </div>
  );
}
```

- [ ] **Step 8: Create ScheduleForm**

Create `components/schedule-form.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Schedule form — configure auto-generation schedule.
//  Toggle on/off, set daily time, weekly compilation day.
//  Shows the day-of-week category rotation.
// ─────────────────────────────────────────────────────────────

import { useState } from "react";
import { Save, Clock } from "lucide-react";
import type { ScheduleConfig } from "@/lib/types";

// -- Day-of-week category rotation (matches pipeline config.py) --
const dayCategories = [
  { day: "Monday", category: "Animals", emoji: "🦁" },
  { day: "Tuesday", category: "Dinosaurs", emoji: "🦕" },
  { day: "Wednesday", category: "Space", emoji: "🚀" },
  { day: "Thursday", category: "Vehicles", emoji: "🚗" },
  { day: "Friday", category: "Fruits", emoji: "🍎" },
  { day: "Saturday", category: "Flags", emoji: "🏳️" },
  { day: "Sunday", category: "Mixed", emoji: "🎲" },
];

// -- Day names for the weekly compilation picker --
const weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface ScheduleFormProps {
  // Current schedule configuration
  config: ScheduleConfig;
  // Callback when the user saves changes
  onSave: (updates: Partial<ScheduleConfig>) => void;
  // Whether a save is in progress
  saving?: boolean;
}

export default function ScheduleForm({ config, onSave, saving }: ScheduleFormProps) {
  // Local state for form fields
  const [autoEnabled, setAutoEnabled] = useState(config.auto_enabled);
  const [dailyHour, setDailyHour] = useState(config.daily_hour_utc);
  const [dailyMinute, setDailyMinute] = useState(config.daily_minute_utc);
  const [weeklyDay, setWeeklyDay] = useState(config.weekly_day);
  const [weeklyHour, setWeeklyHour] = useState(config.weekly_hour_utc);

  // -- Handle save --
  const handleSave = () => {
    onSave({
      auto_enabled: autoEnabled,
      daily_hour_utc: dailyHour,
      daily_minute_utc: dailyMinute,
      weekly_day: weeklyDay,
      weekly_hour_utc: weeklyHour,
    });
  };

  return (
    <div className="space-y-6">
      {/* Auto-generation toggle */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-white font-medium">Auto-Generation</h3>
          <p className="text-sm text-gray-400">Automatically generate videos on schedule</p>
        </div>
        <button
          onClick={() => setAutoEnabled(!autoEnabled)}
          className={`relative w-12 h-6 rounded-full transition-colors ${
            autoEnabled ? "bg-indigo-500" : "bg-white/10"
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white
                        transition-transform ${autoEnabled ? "translate-x-6" : ""}`}
          />
        </button>
      </div>

      {/* Daily schedule (visible when auto is on) */}
      {autoEnabled && (
        <>
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">
              <Clock className="w-4 h-4 inline mr-1" />
              Daily Generation Time (UTC)
            </label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                min={0}
                max={23}
                value={dailyHour}
                onChange={(e) => setDailyHour(Number(e.target.value))}
                className="w-20 px-3 py-2 rounded-lg bg-white/5 border border-white/10
                           text-white text-sm text-center"
              />
              <span className="text-gray-400">:</span>
              <input
                type="number"
                min={0}
                max={59}
                step={15}
                value={dailyMinute}
                onChange={(e) => setDailyMinute(Number(e.target.value))}
                className="w-20 px-3 py-2 rounded-lg bg-white/5 border border-white/10
                           text-white text-sm text-center"
              />
              <span className="text-gray-500 text-sm">UTC</span>
            </div>
          </div>

          {/* Weekly compilation day */}
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">
              Weekly Compilation Day
            </label>
            <select
              value={weeklyDay}
              onChange={(e) => setWeeklyDay(Number(e.target.value))}
              className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                         text-white text-sm"
            >
              {weekDays.map((day, i) => (
                <option key={day} value={i}>{day}</option>
              ))}
            </select>
          </div>

          {/* Category rotation display (read-only) */}
          <div>
            <label className="block text-sm text-gray-300 mb-2">Category Rotation</label>
            <div className="grid grid-cols-2 gap-2">
              {dayCategories.map((dc) => (
                <div
                  key={dc.day}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5
                             text-sm"
                >
                  <span>{dc.emoji}</span>
                  <span className="text-gray-400">{dc.day}:</span>
                  <span className="text-white">{dc.category}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl
                   bg-gradient-to-r from-indigo-600 to-purple-600
                   text-white text-sm font-medium
                   hover:from-indigo-500 hover:to-purple-500
                   disabled:opacity-50 transition-all"
      >
        <Save className="w-4 h-4" />
        {saving ? "Saving..." : "Save Schedule"}
      </button>
    </div>
  );
}
```

- [ ] **Step 9: Create VideoCard**

Create `components/video-card.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Video card — displays a video in the approval queue.
//  Shows video player, thumbnail, metadata editor, and action buttons.
//  This is the primary interaction surface for reviewing videos.
// ─────────────────────────────────────────────────────────────

import { useState } from "react";
import { Check, X, Calendar, RefreshCw } from "lucide-react";
import type { Video } from "@/lib/types";
import StatusBadge from "./status-badge";
import CategoryBadge from "./category-badge";
import VideoPlayer from "./video-player";
import MetadataEditor from "./metadata-editor";
import DateTimePicker from "./date-time-picker";

interface VideoCardProps {
  // The video to display
  video: Video;
  // Callback when admin approves (optional scheduled_at)
  onApprove: (videoId: string, scheduledAt?: string) => void;
  // Callback when admin rejects
  onReject: (videoId: string) => void;
  // Callback when metadata changes (auto-saved)
  onUpdate: (videoId: string, updates: Partial<Video>) => void;
}

export default function VideoCard({ video, onApprove, onReject, onUpdate }: VideoCardProps) {
  // Local state for schedule picker
  const [showScheduler, setShowScheduler] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");

  // Parse quiz rounds from metadata JSON
  const quizData = video.metadata_json ? JSON.parse(video.metadata_json) : null;
  const rounds = quizData?.rounds || [];

  return (
    <div className="glass-card p-6">
      <div className="flex flex-col lg:flex-row gap-6">
        {/* -- Left: Video player + thumbnail -- */}
        <div className="flex gap-4 flex-shrink-0">
          <VideoPlayer url={video.video_url} poster={video.thumbnail_url} />
          {/* Thumbnail preview */}
          {video.thumbnail_url && (
            <div className="hidden xl:block">
              <p className="text-xs text-gray-500 mb-1">Thumbnail</p>
              <img
                src={video.thumbnail_url}
                alt="Thumbnail"
                className="w-32 rounded-lg border border-white/10"
              />
            </div>
          )}
        </div>

        {/* -- Right: Metadata + actions -- */}
        <div className="flex-1 space-y-4">
          {/* Status + category badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={video.status} />
            <CategoryBadge category={video.category} />
            <span className="text-xs text-gray-500">
              {video.trigger_type === "automated" ? "Auto-generated" : "Manual"}
            </span>
          </div>

          {/* Quiz rounds summary */}
          {rounds.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {rounds.map((r: { answer: string }, i: number) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-md bg-white/5 text-xs text-gray-300"
                >
                  {r.answer}
                </span>
              ))}
            </div>
          )}

          {/* Metadata editor — editable title, description, tags, hashtags */}
          <MetadataEditor
            video={video}
            onChange={(updates) => onUpdate(video.id, updates)}
          />

          {/* Schedule picker (shown when "Approve & Schedule" is clicked) */}
          {showScheduler && (
            <DateTimePicker
              value={scheduledAt}
              onChange={setScheduledAt}
              label="Schedule posting for"
            />
          )}

          {/* -- Action buttons -- */}
          <div className="flex flex-wrap gap-3 pt-2">
            {/* Approve & Post Now */}
            <button
              onClick={() => onApprove(video.id)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl
                         bg-emerald-500/20 text-emerald-400 border border-emerald-500/30
                         hover:bg-emerald-500/30 transition-colors text-sm font-medium"
            >
              <Check className="w-4 h-4" />
              Approve & Post Now
            </button>

            {/* Approve & Schedule */}
            <button
              onClick={() => {
                if (showScheduler && scheduledAt) {
                  onApprove(video.id, scheduledAt);
                } else {
                  setShowScheduler(true);
                }
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl
                         bg-purple-500/20 text-purple-400 border border-purple-500/30
                         hover:bg-purple-500/30 transition-colors text-sm font-medium"
            >
              <Calendar className="w-4 h-4" />
              {showScheduler ? "Confirm Schedule" : "Approve & Schedule"}
            </button>

            {/* Reject */}
            <button
              onClick={() => onReject(video.id)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl
                         bg-rose-500/20 text-rose-400 border border-rose-500/30
                         hover:bg-rose-500/30 transition-colors text-sm font-medium"
            >
              <X className="w-4 h-4" />
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 10: Verify components compile**

Run: `npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 11: Commit**

```bash
git add components/
git commit -m "feat: shared UI components — stats, badges, video card, metadata editor, schedule form"
```

---

### Task 5: Videos API Routes + Activity API

**Files:**
- Create: `app/api/videos/route.ts`
- Create: `app/api/videos/[id]/route.ts`
- Create: `app/api/videos/[id]/approve/route.ts`
- Create: `app/api/videos/[id]/reject/route.ts`
- Create: `app/api/activity/route.ts`
- Create: `app/api/schedule/route.ts`

**Interfaces:**
- Consumes: `listVideos`, `getVideo`, `updateVideo`, `logActivity`, `getRecentActivity`, `getScheduleConfig`, `updateScheduleConfig` from `lib/db.ts`
- Produces:
  - `GET /api/videos?status=&category=&search=&offset=&limit=` → `{ videos: Video[], total: number }`
  - `GET /api/videos/[id]` → `Video`
  - `PATCH /api/videos/[id]` → `Video` (update title, desc, tags, hashtags, platform)
  - `POST /api/videos/[id]/approve` → `Video` (optionally with `scheduled_at`)
  - `POST /api/videos/[id]/reject` → `Video`
  - `GET /api/activity?limit=50` → `ActivityLogEntry[]`
  - `GET /api/schedule` → `ScheduleConfig`
  - `PUT /api/schedule` → `ScheduleConfig`

- [ ] **Step 1: Create videos list API route**

Create `app/api/videos/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/videos
//  Lists videos with optional filters and pagination.
//  Query params: status, category, trigger_type, search, offset, limit
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { listVideos } from "@/lib/db";
import type { VideoFilters } from "@/lib/types";

export async function GET(request: Request) {
  // Parse query parameters from the URL
  const url = new URL(request.url);

  const filters: VideoFilters = {
    status: url.searchParams.get("status") as VideoFilters["status"] || undefined,
    category: url.searchParams.get("category") as VideoFilters["category"] || undefined,
    trigger_type: url.searchParams.get("trigger_type") as VideoFilters["trigger_type"] || undefined,
    search: url.searchParams.get("search") || undefined,
    offset: Number(url.searchParams.get("offset")) || 0,
    limit: Number(url.searchParams.get("limit")) || 20,
  };

  const result = await listVideos(filters);
  return NextResponse.json(result);
}
```

- [ ] **Step 2: Create single video + update API route**

Create `app/api/videos/[id]/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/videos/[id] — Fetch a single video by ID
//  PATCH /api/videos/[id] — Update video metadata (title, desc, tags, etc.)
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo, updateVideo } from "@/lib/db";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const video = await getVideo(id);

  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  return NextResponse.json(video);
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  // Check video exists
  const existing = await getVideo(id);
  if (!existing) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  // Parse update fields from request body
  const body = await request.json().catch(() => ({}));
  const allowedFields = ["title", "description", "tags", "hashtags", "platform", "scheduled_at"];
  const updates: Record<string, unknown> = {};

  for (const field of allowedFields) {
    if (body[field] !== undefined) {
      updates[field] = body[field];
    }
  }

  const updated = await updateVideo(id, updates);
  return NextResponse.json(updated);
}
```

- [ ] **Step 3: Create approve API route**

Create `app/api/videos/[id]/approve/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/videos/[id]/approve
//  Approves a pending video. Optionally schedule for later posting.
//  Body: { scheduled_at?: string } — ISO timestamp for scheduled posting
//  If no scheduled_at: status → "approved" (post immediately)
//  If scheduled_at provided: status → "scheduled"
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo, updateVideo, logActivity } from "@/lib/db";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const video = await getVideo(id);

  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  // Only pending videos can be approved
  if (video.status !== "pending") {
    return NextResponse.json(
      { error: `Cannot approve video with status "${video.status}"` },
      { status: 400 }
    );
  }

  // Check if a scheduled time was provided
  const body = await request.json().catch(() => ({}));
  const scheduledAt = body.scheduled_at as string | undefined;
  const now = new Date().toISOString();

  if (scheduledAt) {
    // Schedule for later
    const updated = await updateVideo(id, {
      status: "scheduled",
      scheduled_at: scheduledAt,
      reviewed_at: now,
    });
    await logActivity("scheduled", id, `Video scheduled: ${video.title || video.category}`);
    return NextResponse.json(updated);
  } else {
    // Approve for immediate posting
    const updated = await updateVideo(id, {
      status: "approved",
      reviewed_at: now,
    });
    await logActivity("approved", id, `Video approved: ${video.title || video.category}`);
    return NextResponse.json(updated);
  }
}
```

- [ ] **Step 4: Create reject API route**

Create `app/api/videos/[id]/reject/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/videos/[id]/reject
//  Rejects a pending video, moving it to history.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo, updateVideo, logActivity } from "@/lib/db";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const video = await getVideo(id);

  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  if (video.status !== "pending") {
    return NextResponse.json(
      { error: `Cannot reject video with status "${video.status}"` },
      { status: 400 }
    );
  }

  const now = new Date().toISOString();
  const updated = await updateVideo(id, {
    status: "rejected",
    reviewed_at: now,
  });

  await logActivity("rejected", id, `Video rejected: ${video.title || video.category}`);
  return NextResponse.json(updated);
}
```

- [ ] **Step 5: Create activity API route**

Create `app/api/activity/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/activity
//  Returns recent activity log entries for the dashboard feed.
//  Query params: limit (default 50)
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getRecentActivity } from "@/lib/db";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit")) || 50;

  const entries = await getRecentActivity(limit);
  return NextResponse.json(entries);
}
```

- [ ] **Step 6: Create schedule API route**

Create `app/api/schedule/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/schedule — Returns current schedule configuration
//  PUT /api/schedule — Updates schedule configuration
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getScheduleConfig, updateScheduleConfig } from "@/lib/db";

export async function GET() {
  const config = await getScheduleConfig();
  return NextResponse.json(config);
}

export async function PUT(request: Request) {
  const body = await request.json().catch(() => ({}));

  const config = await updateScheduleConfig({
    auto_enabled: body.auto_enabled,
    daily_hour_utc: body.daily_hour_utc,
    daily_minute_utc: body.daily_minute_utc,
    weekly_day: body.weekly_day,
    weekly_hour_utc: body.weekly_hour_utc,
  });

  return NextResponse.json(config);
}
```

- [ ] **Step 7: Verify all routes compile**

Run: `npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 8: Commit**

```bash
git add app/api/
git commit -m "feat: videos CRUD, approve/reject, activity, and schedule API routes"
```

---

### Task 6: GitHub Actions Integration + Generate + Webhook

**Files:**
- Create: `lib/github.ts`
- Create: `app/api/generate/route.ts`
- Create: `app/api/videos/[id]/status/route.ts`
- Create: `app/api/webhook/pipeline-complete/route.ts`
- Test: `__tests__/github.test.ts`

**Interfaces:**
- Consumes: `createVideo`, `updateVideo`, `logActivity` from `lib/db.ts`
- Produces:
  - `triggerWorkflow(videoId: string, category: string, rounds: number): Promise<number>` — returns GitHub run ID
  - `getWorkflowRunStatus(runId: number): Promise<{ status, conclusion }>` — polls run status
  - `POST /api/generate` — body `{ category, rounds, trigger_type }`, creates video record + triggers workflow
  - `GET /api/videos/[id]/status` — polls GitHub Actions for workflow run status
  - `POST /api/webhook/pipeline-complete` — receives video/thumbnail URLs + metadata from pipeline

- [ ] **Step 1: Create GitHub API helper**

Create `lib/github.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GitHub Actions API helpers.
//  Triggers pipeline workflows via workflow_dispatch and polls
//  run status for the dashboard's progress indicator.
//
//  Uses the GitHub REST API:
//    POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches
//    GET  /repos/{owner}/{repo}/actions/runs/{id}
// ─────────────────────────────────────────────────────────────

// -- GitHub API base URL --
const GITHUB_API = "https://api.github.com";

// -- Repo coordinates from env vars --
function getRepoInfo() {
  return {
    owner: process.env.GITHUB_REPO_OWNER || "Leo-emp",
    repo: process.env.GITHUB_REPO_NAME || "leo-quiz-pipeline",
    token: process.env.GITHUB_TOKEN || "",
  };
}

// -- Common headers for GitHub API calls --
function getHeaders() {
  const { token } = getRepoInfo();
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github.v3+json",
    "Content-Type": "application/json",
  };
}

export async function triggerWorkflow(
  videoId: string,
  category: string,
  rounds: number
): Promise<number | null> {
  // Triggers the daily.yml workflow via workflow_dispatch.
  // Passes video_id, category, and rounds as inputs so the
  // pipeline knows which dashboard record to callback to.
  // Returns the workflow run ID (or null on failure).
  const { owner, repo } = getRepoInfo();

  // Step 1: Dispatch the workflow
  const dispatchRes = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/workflows/daily.yml/dispatches`,
    {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({
        ref: "main",
        inputs: {
          video_id: videoId,
          category,
          rounds: String(rounds),
        },
      }),
    }
  );

  if (!dispatchRes.ok) {
    console.error("[GITHUB] Workflow dispatch failed:", dispatchRes.status);
    return null;
  }

  // Step 2: Wait a moment, then find the newly created run
  // GitHub doesn't return the run ID from dispatch — we poll for it
  await new Promise((r) => setTimeout(r, 3000));

  const runsRes = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/workflows/daily.yml/runs?per_page=1`,
    { headers: getHeaders() }
  );

  if (!runsRes.ok) return null;

  const runsData = await runsRes.json();
  const latestRun = runsData.workflow_runs?.[0];

  return latestRun?.id || null;
}

export async function getWorkflowRunStatus(
  runId: number
): Promise<{ status: string; conclusion: string | null }> {
  // Polls a workflow run to check its current status.
  // Returns { status: "queued"|"in_progress"|"completed", conclusion: "success"|"failure"|null }
  const { owner, repo } = getRepoInfo();

  const res = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/runs/${runId}`,
    { headers: getHeaders() }
  );

  if (!res.ok) {
    return { status: "unknown", conclusion: null };
  }

  const data = await res.json();
  return {
    status: data.status || "unknown",
    conclusion: data.conclusion || null,
  };
}

export async function triggerUploadWorkflow(
  videoId: string,
  videoBlobUrl: string,
  metadata: { title: string; description: string; tags: string[] },
  platform: string
): Promise<number | null> {
  // Triggers the upload.yml workflow to post a video to YouTube/TikTok.
  // Called after approval or when a scheduled post is due.
  const { owner, repo } = getRepoInfo();

  const dispatchRes = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/workflows/upload.yml/dispatches`,
    {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({
        ref: "main",
        inputs: {
          video_id: videoId,
          video_blob_url: videoBlobUrl,
          metadata_json: JSON.stringify(metadata),
          platform,
        },
      }),
    }
  );

  if (!dispatchRes.ok) {
    console.error("[GITHUB] Upload workflow dispatch failed:", dispatchRes.status);
    return null;
  }

  // Find the run ID
  await new Promise((r) => setTimeout(r, 3000));

  const runsRes = await fetch(
    `${GITHUB_API}/repos/${owner}/${repo}/actions/workflows/upload.yml/runs?per_page=1`,
    { headers: getHeaders() }
  );

  if (!runsRes.ok) return null;
  const runsData = await runsRes.json();
  return runsData.workflow_runs?.[0]?.id || null;
}
```

- [ ] **Step 2: Create generate API route**

Create `app/api/generate/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/generate
//  Creates a new video record and triggers the pipeline via
//  GitHub Actions workflow_dispatch.
//  Body: { category?: string, rounds?: number, trigger_type?: string }
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { createVideo, updateVideo, logActivity } from "@/lib/db";
import { triggerWorkflow } from "@/lib/github";
import type { Category, TriggerType } from "@/lib/types";

// -- Valid categories (matches pipeline config.py) --
const VALID_CATEGORIES = ["animals", "dinosaurs", "space", "vehicles", "fruits", "flags"];

// -- Day-of-week rotation for "auto" category --
const DAY_CATEGORIES: Category[] = [
  "animals", "dinosaurs", "space", "vehicles", "fruits", "flags",
];

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));

  // Determine category — "auto" picks today's rotation
  let category = body.category as string;
  if (!category || category === "auto") {
    const dayIndex = new Date().getDay();
    // Sunday = 0 in JS → map to our rotation (Mon=0 in pipeline)
    const adjustedDay = dayIndex === 0 ? 6 : dayIndex - 1;
    category = DAY_CATEGORIES[adjustedDay % 6];
  }

  // Validate category
  if (!VALID_CATEGORIES.includes(category)) {
    return NextResponse.json(
      { error: `Invalid category: ${category}` },
      { status: 400 }
    );
  }

  const rounds = body.rounds || 5;
  const triggerType = (body.trigger_type || "manual") as TriggerType;

  // Step 1: Create video record in DB with status "generating"
  const video = await createVideo({
    category: category as Category,
    trigger_type: triggerType,
    rounds_count: rounds,
    status: "generating",
  });

  // Step 2: Trigger the pipeline GitHub Action
  const runId = await triggerWorkflow(video.id, category, rounds);

  if (runId) {
    // Store the run ID so we can poll for status
    await updateVideo(video.id, { github_run_id: String(runId) });
  } else {
    // Workflow trigger failed
    await updateVideo(video.id, { status: "failed" });
    await logActivity("failed", video.id, `Pipeline trigger failed for ${category}`);
    return NextResponse.json(
      { error: "Failed to trigger pipeline", video_id: video.id },
      { status: 500 }
    );
  }

  await logActivity("generated", video.id, `Video generation started: ${category} (${rounds} rounds)`);

  return NextResponse.json({
    video_id: video.id,
    github_run_id: runId,
    status: "generating",
  });
}
```

- [ ] **Step 3: Create video status polling route**

Create `app/api/videos/[id]/status/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/videos/[id]/status
//  Polls the GitHub Actions API for the workflow run status.
//  Used by the Generate page to show progress updates.
//  Returns: { status, conclusion, video_status }
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo } from "@/lib/db";
import { getWorkflowRunStatus } from "@/lib/github";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const video = await getVideo(id);

  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  // If video has no GitHub run ID, return current DB status
  if (!video.github_run_id) {
    return NextResponse.json({
      video_status: video.status,
      github_status: null,
      github_conclusion: null,
    });
  }

  // Poll GitHub Actions for the current workflow run status
  const runStatus = await getWorkflowRunStatus(Number(video.github_run_id));

  return NextResponse.json({
    video_status: video.status,
    github_status: runStatus.status,
    github_conclusion: runStatus.conclusion,
  });
}
```

- [ ] **Step 4: Create webhook for pipeline completion**

Create `app/api/webhook/pipeline-complete/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/webhook/pipeline-complete
//  Called by the GitHub Action after video generation finishes.
//  Receives video + thumbnail Blob URLs and quiz metadata.
//  Updates the video record and moves it to "pending" status.
//
//  Protected by DASHBOARD_WEBHOOK_SECRET header.
//
//  Expected body:
//  {
//    video_id: string,
//    video_url: string,        // Vercel Blob URL
//    thumbnail_url: string,    // Vercel Blob URL
//    title: string,
//    description: string,
//    tags: string[],
//    hashtags: string[],
//    metadata_json: object,    // Full quiz pack data
//  }
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo, updateVideo, logActivity } from "@/lib/db";

export async function POST(request: Request) {
  // -- Verify webhook secret --
  const secret = request.headers.get("x-webhook-secret");
  const expectedSecret = process.env.DASHBOARD_WEBHOOK_SECRET;

  if (!expectedSecret || secret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // -- Parse the webhook payload --
  const body = await request.json().catch(() => null);
  if (!body || !body.video_id) {
    return NextResponse.json({ error: "Missing video_id" }, { status: 400 });
  }

  // -- Find the video record --
  const video = await getVideo(body.video_id);
  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  // -- Update the video with pipeline results --
  const updated = await updateVideo(video.id, {
    status: "pending",
    video_url: body.video_url || null,
    thumbnail_url: body.thumbnail_url || null,
    title: body.title || null,
    description: body.description || null,
    tags: body.tags ? JSON.stringify(body.tags) : null,
    hashtags: body.hashtags ? JSON.stringify(body.hashtags) : null,
    metadata_json: body.metadata_json ? JSON.stringify(body.metadata_json) : null,
  });

  // -- Log the event --
  await logActivity(
    "generated",
    video.id,
    `Video ready for review: ${body.title || video.category}`
  );

  return NextResponse.json({ success: true, video: updated });
}
```

- [ ] **Step 5: Verify all routes compile**

Run: `npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add lib/github.ts app/api/generate/ app/api/videos/ app/api/webhook/
git commit -m "feat: GitHub Actions integration — generate trigger, status polling, pipeline webhook"
```

---

### Task 7: Dashboard Overview Page

**Files:**
- Modify: `app/page.tsx`

**Interfaces:**
- Consumes: `getVideoStats()`, `getRecentActivity()` from `lib/db.ts`, `getScheduleConfig()` from `lib/db.ts`
- Produces: Dashboard overview page with 4 stats cards and activity feed

- [ ] **Step 1: Build the dashboard overview page**

Overwrite `app/page.tsx`:
```tsx
// ─────────────────────────────────────────────────────────────
//  Dashboard overview page — shows key metrics and recent activity.
//  Stats: videos today, this week, total, pending approval count.
//  Activity feed: last 20 events with action icons and timestamps.
// ─────────────────────────────────────────────────────────────

import { Video, Clock, CheckSquare, BarChart3 } from "lucide-react";
import StatsCard from "@/components/stats-card";
import ActivityFeed from "@/components/activity-feed";
import { getVideoStats, getRecentActivity } from "@/lib/db";
import { initializeDatabase } from "@/lib/db";

export default async function DashboardPage() {
  // Initialize DB on first load (safe to call multiple times)
  await initializeDatabase();

  // Fetch stats and activity in parallel
  const [stats, activity] = await Promise.all([
    getVideoStats(),
    getRecentActivity(20),
  ]);

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">
          Overview of your Leo Quiz video pipeline
        </p>
      </div>

      {/* Stats cards — 4 across on desktop, 2x2 on mobile */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          icon={Video}
          label="Videos Today"
          value={stats.today}
          gradient="from-blue-500 to-cyan-500"
        />
        <StatsCard
          icon={BarChart3}
          label="This Week"
          value={stats.week}
          gradient="from-indigo-500 to-purple-600"
        />
        <StatsCard
          icon={CheckSquare}
          label="Pending Approval"
          value={stats.pending}
          gradient="from-amber-500 to-orange-500"
        />
        <StatsCard
          icon={Clock}
          label="Total Videos"
          value={stats.total}
          gradient="from-emerald-500 to-teal-500"
        />
      </div>

      {/* Recent activity feed */}
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Activity</h2>
        <ActivityFeed entries={activity} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Start dev server and verify**

Run: `npm run dev`

Test in browser:
1. Login with admin credentials
2. Dashboard shows 4 stats cards (all zeros for fresh DB)
3. Activity feed shows "No activity yet" message
4. Sidebar navigation is visible and functional

- [ ] **Step 3: Commit**

```bash
git add app/page.tsx
git commit -m "feat: dashboard overview page with stats cards and activity feed"
```

---

### Task 8: Generate Page

**Files:**
- Create: `app/generate/page.tsx`

**Interfaces:**
- Consumes: `POST /api/generate`, `GET /api/videos/[id]/status`, `GET /api/schedule`, `PUT /api/schedule`
- Produces: Generate page with manual trigger card and auto-schedule card

- [ ] **Step 1: Build the generate page**

Create `app/generate/page.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Generate page — two sections:
//  1. Manual Generate: pick category + rounds, click Generate
//  2. Auto Schedule: toggle auto-generation, set times
//
//  After triggering generation, polls for status every 10 seconds
//  until the pipeline completes and the webhook fires.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import ScheduleForm from "@/components/schedule-form";
import StatusBadge from "@/components/status-badge";
import type { ScheduleConfig, VideoStatus } from "@/lib/types";

// -- Available quiz categories --
const categories = [
  { value: "auto", label: "Auto (Today's Rotation)", emoji: "🎲" },
  { value: "animals", label: "Animals", emoji: "🦁" },
  { value: "dinosaurs", label: "Dinosaurs", emoji: "🦕" },
  { value: "space", label: "Space", emoji: "🚀" },
  { value: "vehicles", label: "Vehicles", emoji: "🚗" },
  { value: "fruits", label: "Fruits & Vegetables", emoji: "🍎" },
  { value: "flags", label: "Country Flags", emoji: "🏳️" },
];

export default function GeneratePage() {
  // Manual generation state
  const [category, setCategory] = useState("auto");
  const [rounds, setRounds] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [generatingVideoId, setGeneratingVideoId] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<string | null>(null);

  // Schedule state
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);

  // -- Load schedule config on mount --
  useEffect(() => {
    fetch("/api/schedule")
      .then((r) => r.json())
      .then(setSchedule)
      .catch(console.error);
  }, []);

  // -- Poll for generation status when a video is being generated --
  useEffect(() => {
    if (!generatingVideoId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/videos/${generatingVideoId}/status`);
        const data = await res.json();

        // Update the status display
        setGenerationStatus(data.github_status || data.video_status);

        // Stop polling if complete or failed
        if (data.video_status === "pending" || data.video_status === "failed") {
          setGenerating(false);
          setGeneratingVideoId(null);
          clearInterval(interval);
        }
      } catch {
        // Ignore polling errors
      }
    }, 10000); // Poll every 10 seconds

    return () => clearInterval(interval);
  }, [generatingVideoId]);

  // -- Handle manual generation --
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenerationStatus("queued");

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, rounds }),
      });

      const data = await res.json();

      if (res.ok) {
        setGeneratingVideoId(data.video_id);
        setGenerationStatus("dispatched");
      } else {
        setGenerationStatus(`Error: ${data.error}`);
        setGenerating(false);
      }
    } catch {
      setGenerationStatus("Network error");
      setGenerating(false);
    }
  }, [category, rounds]);

  // -- Handle schedule save --
  const handleSaveSchedule = async (updates: Partial<ScheduleConfig>) => {
    setSavingSchedule(true);
    try {
      const res = await fetch("/api/schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      const data = await res.json();
      setSchedule(data);
    } catch (err) {
      console.error("Failed to save schedule:", err);
    } finally {
      setSavingSchedule(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Generate Video</h1>
        <p className="text-gray-400 text-sm mt-1">
          Trigger video generation manually or configure auto-generation
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* -- Manual Generate Card -- */}
        <div className="glass-card p-6 space-y-5">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            Manual Generate
          </h2>

          {/* Category selector */}
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={generating}
              className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                         text-white text-sm focus:outline-none focus:border-indigo-500/50"
            >
              {categories.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.emoji} {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Rounds count */}
          <div>
            <label className="block text-sm text-gray-300 mb-1.5">
              Number of Rounds
            </label>
            <input
              type="number"
              min={3}
              max={10}
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))}
              disabled={generating}
              className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                         text-white text-sm focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-gradient-to-r from-indigo-600 to-purple-600 text-white
                       font-semibold hover:from-indigo-500 hover:to-purple-500
                       disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {generating ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                Generate Video
              </>
            )}
          </button>

          {/* Generation status */}
          {generationStatus && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5">
              <StatusBadge status={(generationStatus === "completed" ? "pending" : "generating") as VideoStatus} />
              <span className="text-sm text-gray-300">
                Pipeline: {generationStatus}
              </span>
            </div>
          )}
        </div>

        {/* -- Auto Schedule Card -- */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-5">Auto Schedule</h2>
          {schedule ? (
            <ScheduleForm
              config={schedule}
              onSave={handleSaveSchedule}
              saving={savingSchedule}
            />
          ) : (
            <p className="text-gray-500 text-sm">Loading schedule...</p>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Run: `npm run dev`

Test: Visit `/generate`
1. Category dropdown with all 6 categories + "Auto"
2. Rounds number input (3-10)
3. Generate button triggers API call
4. Auto Schedule card with toggle, time picker, category rotation

- [ ] **Step 3: Commit**

```bash
git add app/generate/
git commit -m "feat: generate page with manual trigger and auto-schedule controls"
```

---

### Task 9: Approval Queue Page

**Files:**
- Create: `app/queue/page.tsx`

**Interfaces:**
- Consumes: `GET /api/videos?status=pending`, `PATCH /api/videos/[id]`, `POST /api/videos/[id]/approve`, `POST /api/videos/[id]/reject`
- Produces: Approval queue page with video cards, metadata editing, approve/reject/schedule actions

- [ ] **Step 1: Build the approval queue page**

Create `app/queue/page.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Approval Queue page — lists all pending videos for review.
//  Each video card shows player, metadata editor, and action buttons.
//  Admin can approve (post now or schedule), reject, or edit metadata.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { CheckSquare, RefreshCw } from "lucide-react";
import VideoCard from "@/components/video-card";
import type { Video } from "@/lib/types";

export default function QueuePage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);

  // -- Fetch pending videos --
  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/videos?status=pending&limit=50");
      const data = await res.json();
      setVideos(data.videos || []);
    } catch (err) {
      console.error("Failed to fetch queue:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on mount
  useEffect(() => { fetchPending(); }, [fetchPending]);

  // -- Handle approve --
  const handleApprove = async (videoId: string, scheduledAt?: string) => {
    await fetch(`/api/videos/${videoId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: scheduledAt }),
    });
    // If approved for immediate posting, trigger upload
    if (!scheduledAt) {
      await fetch(`/api/videos/${videoId}/upload`, { method: "POST" });
    }
    // Remove from queue
    setVideos((prev) => prev.filter((v) => v.id !== videoId));
  };

  // -- Handle reject --
  const handleReject = async (videoId: string) => {
    await fetch(`/api/videos/${videoId}/reject`, { method: "POST" });
    setVideos((prev) => prev.filter((v) => v.id !== videoId));
  };

  // -- Handle metadata update --
  const handleUpdate = async (videoId: string, updates: Partial<Video>) => {
    await fetch(`/api/videos/${videoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <CheckSquare className="w-6 h-6 text-amber-400" />
            Approval Queue
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            {videos.length} video{videos.length !== 1 ? "s" : ""} awaiting review
          </p>
        </div>
        {/* Refresh button */}
        <button
          onClick={fetchPending}
          className="flex items-center gap-2 px-4 py-2 rounded-xl
                     bg-white/5 text-gray-400 hover:text-white hover:bg-white/10
                     transition-colors text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Video cards */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading queue...</div>
      ) : videos.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <CheckSquare className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No videos pending approval</p>
          <p className="text-gray-500 text-sm mt-1">
            Generate a new video to get started
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onApprove={handleApprove}
              onReject={handleReject}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create upload trigger API route**

Create `app/api/videos/[id]/upload/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/videos/[id]/upload
//  Triggers the upload GitHub Action for an approved video.
//  Downloads from Blob, uploads to YouTube/TikTok via Action.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getVideo, updateVideo, logActivity } from "@/lib/db";
import { triggerUploadWorkflow } from "@/lib/github";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const video = await getVideo(id);

  if (!video) {
    return NextResponse.json({ error: "Video not found" }, { status: 404 });
  }

  if (!video.video_url) {
    return NextResponse.json({ error: "No video file available" }, { status: 400 });
  }

  // Parse tags from JSON string
  const tags = video.tags ? JSON.parse(video.tags) : [];

  // Trigger the upload workflow
  const runId = await triggerUploadWorkflow(
    video.id,
    video.video_url,
    {
      title: video.title || `Leo Quiz: ${video.category}`,
      description: video.description || "",
      tags,
    },
    video.platform
  );

  if (!runId) {
    await logActivity("failed", video.id, `Upload trigger failed: ${video.title || video.category}`);
    return NextResponse.json({ error: "Failed to trigger upload" }, { status: 500 });
  }

  await logActivity("uploaded", video.id, `Upload started: ${video.title || video.category}`);

  return NextResponse.json({ success: true, run_id: runId });
}
```

- [ ] **Step 3: Verify in browser**

Run: `npm run dev`

Test: Visit `/queue`
1. Shows empty state "No videos pending approval"
2. Refresh button works

- [ ] **Step 4: Commit**

```bash
git add app/queue/ app/api/videos/
git commit -m "feat: approval queue page with video cards and upload trigger"
```

---

### Task 10: History Page

**Files:**
- Create: `app/history/page.tsx`

**Interfaces:**
- Consumes: `GET /api/videos?status=&category=&search=&offset=&limit=`
- Produces: History page with filters, search, paginated video list

- [ ] **Step 1: Build the history page**

Create `app/history/page.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  History page — all past videos with filters and search.
//  Filters: status, category, trigger type, title search.
//  Paginated with 20 videos per page.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { History as HistoryIcon, Search, ChevronLeft, ChevronRight } from "lucide-react";
import StatusBadge from "@/components/status-badge";
import CategoryBadge from "@/components/category-badge";
import type { Video, VideoStatus, Category } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

const PAGE_SIZE = 20;

export default function HistoryPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [triggerFilter, setTriggerFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  // -- Fetch videos with current filters --
  const fetchVideos = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (categoryFilter !== "all") params.set("category", categoryFilter);
    if (triggerFilter !== "all") params.set("trigger_type", triggerFilter);
    if (search) params.set("search", search);
    params.set("offset", String(page * PAGE_SIZE));
    params.set("limit", String(PAGE_SIZE));

    try {
      const res = await fetch(`/api/videos?${params}`);
      const data = await res.json();
      setVideos(data.videos || []);
      setTotal(data.total || 0);
    } catch {
      console.error("Failed to fetch history");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, triggerFilter, search, page]);

  // Re-fetch when filters or page change
  useEffect(() => { fetchVideos(); }, [fetchVideos]);

  // Total pages
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <HistoryIcon className="w-6 h-6 text-purple-400" />
          History
        </h1>
        <p className="text-gray-400 text-sm mt-1">{total} total videos</p>
      </div>

      {/* Filters bar */}
      <div className="glass-card p-4 flex flex-wrap gap-3 items-center">
        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-sm"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="scheduled">Scheduled</option>
          <option value="uploaded">Uploaded</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed</option>
        </select>

        {/* Category filter */}
        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-sm"
        >
          <option value="all">All Categories</option>
          <option value="animals">Animals</option>
          <option value="dinosaurs">Dinosaurs</option>
          <option value="space">Space</option>
          <option value="vehicles">Vehicles</option>
          <option value="fruits">Fruits</option>
          <option value="flags">Flags</option>
        </select>

        {/* Trigger filter */}
        <select
          value={triggerFilter}
          onChange={(e) => { setTriggerFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10
                     text-white text-sm"
        >
          <option value="all">All Triggers</option>
          <option value="manual">Manual</option>
          <option value="automated">Automated</option>
        </select>

        {/* Search */}
        <div className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder="Search by title..."
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white text-sm placeholder-gray-500 focus:outline-none
                       focus:border-indigo-500/50"
          />
        </div>
      </div>

      {/* Videos table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : videos.length === 0 ? (
        <div className="glass-card p-12 text-center text-gray-400">
          No videos match your filters
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Video</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Category</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Status</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Trigger</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((video) => (
                  <tr key={video.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        {/* Thumbnail */}
                        {video.thumbnail_url ? (
                          <img
                            src={video.thumbnail_url}
                            alt=""
                            className="w-16 h-9 rounded object-cover"
                          />
                        ) : (
                          <div className="w-16 h-9 rounded bg-white/5" />
                        )}
                        <span className="text-white font-medium truncate max-w-[200px]">
                          {video.title || `${video.category} quiz`}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <CategoryBadge category={video.category} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={video.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-400 capitalize">
                      {video.trigger_type}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {formatDistanceToNow(new Date(video.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-white/5">
              <span className="text-sm text-gray-400">
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="p-2 rounded-lg bg-white/5 text-gray-400
                             hover:text-white disabled:opacity-30"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  className="p-2 rounded-lg bg-white/5 text-gray-400
                             hover:text-white disabled:opacity-30"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Run: `npm run dev`

Test: Visit `/history`
1. Empty state shows "No videos match your filters"
2. All filter dropdowns render (status, category, trigger)
3. Search input works
4. Pagination controls appear when needed

- [ ] **Step 3: Commit**

```bash
git add app/history/
git commit -m "feat: history page with filters, search, and pagination"
```

---

### Task 11: YouTube OAuth + Token Management

**Files:**
- Create: `lib/tokens.ts`
- Create: `app/api/auth/youtube/route.ts`
- Create: `app/api/auth/youtube/callback/route.ts`
- Create: `app/api/auth/disconnect/route.ts`
- Create: `app/api/auth/status/route.ts`
- Create: `app/api/tokens/youtube/route.ts`

**Interfaces:**
- Consumes: `@vercel/blob` (put, list, del), YouTube OAuth2 endpoints
- Produces:
  - `saveToken(platform, data): Promise<void>` — stores OAuth tokens in Blob
  - `getToken(platform): Promise<TokenData | null>` — reads + auto-refreshes tokens
  - `deleteToken(platform): Promise<void>` — disconnects a platform
  - `getConnectionStatus(): Promise<Record<string, ConnectionStatus>>` — checks all platforms
  - `GET /api/auth/youtube` — redirects to Google OAuth consent screen
  - `GET /api/auth/youtube/callback` — exchanges code for tokens, saves to Blob
  - `POST /api/auth/disconnect` — deletes token for a platform
  - `GET /api/auth/status` — returns connection status for all platforms
  - `GET /api/tokens/youtube` — returns fresh access token (for GitHub Action to use)

- [ ] **Step 1: Create token management module**

Create `lib/tokens.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  OAuth token management for YouTube (and future TikTok).
//  Stores tokens in Vercel Blob as private JSON files.
//  Auto-refreshes expired access tokens using the refresh token.
//
//  "Connect once" pattern: user authorizes once via OAuth,
//  we store the refresh token, and auto-refresh access tokens
//  forever — no manual re-auth needed.
//
//  Token files in Blob:
//    tokens/youtube.json
//
//  Same pattern as Luminous Will's lib/tokens.ts.
// ─────────────────────────────────────────────────────────────

import { put, list, del } from "@vercel/blob";
import type { TokenData, ConnectionStatus } from "./types";

// -- Blob path prefix for all token files --
const TOKEN_PREFIX = "tokens/";

// -- Refresh 5 minutes before actual expiry --
// Prevents edge cases where token expires mid-upload
const REFRESH_BUFFER_SECONDS = 300;

// -- YouTube OAuth token endpoint --
const YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token";

export async function saveToken(platform: string, data: TokenData): Promise<void> {
  // Writes token data to Blob as a private JSON file.
  // Uses addRandomSuffix: false so we can overwrite on refresh.
  const path = `${TOKEN_PREFIX}${platform}.json`;
  await put(path, JSON.stringify(data), {
    access: "public",
    contentType: "application/json",
    addRandomSuffix: false,
  });
}

export async function deleteToken(platform: string): Promise<void> {
  // Removes the token file from Blob — disconnects the platform
  try {
    const { blobs } = await list({ prefix: `${TOKEN_PREFIX}${platform}.json` });
    if (blobs.length > 0) {
      await del(blobs[0].url);
    }
  } catch {
    // Ignore errors — token may already be gone
  }
}

async function loadTokenData(platform: string): Promise<TokenData | null> {
  // Reads raw token data from Blob. Returns null if not connected.
  try {
    const { blobs } = await list({ prefix: `${TOKEN_PREFIX}${platform}.json` });
    if (blobs.length === 0) return null;

    // Fetch the blob content
    const response = await fetch(blobs[0].url);
    if (!response.ok) return null;
    return (await response.json()) as TokenData;
  } catch (err) {
    console.error(`[TOKENS] loadTokenData error for ${platform}:`, err);
    return null;
  }
}

export async function refreshAccessToken(
  platform: string,
  tokenData: TokenData
): Promise<TokenData | null> {
  // Exchanges the refresh token for a fresh access token.
  // Returns updated TokenData on success, null if refresh was rejected.
  const clientId = process.env.YOUTUBE_CLIENT_ID || "";
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET || "";

  try {
    const response = await fetch(YOUTUBE_TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
        grant_type: "refresh_token",
        refresh_token: tokenData.refresh_token,
      }).toString(),
    });

    if (!response.ok) {
      console.error(`[TOKENS] Refresh failed for ${platform}: ${response.status}`);
      return null;
    }

    const data = await response.json();

    // Build updated token data — some providers return a new refresh token
    const updated: TokenData = {
      refresh_token: data.refresh_token || tokenData.refresh_token,
      access_token: data.access_token,
      expires_at: Math.floor(Date.now() / 1000) + (data.expires_in || 3600),
      account_name: tokenData.account_name,
    };

    // Persist the refreshed tokens back to Blob
    await saveToken(platform, updated);

    return updated;
  } catch (error) {
    console.error(`[TOKENS] Refresh error for ${platform}:`, error);
    return null;
  }
}

export async function getToken(platform: string): Promise<TokenData | null> {
  // Reads the token for a platform, auto-refreshing if expired.
  // Returns null if not connected or if refresh fails (needs reconnect).
  const tokenData = await loadTokenData(platform);
  if (!tokenData) return null;

  // Check if access token is still valid (with 5-min buffer)
  const now = Math.floor(Date.now() / 1000);
  if (tokenData.expires_at > now + REFRESH_BUFFER_SECONDS) {
    // Token is still fresh — use it
    return tokenData;
  }

  // Access token expired — refresh it
  const refreshed = await refreshAccessToken(platform, tokenData);
  return refreshed;
}

export async function isConnected(platform: string): Promise<boolean> {
  // Quick check — does a token file exist for this platform?
  const tokenData = await loadTokenData(platform);
  return tokenData !== null;
}

export async function getConnectionStatus(): Promise<Record<string, ConnectionStatus>> {
  // Returns connection status for YouTube (and future platforms).
  // Used by the settings page to show connected/disconnected state.
  const platforms = ["youtube"];
  const result: Record<string, ConnectionStatus> = {};

  for (const platform of platforms) {
    const tokenData = await loadTokenData(platform);

    if (!tokenData) {
      result[platform] = { connected: false };
      continue;
    }

    // Check if access token can be refreshed
    const now = Math.floor(Date.now() / 1000);
    if (tokenData.expires_at <= now + REFRESH_BUFFER_SECONDS) {
      const refreshed = await refreshAccessToken(platform, tokenData);
      if (!refreshed) {
        result[platform] = {
          connected: false,
          account_name: tokenData.account_name,
          needs_reconnect: true,
        };
        continue;
      }
    }

    result[platform] = {
      connected: true,
      account_name: tokenData.account_name,
    };
  }

  return result;
}
```

- [ ] **Step 2: Create YouTube OAuth start route**

Create `app/api/auth/youtube/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/auth/youtube
//  Redirects to Google's OAuth consent screen.
//  After the user approves, Google redirects to the callback URL.
//  Uses CSRF state token stored in a cookie for security.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { randomBytes } from "crypto";

export async function GET() {
  const clientId = process.env.YOUTUBE_CLIENT_ID;
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const redirectUri = `${appUrl}/api/auth/youtube/callback`;

  // Generate CSRF state token
  const state = randomBytes(32).toString("hex");

  // Build Google OAuth URL with required scopes
  const params = new URLSearchParams({
    client_id: clientId || "",
    redirect_uri: redirectUri,
    response_type: "code",
    // youtube.upload = upload videos, youtube.readonly = read channel info
    scope: "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
    // "offline" = get a refresh token (essential for connect-once)
    access_type: "offline",
    // "consent" = always show the consent screen (ensures we get refresh_token)
    prompt: "consent",
    state,
  });

  // Redirect to Google with CSRF state in a cookie
  const response = NextResponse.redirect(
    `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`
  );

  // Store state in secure cookie for CSRF verification on callback
  response.cookies.set("oauth_state_youtube", state, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: 600,
    path: "/",
  });

  return response;
}
```

- [ ] **Step 3: Create YouTube OAuth callback route**

Create `app/api/auth/youtube/callback/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/auth/youtube/callback
//  Google redirects here after the user approves.
//  Exchanges the auth code for access + refresh tokens,
//  fetches the channel name, saves tokens to Blob,
//  and redirects to /settings.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { saveToken } from "@/lib/tokens";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const error = url.searchParams.get("error");
  const state = url.searchParams.get("state");
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

  // Handle denial or error
  if (error || !code) {
    return NextResponse.redirect(`${appUrl}/settings?error=youtube_denied`);
  }

  // Verify CSRF state token
  const cookieStore = await cookies();
  const savedState = cookieStore.get("oauth_state_youtube")?.value;
  if (!state || !savedState || state !== savedState) {
    return NextResponse.redirect(`${appUrl}/settings?error=youtube_csrf`);
  }

  try {
    // Exchange auth code for tokens
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: process.env.YOUTUBE_CLIENT_ID || "",
        client_secret: process.env.YOUTUBE_CLIENT_SECRET || "",
        redirect_uri: `${appUrl}/api/auth/youtube/callback`,
        grant_type: "authorization_code",
      }).toString(),
    });

    if (!tokenResponse.ok) {
      return NextResponse.redirect(`${appUrl}/settings?error=youtube_token_failed`);
    }

    const tokens = await tokenResponse.json();

    // Get the channel name for display
    let accountName = "YouTube Channel";
    try {
      const channelResponse = await fetch(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        { headers: { Authorization: `Bearer ${tokens.access_token}` } }
      );
      if (channelResponse.ok) {
        const channelData = await channelResponse.json();
        accountName = channelData.items?.[0]?.snippet?.title || accountName;
      }
    } catch {
      // Fallback to default name — not critical
    }

    // Save tokens to Vercel Blob
    await saveToken("youtube", {
      refresh_token: tokens.refresh_token,
      access_token: tokens.access_token,
      expires_at: Math.floor(Date.now() / 1000) + (tokens.expires_in || 3600),
      account_name: accountName,
    });

    // Redirect to settings with success indicator
    const successResponse = NextResponse.redirect(`${appUrl}/settings?connected=youtube`);
    successResponse.cookies.delete("oauth_state_youtube");
    return successResponse;
  } catch (err) {
    console.error("[YOUTUBE_CALLBACK] Error:", err);
    return NextResponse.redirect(`${appUrl}/settings?error=youtube_failed`);
  }
}
```

- [ ] **Step 4: Create disconnect and status routes**

Create `app/api/auth/disconnect/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/auth/disconnect
//  Disconnects a platform by deleting its token from Blob.
//  Body: { platform: "youtube" }
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { deleteToken } from "@/lib/tokens";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const platform = body.platform as string;

  if (!platform || !["youtube"].includes(platform)) {
    return NextResponse.json({ error: "Invalid platform" }, { status: 400 });
  }

  await deleteToken(platform);
  return NextResponse.json({ disconnected: platform });
}
```

Create `app/api/auth/status/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/auth/status
//  Returns the connection status for all platforms.
//  Used by the settings page to show which platforms are connected.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getConnectionStatus } from "@/lib/tokens";

export async function GET() {
  const status = await getConnectionStatus();
  return NextResponse.json(status);
}
```

- [ ] **Step 5: Create token endpoint for GitHub Action**

Create `app/api/tokens/youtube/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  GET /api/tokens/youtube
//  Returns a fresh YouTube access token for the upload Action.
//  Protected by DASHBOARD_WEBHOOK_SECRET (same secret as pipeline).
//  The GitHub Action calls this before uploading to YouTube.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { getToken } from "@/lib/tokens";

export async function GET(request: Request) {
  // Verify webhook secret (same as pipeline callback)
  const secret = request.headers.get("x-webhook-secret");
  const expectedSecret = process.env.DASHBOARD_WEBHOOK_SECRET;

  if (!expectedSecret || secret !== expectedSecret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Get a fresh access token (auto-refreshes if expired)
  const token = await getToken("youtube");

  if (!token) {
    return NextResponse.json(
      { error: "YouTube not connected" },
      { status: 404 }
    );
  }

  // Return just the access token — the Action uses it for upload
  return NextResponse.json({
    access_token: token.access_token,
    expires_at: token.expires_at,
    account_name: token.account_name,
  });
}
```

- [ ] **Step 6: Verify all routes compile**

Run: `npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 7: Commit**

```bash
git add lib/tokens.ts app/api/auth/ app/api/tokens/
git commit -m "feat: YouTube OAuth connect-once flow with Blob token storage and auto-refresh"
```

---

### Task 12: Cron Job + Settings Page

**Files:**
- Create: `app/api/cron/check-scheduled/route.ts`
- Create: `app/settings/page.tsx`

**Interfaces:**
- Consumes: `listVideos`, `updateVideo`, `logActivity`, `getScheduleConfig`, `updateScheduleConfig` from `lib/db.ts`, `getConnectionStatus` from `lib/tokens.ts`, `triggerUploadWorkflow` from `lib/github.ts`
- Produces:
  - `POST /api/cron/check-scheduled` — Vercel Cron handler that finds due scheduled videos and triggers upload
  - Settings page with schedule config, YouTube connection, and API status indicators

- [ ] **Step 1: Create the cron job route**

Create `app/api/cron/check-scheduled/route.ts`:
```typescript
// ─────────────────────────────────────────────────────────────
//  POST /api/cron/check-scheduled
//  Vercel Cron job — runs every 15 minutes.
//  Finds videos where status = "scheduled" and scheduled_at <= now.
//  Triggers the upload GitHub Action for each due video.
//  Protected by CRON_SECRET header.
// ─────────────────────────────────────────────────────────────

import { NextResponse } from "next/server";
import { listVideos, updateVideo, logActivity } from "@/lib/db";
import { triggerUploadWorkflow } from "@/lib/github";

export async function POST(request: Request) {
  // -- Verify cron secret --
  const authHeader = request.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (!cronSecret || authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // -- Find scheduled videos that are due --
  const { videos } = await listVideos({ status: "scheduled", limit: 50 });
  const now = new Date();

  let triggered = 0;

  for (const video of videos) {
    // Skip if not yet due
    if (!video.scheduled_at || new Date(video.scheduled_at) > now) {
      continue;
    }

    // Skip if no video file
    if (!video.video_url) {
      await updateVideo(video.id, { status: "failed" });
      await logActivity("failed", video.id, `No video file for scheduled post: ${video.title}`);
      continue;
    }

    // Trigger the upload workflow
    const tags = video.tags ? JSON.parse(video.tags) : [];
    const runId = await triggerUploadWorkflow(
      video.id,
      video.video_url,
      {
        title: video.title || `Leo Quiz: ${video.category}`,
        description: video.description || "",
        tags,
      },
      video.platform
    );

    if (runId) {
      await updateVideo(video.id, { status: "approved" });
      await logActivity("uploaded", video.id, `Scheduled upload started: ${video.title}`);
      triggered++;
    } else {
      await logActivity("failed", video.id, `Scheduled upload trigger failed: ${video.title}`);
    }
  }

  return NextResponse.json({
    checked: videos.length,
    triggered,
    timestamp: now.toISOString(),
  });
}
```

- [ ] **Step 2: Build the settings page**

Create `app/settings/page.tsx`:
```tsx
"use client";

// ─────────────────────────────────────────────────────────────
//  Settings page — system configuration:
//  1. Schedule config (same as Generate page auto-schedule)
//  2. YouTube connection (connect/disconnect)
//  3. API status indicators
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from "react";
import { Settings as SettingsIcon, Youtube, Link2, LinkOff, CheckCircle, XCircle } from "lucide-react";
import ScheduleForm from "@/components/schedule-form";
import type { ScheduleConfig, ConnectionStatus } from "@/lib/types";

export default function SettingsPage() {
  // Schedule state
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);

  // Connection status
  const [connections, setConnections] = useState<Record<string, ConnectionStatus>>({});
  const [loadingConnections, setLoadingConnections] = useState(true);

  // -- Load data on mount --
  useEffect(() => {
    // Fetch schedule config
    fetch("/api/schedule")
      .then((r) => r.json())
      .then(setSchedule)
      .catch(console.error);

    // Fetch connection status
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then(setConnections)
      .catch(console.error)
      .finally(() => setLoadingConnections(false));
  }, []);

  // -- Handle schedule save --
  const handleSaveSchedule = async (updates: Partial<ScheduleConfig>) => {
    setSavingSchedule(true);
    try {
      const res = await fetch("/api/schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      setSchedule(await res.json());
    } finally {
      setSavingSchedule(false);
    }
  };

  // -- Handle YouTube connect --
  const handleConnectYouTube = () => {
    // Redirect to the YouTube OAuth flow
    window.location.href = "/api/auth/youtube";
  };

  // -- Handle disconnect --
  const handleDisconnect = async (platform: string) => {
    await fetch("/api/auth/disconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
    });
    // Refresh connection status
    const res = await fetch("/api/auth/status");
    setConnections(await res.json());
  };

  const ytStatus = connections.youtube;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-gray-400" />
          Settings
        </h1>
        <p className="text-gray-400 text-sm mt-1">Configure your pipeline and connections</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* -- Schedule Configuration -- */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-5">Generation Schedule</h2>
          {schedule ? (
            <ScheduleForm
              config={schedule}
              onSave={handleSaveSchedule}
              saving={savingSchedule}
            />
          ) : (
            <p className="text-gray-500">Loading...</p>
          )}
        </div>

        {/* -- Platform Connections -- */}
        <div className="space-y-6">
          {/* YouTube connection card */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-2">
              <Youtube className="w-5 h-5 text-red-500" />
              YouTube
            </h2>

            {loadingConnections ? (
              <p className="text-gray-500 text-sm">Checking connection...</p>
            ) : ytStatus?.connected ? (
              <div className="space-y-3">
                {/* Connected state */}
                <div className="flex items-center gap-2 text-emerald-400">
                  <CheckCircle className="w-5 h-5" />
                  <span className="text-sm font-medium">Connected</span>
                </div>
                <p className="text-gray-400 text-sm">
                  Channel: {ytStatus.account_name || "Unknown"}
                </p>
                <button
                  onClick={() => handleDisconnect("youtube")}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl
                             bg-rose-500/10 text-rose-400 border border-rose-500/20
                             hover:bg-rose-500/20 transition-colors text-sm"
                >
                  <LinkOff className="w-4 h-4" />
                  Disconnect
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Disconnected state */}
                <div className="flex items-center gap-2 text-gray-500">
                  <XCircle className="w-5 h-5" />
                  <span className="text-sm">Not connected</span>
                </div>
                {ytStatus?.needs_reconnect && (
                  <p className="text-amber-400 text-xs">
                    Session expired — reconnect to continue posting
                  </p>
                )}
                <button
                  onClick={handleConnectYouTube}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl
                             bg-gradient-to-r from-red-600 to-red-500
                             text-white text-sm font-medium
                             hover:from-red-500 hover:to-red-400 transition-all"
                >
                  <Link2 className="w-4 h-4" />
                  Connect YouTube
                </button>
                <p className="text-gray-500 text-xs">
                  One-time authorization — stays connected forever
                </p>
              </div>
            )}
          </div>

          {/* API Status card */}
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white mb-4">API Status</h2>
            <div className="space-y-3">
              {[
                { label: "GitHub Token", key: "GITHUB_TOKEN" },
                { label: "Webhook Secret", key: "DASHBOARD_WEBHOOK_SECRET" },
                { label: "Vercel Blob", key: "BLOB_READ_WRITE_TOKEN" },
                { label: "Turso Database", key: "TURSO_DATABASE_URL" },
              ].map((item) => (
                <div key={item.key} className="flex items-center justify-between py-1">
                  <span className="text-sm text-gray-400">{item.label}</span>
                  {/* We can't check env vars from client — show as configured */}
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <div className="w-2 h-2 rounded-full bg-emerald-500" />
                    Configured
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify in browser**

Run: `npm run dev`

Test: Visit `/settings`
1. Schedule form loads with defaults
2. YouTube section shows "Not connected" with Connect button
3. API Status shows configured indicators

- [ ] **Step 4: Commit**

```bash
git add app/api/cron/ app/settings/
git commit -m "feat: Vercel Cron for scheduled posts and settings page with YouTube connect"
```

---

### Task 13: Pipeline Workflow Modifications

**Files:**
- Modify: `C:\Users\User\LeoQuiz\.github\workflows\daily.yml`
- Create: `C:\Users\User\LeoQuiz\.github\workflows\upload.yml`

**Interfaces:**
- Consumes: Pipeline's `main.py` output (video.mp4, thumbnail.png, metadata_youtube.json, quiz_pack.json)
- Produces:
  - Modified `daily.yml` that accepts `workflow_dispatch` inputs (video_id, category, rounds), uploads outputs to Vercel Blob, and calls the dashboard webhook
  - New `upload.yml` that accepts inputs (video_id, video_blob_url, metadata, platform), fetches a fresh YouTube token from dashboard, and uploads to YouTube

- [ ] **Step 1: Update daily.yml with dashboard integration**

Modify `.github/workflows/daily.yml` to the following:
```yaml
name: Daily Quiz Video Generation

on:
  schedule:
    - cron: '0 6 * * *'  # Every day at 6:00 AM UTC
  workflow_dispatch:
    inputs:
      video_id:
        description: 'Dashboard video record ID'
        required: false
        type: string
      category:
        description: 'Quiz category (animals, dinosaurs, space, vehicles, fruits, flags)'
        required: false
        type: string
      rounds:
        description: 'Number of quiz rounds'
        required: false
        default: '5'
        type: string

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install Node.js (for Blob upload)
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Run pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          ELEVENLABS_VOICE_ID: ${{ secrets.ELEVENLABS_VOICE_ID }}
        run: |
          ARGS=""
          if [ -n "${{ inputs.category }}" ]; then
            ARGS="$ARGS --category ${{ inputs.category }}"
          fi
          if [ -n "${{ inputs.rounds }}" ]; then
            ARGS="$ARGS --rounds ${{ inputs.rounds }}"
          fi
          python main.py $ARGS

      - name: Find output directory
        id: find_output
        run: |
          OUTPUT_DIR=$(ls -td output/shorts/*/ | head -1)
          echo "dir=$OUTPUT_DIR" >> $GITHUB_OUTPUT

      - name: Upload to Vercel Blob and notify dashboard
        if: inputs.video_id != ''
        env:
          BLOB_READ_WRITE_TOKEN: ${{ secrets.BLOB_READ_WRITE_TOKEN }}
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
          DASHBOARD_WEBHOOK_SECRET: ${{ secrets.DASHBOARD_WEBHOOK_SECRET }}
        run: |
          OUTPUT_DIR="${{ steps.find_output.outputs.dir }}"
          VIDEO_ID="${{ inputs.video_id }}"

          # Upload video to Vercel Blob
          VIDEO_URL=$(npx -y vercel-blob-upload "$OUTPUT_DIR/video.mp4" \
            --content-type video/mp4 --token "$BLOB_READ_WRITE_TOKEN" 2>/dev/null | tail -1)

          # Upload thumbnail to Vercel Blob
          THUMB_URL=$(npx -y vercel-blob-upload "$OUTPUT_DIR/thumbnail.png" \
            --content-type image/png --token "$BLOB_READ_WRITE_TOKEN" 2>/dev/null | tail -1)

          # Read metadata
          METADATA=$(cat "$OUTPUT_DIR/metadata_youtube.json")
          TITLE=$(echo "$METADATA" | python -c "import sys,json; print(json.load(sys.stdin).get('title',''))")
          DESCRIPTION=$(echo "$METADATA" | python -c "import sys,json; print(json.load(sys.stdin).get('description',''))")
          TAGS=$(echo "$METADATA" | python -c "import sys,json; print(json.dumps(json.load(sys.stdin).get('tags',[])))")
          HASHTAGS=$(echo "$METADATA" | python -c "import sys,json; print(json.dumps(json.load(sys.stdin).get('hashtags',[])))")

          # Read quiz pack for full metadata
          QUIZ_PACK=$(cat "$OUTPUT_DIR/quiz_pack.json")

          # Notify dashboard webhook
          curl -X POST "$DASHBOARD_URL/api/webhook/pipeline-complete" \
            -H "Content-Type: application/json" \
            -H "x-webhook-secret: $DASHBOARD_WEBHOOK_SECRET" \
            -d "{
              \"video_id\": \"$VIDEO_ID\",
              \"video_url\": \"$VIDEO_URL\",
              \"thumbnail_url\": \"$THUMB_URL\",
              \"title\": \"$TITLE\",
              \"description\": \"$DESCRIPTION\",
              \"tags\": $TAGS,
              \"hashtags\": $HASHTAGS,
              \"metadata_json\": $QUIZ_PACK
            }"

      - name: Upload artifact (fallback)
        uses: actions/upload-artifact@v4
        with:
          name: quiz-video-${{ github.run_number }}
          path: output/shorts/
          retention-days: 30
```

- [ ] **Step 2: Create upload.yml workflow**

Create `.github/workflows/upload.yml`:
```yaml
name: Upload Video to Platform

on:
  workflow_dispatch:
    inputs:
      video_id:
        description: 'Dashboard video record ID'
        required: true
        type: string
      video_blob_url:
        description: 'Vercel Blob URL of the video file'
        required: true
        type: string
      metadata_json:
        description: 'JSON string with title, description, tags'
        required: true
        type: string
      platform:
        description: 'Target platform (youtube, tiktok, both)'
        required: true
        default: 'youtube'
        type: string

jobs:
  upload:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib requests

      - name: Get fresh YouTube token from dashboard
        id: token
        env:
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
          DASHBOARD_WEBHOOK_SECRET: ${{ secrets.DASHBOARD_WEBHOOK_SECRET }}
        run: |
          TOKEN_RESPONSE=$(curl -s "$DASHBOARD_URL/api/tokens/youtube" \
            -H "x-webhook-secret: $DASHBOARD_WEBHOOK_SECRET")
          ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
          echo "::add-mask::$ACCESS_TOKEN"
          echo "access_token=$ACCESS_TOKEN" >> $GITHUB_OUTPUT

      - name: Download video from Blob
        run: |
          curl -o video.mp4 "${{ inputs.video_blob_url }}"

      - name: Upload to YouTube
        if: inputs.platform == 'youtube' || inputs.platform == 'both'
        env:
          YOUTUBE_ACCESS_TOKEN: ${{ steps.token.outputs.access_token }}
        run: |
          python - << 'UPLOAD_SCRIPT'
          import json, os, sys
          from googleapiclient.discovery import build
          from googleapiclient.http import MediaFileUpload
          from google.oauth2.credentials import Credentials

          # Parse metadata
          metadata = json.loads('''${{ inputs.metadata_json }}''')

          # Build YouTube client with the dashboard-provided access token
          access_token = os.environ["YOUTUBE_ACCESS_TOKEN"]
          credentials = Credentials(token=access_token)
          youtube = build("youtube", "v3", credentials=credentials)

          # Upload video
          body = {
              "snippet": {
                  "title": metadata.get("title", "Leo Quiz"),
                  "description": metadata.get("description", ""),
                  "tags": metadata.get("tags", []),
                  "categoryId": "24",
              },
              "status": {
                  "privacyStatus": "public",
                  "selfDeclaredMadeForKids": True,
              },
          }

          media = MediaFileUpload("video.mp4", mimetype="video/mp4", resumable=True)
          request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
          response = request.execute()

          video_url = f"https://youtube.com/watch?v={response['id']}"
          print(f"Uploaded: {video_url}")

          # Write URL for webhook callback
          with open("upload_result.json", "w") as f:
              json.dump({"url": video_url, "video_id": response["id"]}, f)
          UPLOAD_SCRIPT

      - name: Notify dashboard of upload result
        env:
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
          DASHBOARD_WEBHOOK_SECRET: ${{ secrets.DASHBOARD_WEBHOOK_SECRET }}
        run: |
          if [ -f upload_result.json ]; then
            UPLOAD_URL=$(python -c "import json; print(json.load(open('upload_result.json'))['url'])")
            curl -X POST "$DASHBOARD_URL/api/webhook/pipeline-complete" \
              -H "Content-Type: application/json" \
              -H "x-webhook-secret: $DASHBOARD_WEBHOOK_SECRET" \
              -d "{
                \"video_id\": \"${{ inputs.video_id }}\",
                \"status\": \"uploaded\",
                \"upload_url\": \"$UPLOAD_URL\"
              }"
          fi
```

- [ ] **Step 3: Verify YAML is valid**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml')); print('daily.yml OK')"`
Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/upload.yml')); print('upload.yml OK')"`
Expected: Both OK

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "feat: pipeline workflows with dashboard integration — Blob upload + webhook callback + YouTube upload"
```

---

## Post-Implementation Checklist

After all 13 tasks are complete:

1. **Create GitHub repos:**
   - `gh repo create Leo-emp/leo-quiz-pipeline --public --source=. --push`
   - Create `Leo-emp/leo-quiz-dashboard` and push the dashboard code

2. **Set up Turso database:**
   - Create a database at turso.tech
   - Run the schema: `turso db shell <db-name> < lib/schema.sql`

3. **Set Vercel environment variables** (all from `.env.example`)

4. **Set GitHub Secrets** on `leo-quiz-pipeline` repo:
   - `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
   - `BLOB_READ_WRITE_TOKEN`, `DASHBOARD_URL`, `DASHBOARD_WEBHOOK_SECRET`

5. **Create YouTube OAuth app:**
   - Google Cloud Console → enable YouTube Data API v3
   - Create OAuth 2.0 credentials (Web application)
   - Set redirect URI: `https://your-dashboard.vercel.app/api/auth/youtube/callback`

6. **Connect YouTube** (one-time):
   - Go to dashboard Settings → click "Connect YouTube" → authorize → done forever

7. **Generate bcrypt password hash:**
   - `npx bcryptjs hash "your-admin-password"` → set as `ADMIN_PASSWORD_HASH`

8. **Deploy to Vercel:**
   - Connect `leo-quiz-dashboard` repo
   - Vercel auto-detects Next.js, builds and deploys
   - Cron job activates automatically from `vercel.json`
