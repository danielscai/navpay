# NavPay Telegram Bot (/bind, /link) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Telegram group bot for NavPay that supports `/bind` (bind a NavPay account via 6-char invite code, returns “Binding successful, waiting for review”) and `/link` (return a “View Messages” link), using a new project `navpay-tgbot/` and adding the necessary backend + admin review flow in `navpay-admin/`.

**Architecture:** A Node.js Telegram bot (long-polling initially) receives commands in the group, validates input, and calls `navpay-admin` integration APIs to create a binding record with `REVIEW_PENDING` status. Admin reviewers approve/reject bindings in `navpay-admin` UI; the bot reflects status in replies (minimal v1: only acknowledges bind and provides link).

**Tech Stack:** `navpay-tgbot` (Node 20+, TypeScript, `grammY` or `telegraf`, Vitest, `dotenv`), `navpay-admin` (Next.js, TypeScript, Drizzle ORM, SQLite migrations in `navpay-admin/drizzle/*.sql`).

---

## Product Spec (From Screenshots)

### `/bind`
- User sends `/bind` in the Telegram group.
- Bot replies with an instruction message:
  - “Please enter the 6-character invitation code displayed on our APP homepage. If you don't have an invitation code yet, register now for free.”
- User sends a 6-char invite code (example: `B5SPMT`).
- Bot replies:
  - “Binding successful, waiting for review”

### `/link`
- User sends `/link` in the Telegram group.
- Bot returns a “View Messages” link (exact destination depends on product decision; see Open Questions).

---

## Open Questions (Answer These Before/While Implementing)

1. `/link` “查看消息” should link to what exactly?
   - Option A: A Telegram channel (broadcast announcements).
   - Option B: A web page (NavPay message center) with per-account messages.
   - Option C: A static landing page or pinned-message permalink.
   - Plan below assumes v1 is “return a configurable URL”, upgrade later to a real message center if needed.
2. Binding scope:
   - Is “NavPay account” the `payment_persons` personal account in `navpay-admin` (invite code exists there), or another user model?
   - Plan assumes `payment_persons.invite_code` is the 6-char code users copy from the app.
3. Privacy requirement:
   - Is it acceptable that invite codes are posted publicly in the group (as screenshot shows)?
   - If not, bot should instruct users to DM the bot and reject codes in group.

---

## Data Model (Backend)

Create a new table `telegram_bindings` in `navpay-admin`:
- `id` (text PK, `id("tgb")`)
- `person_id` (FK-ish to `payment_persons.id`, not enforced in SQLite)
- `telegram_user_id` (stringified number)
- `telegram_username` (nullable)
- `telegram_first_name` (nullable)
- `telegram_last_name` (nullable)
- `chat_id` (stringified number, nullable; group/supergroup id)
- `chat_type` (`private` | `group` | `supergroup` | `channel`, nullable)
- `status` (`REVIEW_PENDING` | `APPROVED` | `REJECTED`)
- `reviewed_by_user_id` (nullable, admin reviewer)
- `reviewed_at_ms` (nullable)
- `created_at_ms`, `updated_at_ms`

Constraints/indexes:
- Unique on `telegram_user_id` (one TG user -> one NavPay account).
- Unique on `person_id` (one account -> one TG user).
- Index on `(status, created_at_ms)` for review queue.

---

## Security

Bot -> backend calls must be authenticated:
- Add env `TGBOT_SHARED_SECRET` in `navpay-admin`.
- Bot sends header `x-navpay-tgbot-secret: <secret>`.
- Backend rejects requests without correct secret.

Optional hardening:
- Restrict bind requests to allowed chat IDs: env `TELEGRAM_ALLOWED_CHAT_IDS` in `navpay-tgbot` (comma-separated).

---

## Repo / Git Remote Setup (New Project)

We will create a new sibling project directory: `navpay-tgbot/`.

Remote requirement:
- Create bare remote repo: `~/git-remote/navpay-tgbot`
- Set it as git remote `origin` for `navpay-tgbot/`.

Commands (run from workspace root):
```bash
mkdir -p ~/git-remote/navpay-tgbot
git init --bare ~/git-remote/navpay-tgbot

mkdir -p navpay-tgbot
cd navpay-tgbot
git init
git remote add origin ~/git-remote/navpay-tgbot
```

---

## Task 1: Add DB Migration + Schema For Telegram Bindings

**Files:**
- Create: `navpay-admin/drizzle/0006_telegram_bindings.sql`
- Modify: `navpay-admin/src/db/schema.ts`
- Test: `navpay-admin/tests/unit/telegram-bindings.test.ts`

**Step 1: Write the failing test**

Create `navpay-admin/tests/unit/telegram-bindings.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { sqlite } from "@/lib/db";

describe("telegram_bindings schema", () => {
  it("creates telegram_bindings table with required columns", () => {
    const cols = sqlite.prepare("pragma table_info('telegram_bindings')").all() as any[];
    const names = new Set(cols.map((c) => String(c.name)));
    // If migration not applied, cols will be [].
    expect(names.has("id")).toBe(true);
    expect(names.has("person_id")).toBe(true);
    expect(names.has("telegram_user_id")).toBe(true);
    expect(names.has("status")).toBe(true);
    expect(names.has("created_at_ms")).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin
yarn test tests/unit/telegram-bindings.test.ts
```
Expected: FAIL because table doesn't exist / columns missing.

**Step 3: Write minimal implementation**

Create `navpay-admin/drizzle/0006_telegram_bindings.sql`:
```sql
create table if not exists telegram_bindings (
  id text primary key,
  person_id text not null,
  telegram_user_id text not null,
  telegram_username text,
  telegram_first_name text,
  telegram_last_name text,
  chat_id text,
  chat_type text,
  status text not null,
  reviewed_by_user_id text,
  reviewed_at_ms integer,
  created_at_ms integer not null default (unixepoch() * 1000),
  updated_at_ms integer not null default (unixepoch() * 1000)
);

create unique index if not exists telegram_bindings_telegram_user_ux on telegram_bindings(telegram_user_id);
create unique index if not exists telegram_bindings_person_ux on telegram_bindings(person_id);
create index if not exists telegram_bindings_status_created_idx on telegram_bindings(status, created_at_ms);
```

Update `navpay-admin/src/db/schema.ts` (add `export const telegramBindings = sqliteTable(...)`).

**Step 4: Run migration + rerun test**

Run:
```bash
cd navpay-admin
yarn db:migrate
yarn test tests/unit/telegram-bindings.test.ts
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-admin/drizzle/0006_telegram_bindings.sql navpay-admin/src/db/schema.ts navpay-admin/tests/unit/telegram-bindings.test.ts
git commit -m "feat(admin): add telegram bindings table"
```

---

## Task 2: Backend Lib Functions For Binding + Review

**Files:**
- Create: `navpay-admin/src/lib/telegram-bindings.ts`
- Test: `navpay-admin/tests/unit/telegram-bindings-lib.test.ts`

**Step 1: Write the failing test**

Create `navpay-admin/tests/unit/telegram-bindings-lib.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { createTelegramBindingForInviteCode } from "@/lib/telegram-bindings";

describe("telegram bindings", () => {
  it("rejects invalid invite code format", async () => {
    await expect(
      createTelegramBindingForInviteCode({
        inviteCode: "bad",
        telegramUserId: "1",
        telegramUsername: "u",
        telegramFirstName: "f",
        telegramLastName: "l",
        chatId: "-100",
        chatType: "group",
      }),
    ).rejects.toThrow(/invalid_invite_code_format/);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin
yarn test tests/unit/telegram-bindings-lib.test.ts
```
Expected: FAIL because module/function doesn't exist.

**Step 3: Write minimal implementation**

Create `navpay-admin/src/lib/telegram-bindings.ts`:
```ts
import { db } from "@/lib/db";
import { id } from "@/lib/id";
import { paymentPersons, telegramBindings } from "@/db/schema";
import { eq } from "drizzle-orm";

function assertInviteCodeFormat(code: string) {
  const c = code.trim().toUpperCase();
  if (!/^[A-Z0-9]{6}$/.test(c)) {
    const e = new Error("invalid_invite_code_format");
    (e as any).status = 400;
    throw e;
  }
  return c;
}

export async function createTelegramBindingForInviteCode(input: {
  inviteCode: string;
  telegramUserId: string;
  telegramUsername?: string | null;
  telegramFirstName?: string | null;
  telegramLastName?: string | null;
  chatId?: string | null;
  chatType?: string | null;
}) {
  const inviteCode = assertInviteCodeFormat(input.inviteCode);

  const pp = (
    await db.select({ id: paymentPersons.id }).from(paymentPersons).where(eq(paymentPersons.inviteCode, inviteCode)).limit(1)
  )[0];
  if (!pp) {
    const e = new Error("invalid_invite_code");
    (e as any).status = 404;
    throw e;
  }

  const now = Date.now();
  // v1: simplest behavior: insert or return existing binding.
  // Implementation during execution: use onConflict handling via try/catch and query existing.
  await db.insert(telegramBindings).values({
    id: id("tgb"),
    personId: String(pp.id),
    telegramUserId: String(input.telegramUserId),
    telegramUsername: input.telegramUsername ?? null,
    telegramFirstName: input.telegramFirstName ?? null,
    telegramLastName: input.telegramLastName ?? null,
    chatId: input.chatId ?? null,
    chatType: input.chatType ?? null,
    status: "REVIEW_PENDING",
    reviewedByUserId: null as any,
    reviewedAtMs: null as any,
    createdAtMs: now,
    updatedAtMs: now,
  } as any);

  return { ok: true as const, status: "REVIEW_PENDING" as const };
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-admin
yarn test tests/unit/telegram-bindings-lib.test.ts
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-admin/src/lib/telegram-bindings.ts navpay-admin/tests/unit/telegram-bindings-lib.test.ts
git commit -m "feat(admin): add telegram bindings lib"
```

---

## Task 3: Integration API For Bot To Create Bindings

**Files:**
- Create: `navpay-admin/src/app/api/integrations/telegram/bind/route.ts`
- Modify: `navpay-admin/src/lib/env.ts`
- Modify: `navpay-admin/.env.example`
- Test: `navpay-admin/tests/unit/api-telegram-bind.test.ts`

**Step 1: Write the failing test**

Create `navpay-admin/tests/unit/api-telegram-bind.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { POST } from "@/app/api/integrations/telegram/bind/route";

describe("POST /api/integrations/telegram/bind", () => {
  it("rejects missing secret", async () => {
    const req = new Request("http://localhost/api/integrations/telegram/bind", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ inviteCode: "B5SPMT", telegramUserId: "1" }),
    });
    const res = await POST(req as any);
    expect(res.status).toBe(401);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin
yarn test tests/unit/api-telegram-bind.test.ts
```
Expected: FAIL because route doesn’t exist.

**Step 3: Write minimal implementation**

1) Add `TGBOT_SHARED_SECRET` to `navpay-admin/src/lib/env.ts` and `navpay-admin/.env.example`.

2) Create `navpay-admin/src/app/api/integrations/telegram/bind/route.ts`:
```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { env } from "@/lib/env";
import { createTelegramBindingForInviteCode } from "@/lib/telegram-bindings";

const bodySchema = z.object({
  inviteCode: z.string(),
  telegramUserId: z.string(),
  telegramUsername: z.string().optional().nullable(),
  telegramFirstName: z.string().optional().nullable(),
  telegramLastName: z.string().optional().nullable(),
  chatId: z.string().optional().nullable(),
  chatType: z.string().optional().nullable(),
});

export async function POST(req: Request) {
  const secret = req.headers.get("x-navpay-tgbot-secret") || "";
  if (!env.TGBOT_SHARED_SECRET || secret !== env.TGBOT_SHARED_SECRET) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const j = await req.json().catch(() => null);
  const p = bodySchema.safeParse(j);
  if (!p.success) return NextResponse.json({ ok: false, error: "bad_request" }, { status: 400 });

  try {
    const out = await createTelegramBindingForInviteCode(p.data);
    return NextResponse.json(out);
  } catch (e: any) {
    const status = Number(e?.status ?? 500);
    return NextResponse.json({ ok: false, error: String(e?.message ?? "error") }, { status });
  }
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-admin
yarn test tests/unit/api-telegram-bind.test.ts
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-admin/src/app/api/integrations/telegram/bind/route.ts navpay-admin/src/lib/env.ts navpay-admin/.env.example navpay-admin/tests/unit/api-telegram-bind.test.ts
git commit -m "feat(admin): add telegram bind integration api"
```

---

## Task 4: Admin Review UI + API (Approve/Reject)

**Files:**
- Create: `navpay-admin/src/app/api/admin/telegram/bindings/route.ts`
- Create: `navpay-admin/src/app/api/admin/telegram/bindings/[bindingId]/status/route.ts`
- Create: `navpay-admin/src/app/admin/resources/telegram-bindings/page.tsx`
- Modify: `navpay-admin/src/components/resources-client.tsx`
- Modify: `navpay-admin/scripts/db-seed.ts`
- Test: `navpay-admin/tests/unit/api-admin-telegram-bindings.test.ts`

**Step 1: Write the failing test**

Create `navpay-admin/tests/unit/api-admin-telegram-bindings.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { GET } from "@/app/api/admin/telegram/bindings/route";

describe("admin telegram bindings api", () => {
  it("requires auth", async () => {
    const req = new Request("http://localhost/api/admin/telegram/bindings");
    const res = await GET(req as any);
    expect([401, 403]).toContain(res.status);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-admin
yarn test tests/unit/api-admin-telegram-bindings.test.ts
```
Expected: FAIL because route doesn’t exist.

**Step 3: Write minimal implementation**

1) Add a new permission:
- In `navpay-admin/scripts/db-seed.ts`, append:
  - `telegram.bindings.review` with description `"Review Telegram bindings"`
  - Add it to role `"运营"` and `"审核员"` as needed.

2) Implement API routes:
- `GET /api/admin/telegram/bindings?status=REVIEW_PENDING|APPROVED|REJECTED`
- `POST /api/admin/telegram/bindings/:bindingId/status` with body `{ status: "APPROVED" | "REJECTED" }`
- Use `requireApiPerm(req, "telegram.bindings.review")` (see existing `src/lib/api.ts` patterns).
- Write an `auditLogs` entry on review action (action: `telegram.binding.review`).

3) UI:
- Add a new Resources tab:
  - `navpay-admin/src/components/resources-client.tsx` add tab key `telegram_bindings` label `Telegram 绑定`.
- Create page `navpay-admin/src/app/admin/resources/telegram-bindings/page.tsx` that renders the same `ResourcesClient` (or a dedicated component) and uses the new API to list & review.
- Minimal UI elements:
  - Filter chips for status.
  - Table columns: person name/id, inviteCode (optional), telegram user id, username, chat id, created time, status.
  - Approve/Reject buttons for `REVIEW_PENDING`.

**Step 4: Run tests**

Run:
```bash
cd navpay-admin
yarn test tests/unit/api-admin-telegram-bindings.test.ts
```
Expected: PASS.

Manual check:
```bash
cd navpay-admin
yarn dev
```
Open `http://localhost:3000/admin/resources?tab=telegram_bindings` (or the chosen route) and verify list + review actions.

**Step 5: Commit**
```bash
git add navpay-admin/src/app/api/admin/telegram/bindings/route.ts navpay-admin/src/app/api/admin/telegram/bindings/[bindingId]/status/route.ts navpay-admin/src/app/admin/resources/telegram-bindings/page.tsx navpay-admin/src/components/resources-client.tsx navpay-admin/scripts/db-seed.ts navpay-admin/tests/unit/api-admin-telegram-bindings.test.ts
git commit -m "feat(admin): add telegram bindings review ui"
```

---

## Task 5: Create `navpay-tgbot` Project Skeleton

**Files:**
- Create: `navpay-tgbot/package.json`
- Create: `navpay-tgbot/tsconfig.json`
- Create: `navpay-tgbot/src/main.ts`
- Create: `navpay-tgbot/src/config.ts`
- Create: `navpay-tgbot/src/commands/bind.ts`
- Create: `navpay-tgbot/src/commands/link.ts`
- Create: `navpay-tgbot/src/lib/invite-code.ts`
- Create: `navpay-tgbot/tests/invite-code.test.ts`
- Create: `navpay-tgbot/.env.example`
- Create: `navpay-tgbot/README.md`

**Step 1: Write the failing test**

Create `navpay-tgbot/tests/invite-code.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { normalizeInviteCode } from "../src/lib/invite-code";

describe("invite code", () => {
  it("normalizes and validates 6-char codes", () => {
    expect(normalizeInviteCode(" b5spmt ")).toBe("B5SPMT");
    expect(() => normalizeInviteCode("bad")).toThrow(/invalid_invite_code_format/);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-tgbot
yarn test
```
Expected: FAIL because project not set up yet.

**Step 3: Write minimal implementation**

1) Create `navpay-tgbot/package.json`:
```json
{
  "name": "navpay-tgbot",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/main.ts",
    "start": "node --enable-source-maps dist/main.js",
    "build": "tsc -p tsconfig.json",
    "test": "vitest run"
  },
  "dependencies": {
    "dotenv": "^17.2.4",
    "grammy": "^1.37.0"
  },
  "devDependencies": {
    "@types/node": "^20",
    "tsx": "^4.21.0",
    "typescript": "^5",
    "vitest": "^4.0.18"
  },
  "engines": {
    "node": ">=20 <23"
  }
}
```

2) Create `navpay-tgbot/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src", "tests"]
}
```

3) Create `navpay-tgbot/src/lib/invite-code.ts`:
```ts
export function normalizeInviteCode(raw: string): string {
  const c = raw.trim().toUpperCase();
  if (!/^[A-Z0-9]{6}$/.test(c)) throw new Error("invalid_invite_code_format");
  return c;
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-tgbot
yarn install
yarn test
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-tgbot
git commit -m "feat(tgbot): bootstrap project"
```

---

## Task 6: Implement `/bind` Conversation + Backend Call

**Files:**
- Modify: `navpay-tgbot/src/main.ts`
- Create: `navpay-tgbot/src/lib/navpay-api.ts`
- Modify: `navpay-tgbot/src/commands/bind.ts`
- Test: `navpay-tgbot/tests/bind-command.test.ts`

**Step 1: Write the failing test**

Create `navpay-tgbot/tests/bind-command.test.ts` (unit-level, not Telegram network):
```ts
import { describe, expect, it, vi } from "vitest";
import { handleBind } from "../src/commands/bind";

describe("/bind", () => {
  it("prompts for invite code when missing args", async () => {
    const replies: string[] = [];
    await handleBind({
      text: "/bind",
      from: { id: 1, username: "u", first_name: "f", last_name: "l" },
      chat: { id: -100, type: "group" },
      reply: async (t: string) => void replies.push(t),
      bindInviteCode: async () => ({ ok: true, status: "REVIEW_PENDING" }),
    });
    expect(replies.join("\n")).toMatch(/Please enter the 6-character invitation code/i);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-tgbot
yarn test tests/bind-command.test.ts
```
Expected: FAIL because `handleBind` not implemented.

**Step 3: Write minimal implementation**

1) Implement `handleBind(...)` in `navpay-tgbot/src/commands/bind.ts` with a dependency-injected `bindInviteCode` function so tests don’t require network.

2) Add support for:
- `/bind` (no args): reply with instruction string (exactly as screenshot; keep English v1).
- `/bind ABC123`: validate code and call backend, then reply `"Binding successful, waiting for review"`.
- Plain message `ABC123` right after `/bind`: optional v1; implement with an in-memory `Map` keyed by `${chatId}:${userId}` with TTL.

3) Implement `navpay-tgbot/src/lib/navpay-api.ts`:
- `bindInviteCode(...)` does `fetch(`${NAVPAY_API_BASE_URL}/api/integrations/telegram/bind`, ...)`
- Adds `x-navpay-tgbot-secret` header.

4) Add `navpay-tgbot/src/config.ts` + `.env.example`:
- `TELEGRAM_BOT_TOKEN`
- `NAVPAY_ADMIN_BASE_URL` (example `http://127.0.0.1:3000`)
- `TGBOT_SHARED_SECRET`
- `NAVPAY_MESSAGES_URL` (used by `/link`)
- Optional `TELEGRAM_ALLOWED_CHAT_IDS`

5) Wire in `navpay-tgbot/src/main.ts` with `grammy`:
- register command handlers for `/bind` and `/link`
- start bot (long polling).

**Step 4: Run tests**

Run:
```bash
cd navpay-tgbot
yarn test
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-tgbot/src navpay-tgbot/tests navpay-tgbot/.env.example
git commit -m "feat(tgbot): implement /bind command"
```

---

## Task 7: Implement `/link` (View Messages Link)

**Files:**
- Modify: `navpay-tgbot/src/commands/link.ts`
- Test: `navpay-tgbot/tests/link-command.test.ts`

**Step 1: Write the failing test**
```ts
import { describe, expect, it } from "vitest";
import { handleLink } from "../src/commands/link";

describe("/link", () => {
  it("returns configured messages url", async () => {
    const replies: string[] = [];
    await handleLink({
      reply: async (t: string) => void replies.push(t),
      messagesUrl: "https://example.com/messages",
    });
    expect(replies[0]).toMatch(/https:\\/\\/example\\.com\\/messages/);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-tgbot
yarn test tests/link-command.test.ts
```
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement `handleLink`:
- If `messagesUrl` configured: reply `View Messages: <url>`
- Else: reply a helpful message: “No messages link configured.”

**Step 4: Run tests**
```bash
cd navpay-tgbot
yarn test tests/link-command.test.ts
```
Expected: PASS.

**Step 5: Commit**
```bash
git add navpay-tgbot/src/commands/link.ts navpay-tgbot/tests/link-command.test.ts
git commit -m "feat(tgbot): add /link command"
```

---

## Task 8: End-to-End Manual Verification (Local)

**Files:**
- Modify: `navpay-tgbot/README.md`
- Modify: `navpay-admin/.env` (local only; do not commit secrets)

**Step 1: Prepare backend**
```bash
cd navpay-admin
cp .env.example .env
# set TGBOT_SHARED_SECRET="dev-secret"
yarn db:migrate
yarn db:seed
yarn dev
```
Expected: Next.js runs on `http://localhost:3000`.

**Step 2: Run bot**
```bash
cd navpay-tgbot
cp .env.example .env
# set TELEGRAM_BOT_TOKEN=...
# set NAVPAY_ADMIN_BASE_URL=http://127.0.0.1:3000
# set TGBOT_SHARED_SECRET=dev-secret
yarn dev
```

**Step 3: Verify in Telegram**
- In the configured group:
  - send `/bind` -> bot replies instruction
  - send a real invite code from `payment_persons.invite_code` -> bot replies “Binding successful, waiting for review”
  - send `/link` -> bot replies with configured messages link

**Step 4: Verify admin review**
- Open `navpay-admin` admin UI and locate “Telegram 绑定” tab
- Approve or reject the binding
- (Optional v1) Confirm DB `telegram_bindings.status` updated

**Step 5: Commit docs**
```bash
git add navpay-tgbot/README.md
git commit -m "docs(tgbot): add local runbook"
```

---

## Notes / Future Enhancements (Not In v1)

- Delete invite-code messages in group (requires bot admin permission).
- Force DM binding for privacy.
- Implement real “消息中心”:
  - `navpay-admin` add `personal_messages` table + `GET /api/personal/messages`
  - `/link` returns a signed one-time URL or deep link into the app.
- Bot webhook mode (production) behind HTTPS; long polling is fine for v1 dev.

