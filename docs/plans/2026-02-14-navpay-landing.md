# NavPay Landing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a standalone `navpay-landing/` web project that serves a mobile-first landing page styled like `ref/navpay/01_落地页_下载按钮.png`, and set its git remote to a local bare repo at `~/git-remote/navpay-landing`.

**Architecture:** A small Next.js (App Router) app with a single `/` route. Styling via Tailwind v4 + a thin layer of CSS variables to match the purple gradient + green CTA. A tiny `buildDownloadUrl()` helper appends `?invi=...` to the download URL when the landing page is opened with an invitation query param (as hinted by the screenshot URL bar).

**Tech Stack:** Next.js (match `navpay-admin` versions), React, TypeScript, Tailwind CSS v4, ESLint, Vitest (node env) for the URL helper.

---

## Reference (Style Extraction)

Source screenshot: `ref/navpay/01_落地页_下载按钮.png`

Key UI notes to replicate:
- Mobile-first single column layout.
- Top header: left brand (logo + "NavPay" + subtitle), right pill CTA button (green).
- Hero background: deep purple/indigo gradient with subtle geometric overlays.
- Big centered all-caps title.
- Decorative illustration under title (use an inline SVG placeholder, no external assets required).
- Primary CTA: full-width green button ("Download").
- Secondary CTA: full-width purple button ("Earn Money Online").

---

### Task 1: Create Local Bare Git Remote

**Files:** none

**Step 1: Create remote directory**

Run:
```bash
mkdir -p ~/git-remote
```
Expected: directory exists.

**Step 2: Initialize bare remote (idempotent if missing)**

Run:
```bash
test -d ~/git-remote/navpay-landing || git init --bare ~/git-remote/navpay-landing
```
Expected: prints git init output on first run; silent otherwise.

**Step 3: Verify remote repo**

Run:
```bash
ls -la ~/git-remote/navpay-landing | head
```
Expected: shows `HEAD`, `objects/`, `refs/` etc.

---

### Task 2: Create `navpay-landing/` Project Skeleton

**Files:**
- Create: `navpay-landing/.gitignore`
- Create: `navpay-landing/.yarnrc.yml`
- Create: `navpay-landing/.nvmrc`
- Create: `navpay-landing/README.md`
- Create: `navpay-landing/package.json`
- Create: `navpay-landing/tsconfig.json`
- Create: `navpay-landing/next-env.d.ts`
- Create: `navpay-landing/next.config.ts`
- Create: `navpay-landing/eslint.config.mjs`
- Create: `navpay-landing/postcss.config.mjs`
- Create: `navpay-landing/vitest.config.ts`
- Create: `navpay-landing/tests/vitest.setup.ts`
- Create: `navpay-landing/.env.example`
- Create: `navpay-landing/src/app/layout.tsx`
- Create: `navpay-landing/src/app/page.tsx`
- Create: `navpay-landing/src/app/globals.css`

**Step 1: Create folders**

Run:
```bash
mkdir -p navpay-landing/src/app navpay-landing/src/components navpay-landing/src/lib navpay-landing/tests/unit
```
Expected: directories created.

**Step 2: Add `package.json`**

Create `navpay-landing/package.json`:
```json
{
  "name": "navpay-landing",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3010",
    "build": "next build",
    "start": "next start -p 3010",
    "lint": "eslint",
    "typecheck": "tsc -p tsconfig.json --noEmit",
    "test": "vitest run",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "next": "16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "@vitest/ui": "^4.0.18",
    "eslint": "^9",
    "eslint-config-next": "16.1.6",
    "tailwindcss": "^4",
    "typescript": "^5",
    "vitest": "^4.0.18"
  },
  "packageManager": "yarn@4.0.0"
}
```

**Step 3: Add Yarn config**

Create `navpay-landing/.yarnrc.yml`:
```yml
nodeLinker: node-modules
```

**Step 4: Add Node version hint**

Create `navpay-landing/.nvmrc`:
```txt
23
```

**Step 5: Add TypeScript + Next config files**

Create `navpay-landing/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts",
    "**/*.mts"
  ],
  "exclude": ["node_modules", "tests", "vitest.config.ts"]
}
```

Create `navpay-landing/next-env.d.ts`:
```ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />

// NOTE: This file should not be edited
```

Create `navpay-landing/next.config.ts`:
```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" }
        ]
      }
    ];
  }
};

export default nextConfig;
```

**Step 6: Add Tailwind PostCSS config**

Create `navpay-landing/postcss.config.mjs`:
```js
const config = {
  plugins: {
    "@tailwindcss/postcss": {}
  }
};

export default config;
```

**Step 7: Add ESLint config (ESLint v9 flat config)**

Create `navpay-landing/eslint.config.mjs`:
```js
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "tests/**"
  ])
]);

export default eslintConfig;
```

**Step 8: Add Vitest config**

Create `navpay-landing/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src")
    }
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
    setupFiles: ["tests/vitest.setup.ts"]
  }
});
```

Create `navpay-landing/tests/vitest.setup.ts`:
```ts
// Keep tests deterministic across machines.
process.env.TZ = "UTC";
```

**Step 9: Add `.env.example`**

Create `navpay-landing/.env.example`:
```bash
# Absolute URL to the APK / download endpoint
NEXT_PUBLIC_DOWNLOAD_URL="https://example.com/navpay.apk"
```

**Step 10: Add `.gitignore`**

Create `navpay-landing/.gitignore`:
```gitignore
node_modules
.next
out
dist
.DS_Store
.env
*.log
test-results
coverage
```

**Step 11: Add minimal Next App files (placeholder)**

Create `navpay-landing/src/app/globals.css`:
```css
@import "tailwindcss";

body {
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans";
}
```

Create `navpay-landing/src/app/layout.tsx`:
```tsx
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

Create `navpay-landing/src/app/page.tsx`:
```tsx
export default function Home() {
  return (
    <main style={{ padding: 24 }}>
      <h1>NavPay Landing</h1>
    </main>
  );
}
```

**Step 12: Add README**

Create `navpay-landing/README.md`:
```md
# navpay-landing

Mobile-first NavPay landing page.

## Dev

```bash
yarn install
cp .env.example .env
yarn dev
```

Open: http://localhost:3010

## Build

```bash
yarn build
yarn start
```
```

**Step 13: Install deps**

Run:
```bash
cd navpay-landing
yarn install
```
Expected: installs dependencies successfully.

**Step 14: Initialize git early (so later tasks can commit)**

Run:
```bash
cd navpay-landing
git init -b main
git remote add origin ~/git-remote/navpay-landing
```
Expected: `.git/` created; `origin` remote set.

**Step 15: Initial commit (skeleton)**

Run:
```bash
cd navpay-landing
git add .
git commit -m "chore(landing): scaffold navpay-landing project"
```
Expected: one commit on `main`.

---

### Task 3: TDD the Download URL Builder (`?invi=...`)

**Files:**
- Test: `navpay-landing/tests/unit/build-download-url.test.ts`
- Create: `navpay-landing/src/lib/download-url.ts`

**Step 1: Write the failing test**

Create `navpay-landing/tests/unit/build-download-url.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { buildDownloadUrl } from "@/lib/download-url";

describe("buildDownloadUrl", () => {
  test("returns base URL when no invi", () => {
    expect(buildDownloadUrl("https://example.com/app.apk", undefined)).toBe(
      "https://example.com/app.apk"
    );
  });

  test("adds invi query param", () => {
    expect(buildDownloadUrl("https://example.com/app.apk", "ABC123")).toBe(
      "https://example.com/app.apk?invi=ABC123"
    );
  });

  test("preserves existing query params", () => {
    expect(buildDownloadUrl("https://example.com/app.apk?a=1", "X")).toBe(
      "https://example.com/app.apk?a=1&invi=X"
    );
  });

  test("replaces existing invi param", () => {
    expect(buildDownloadUrl("https://example.com/app.apk?invi=OLD", "NEW")).toBe(
      "https://example.com/app.apk?invi=NEW"
    );
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-landing
yarn test
```
Expected: FAIL, module `@/lib/download-url` not found.

**Step 3: Write minimal implementation**

Create `navpay-landing/src/lib/download-url.ts`:
```ts
export function buildDownloadUrl(baseUrl: string, invi: string | undefined): string {
  if (!invi) return baseUrl;

  const u = new URL(baseUrl);
  u.searchParams.set("invi", invi);
  return u.toString();
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-landing
yarn test
```
Expected: PASS.

**Step 5: Commit**

Run:
```bash
cd navpay-landing
git add tests/unit/build-download-url.test.ts src/lib/download-url.ts
git commit -m "feat(landing): add invitation-aware download url helper"
```

---

### Task 4: Add Env Helper for `NEXT_PUBLIC_DOWNLOAD_URL`

**Files:**
- Test: `navpay-landing/tests/unit/env.test.ts`
- Create: `navpay-landing/src/lib/env.ts`

**Step 1: Write the failing test**

Create `navpay-landing/tests/unit/env.test.ts`:
```ts
import { afterEach, describe, expect, test } from "vitest";
import { getDownloadBaseUrl } from "@/lib/env";

describe("getDownloadBaseUrl", () => {
  const original = process.env.NEXT_PUBLIC_DOWNLOAD_URL;

  afterEach(() => {
    if (original === undefined) {
      delete process.env.NEXT_PUBLIC_DOWNLOAD_URL;
    } else {
      process.env.NEXT_PUBLIC_DOWNLOAD_URL = original;
    }
  });

  test("returns configured env var", () => {
    process.env.NEXT_PUBLIC_DOWNLOAD_URL = "https://example.com/app.apk";
    expect(getDownloadBaseUrl()).toBe("https://example.com/app.apk");
  });

  test("throws when missing", () => {
    process.env.NEXT_PUBLIC_DOWNLOAD_URL = "";
    expect(() => getDownloadBaseUrl()).toThrow(/NEXT_PUBLIC_DOWNLOAD_URL/);
  });
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd navpay-landing
yarn test
```
Expected: FAIL, module `@/lib/env` not found.

**Step 3: Write minimal implementation**

Create `navpay-landing/src/lib/env.ts`:
```ts
export function getDownloadBaseUrl(): string {
  const v = process.env.NEXT_PUBLIC_DOWNLOAD_URL ?? "";
  if (!v.trim()) {
    throw new Error("Missing env var: NEXT_PUBLIC_DOWNLOAD_URL");
  }
  return v.trim();
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd navpay-landing
yarn test
```
Expected: PASS.

**Step 5: Commit**

Run:
```bash
cd navpay-landing
git add tests/unit/env.test.ts src/lib/env.ts
git commit -m "feat(landing): validate NEXT_PUBLIC_DOWNLOAD_URL"
```

---

### Task 5: Implement Landing Page UI (Match Screenshot Layout)

**Files:**
- Create: `navpay-landing/src/components/Header.tsx`
- Create: `navpay-landing/src/components/Hero.tsx`
- Create: `navpay-landing/src/components/HeroIllustration.tsx`
- Modify: `navpay-landing/src/app/layout.tsx`
- Modify: `navpay-landing/src/app/page.tsx`
- Create: `navpay-landing/src/app/globals.css`

**Step 1: Add global styles (colors + gradient background)**

Create `navpay-landing/src/app/globals.css`:
```css
@import "tailwindcss";

:root {
  --nl-bg-top: #0a1a4a;
  --nl-bg-mid: #3a1bbd;
  --nl-bg-bot: #6a2de2;
  --nl-cta: #22e6b0;
  --nl-cta-text: #06233b;
  --nl-purple-btn: #7b2bf2;
  --nl-white: rgba(255, 255, 255, 0.94);
  --nl-muted: rgba(255, 255, 255, 0.74);

  /* Keep builds offline-safe; upgrade to self-hosted fonts later if needed. */
  --font-sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans";
}

@theme inline {
  --font-sans: var(--font-sans);
}

body {
  font-family: var(--font-sans), "Apple Color Emoji", "Segoe UI Emoji";
  color: var(--nl-white);
  min-height: 100vh;
  background:
    radial-gradient(1200px 900px at 15% 15%, rgba(34, 230, 176, 0.16), transparent 60%),
    radial-gradient(900px 700px at 85% 25%, rgba(255, 255, 255, 0.10), transparent 55%),
    linear-gradient(180deg, var(--nl-bg-top), var(--nl-bg-mid) 55%, var(--nl-bg-bot));
}

.nl-surface {
  background: rgba(8, 20, 55, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
}

.nl-cta {
  background: var(--nl-cta);
  color: var(--nl-cta-text);
}
.nl-cta:hover {
  filter: brightness(0.98);
}

.nl-purple {
  background: linear-gradient(180deg, rgba(123, 43, 242, 0.95), rgba(123, 43, 242, 0.78));
  border: 1px solid rgba(255, 255, 255, 0.10);
}
```

**Step 2: Add root layout**

Create `navpay-landing/src/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NavPay",
  description: "Earn money online with easy tasks"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="overflow-x-hidden">
      <body className="antialiased overflow-x-hidden">{children}</body>
    </html>
  );
}
```

**Step 3: Implement header**

Create `navpay-landing/src/components/Header.tsx`:
```tsx
import Link from "next/link";

export function Header({ downloadHref }: { downloadHref: string }) {
  return (
    <header className="px-4 pt-4">
      <div className="nl-surface mx-auto max-w-md rounded-2xl px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-white/10 border border-white/15 grid place-items-center">
            <span className="font-black tracking-tight">N</span>
          </div>
          <div className="leading-tight">
            <div className="font-semibold">NavPay</div>
            <div className="text-[12px] text-white/70">Earn Money Online</div>
          </div>
        </div>

        <Link
          className="nl-cta rounded-full px-5 py-2 font-semibold text-sm shadow-[0_12px_30px_rgba(34,230,176,0.25)]"
          href={downloadHref}
        >
          Download
        </Link>
      </div>
    </header>
  );
}
```

**Step 4: Implement hero illustration (inline SVG placeholder)**

Create `navpay-landing/src/components/HeroIllustration.tsx`:
```tsx
export function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 420 260"
      className="w-full max-w-sm mx-auto drop-shadow-[0_18px_60px_rgba(0,0,0,0.35)]"
      role="img"
      aria-label="NavPay illustration"
    >
      <defs>
        <linearGradient id="plinth" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#6fe9ff" stopOpacity="0.92" />
          <stop offset="1" stopColor="#2b6bff" stopOpacity="0.18" />
        </linearGradient>
        <linearGradient id="paper" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.92" />
          <stop offset="1" stopColor="#e7f0ff" stopOpacity="0.75" />
        </linearGradient>
        <linearGradient id="accent" x1="0" x2="1">
          <stop offset="0" stopColor="#22e6b0" />
          <stop offset="1" stopColor="#7b2bf2" />
        </linearGradient>
      </defs>

      <ellipse cx="210" cy="220" rx="150" ry="24" fill="rgba(0,0,0,0.18)" />
      <ellipse cx="210" cy="205" rx="170" ry="40" fill="url(#plinth)" />

      <rect x="110" y="50" width="200" height="130" rx="18" fill="url(#paper)" />
      <path d="M140 90 C 190 60, 230 150, 280 110" stroke="url(#accent)" strokeWidth="10" fill="none" />
      <circle cx="280" cy="110" r="20" fill="rgba(123,43,242,0.95)" />
      <circle cx="150" cy="150" r="10" fill="rgba(255,220,75,0.95)" />
      <circle cx="290" cy="170" r="9" fill="rgba(255,220,75,0.92)" />
    </svg>
  );
}
```

**Step 5: Implement hero section**

Create `navpay-landing/src/components/Hero.tsx`:
```tsx
import Link from "next/link";
import { HeroIllustration } from "@/components/HeroIllustration";

export function Hero({ downloadHref }: { downloadHref: string }) {
  return (
    <main className="px-4 pb-12">
      <section className="mx-auto max-w-md pt-6">
        <h1 className="text-center font-extrabold tracking-tight text-[40px] leading-[1.05]">
          TO GET RUPEE
          <br />
          BY EASY TASK
        </h1>

        <div className="mt-6">
          <HeroIllustration />
        </div>

        <div className="mt-7 grid gap-3">
          <Link
            href={downloadHref}
            className="nl-cta w-full rounded-2xl py-4 text-center font-bold text-lg shadow-[0_18px_50px_rgba(34,230,176,0.22)]"
          >
            Download
          </Link>

          <div className="nl-surface rounded-2xl p-2">
            <a
              href="#features"
              className="nl-purple block w-full rounded-2xl py-4 text-center font-semibold text-lg"
            >
              Earn Money Online
            </a>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-md mt-10 nl-surface rounded-3xl p-5">
        <div className="text-sm text-white/75">How it works</div>
        <ol className="mt-3 grid gap-3 text-[15px]">
          <li className="flex gap-3">
            <span className="h-7 w-7 rounded-full bg-white/10 border border-white/15 grid place-items-center font-semibold">
              1
            </span>
            <span>Download NavPay and register.</span>
          </li>
          <li className="flex gap-3">
            <span className="h-7 w-7 rounded-full bg-white/10 border border-white/15 grid place-items-center font-semibold">
              2
            </span>
            <span>Complete simple tasks.</span>
          </li>
          <li className="flex gap-3">
            <span className="h-7 w-7 rounded-full bg-white/10 border border-white/15 grid place-items-center font-semibold">
              3
            </span>
            <span>Get rupee rewards faster.</span>
          </li>
        </ol>
      </section>

      <footer className="mx-auto max-w-md px-1 mt-10 text-center text-xs text-white/60">
        © {new Date().getFullYear()} NavPay
      </footer>
    </main>
  );
}
```

**Step 6: Wire page with `?invi=` and env**

Create `navpay-landing/src/app/page.tsx`:
```tsx
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { getDownloadBaseUrl } from "@/lib/env";
import { buildDownloadUrl } from "@/lib/download-url";

export default function Home({
  searchParams
}: {
  searchParams: { invi?: string };
}) {
  const base = getDownloadBaseUrl();
  const downloadHref = buildDownloadUrl(base, searchParams?.invi);

  return (
    <div>
      <Header downloadHref={downloadHref} />
      <Hero downloadHref={downloadHref} />
    </div>
  );
}
```

**Step 7: Run dev server and visually compare**

Run:
```bash
cd navpay-landing
cp .env.example .env
# Edit .env and set NEXT_PUBLIC_DOWNLOAD_URL to the real APK URL.
yarn dev
```
Expected: server at `http://localhost:3010`.

Manual checks:
- Compare layout/feel to `ref/navpay/01_落地页_下载按钮.png`.
- Check `http://localhost:3010/?invi=ABC123`:
  - Both "Download" buttons link to `...apk?invi=ABC123` (or `&invi=...` if base already has params).

**Step 8: Run quality gates**

Run:
```bash
cd navpay-landing
yarn lint
yarn typecheck
yarn test
```
Expected: all PASS.

**Step 9: Commit**

Run:
```bash
cd navpay-landing
git add src next.config.ts eslint.config.mjs postcss.config.mjs tsconfig.json vitest.config.ts .env.example README.md .gitignore
git commit -m "feat(landing): add navpay-android landing page UI"
```

---

### Task 6: Push to `~/git-remote/navpay-landing`

**Files:** none (git metadata)

**Step 1: Push**

Run:
```bash
cd navpay-landing
git push -u origin main
```
Expected: push succeeds to local bare remote.

**Step 2: Verify remote**

Run:
```bash
cd navpay-landing
git remote -v
git log --oneline --decorate -n 5
```
Expected: `origin` points to `~/git-remote/navpay-landing` and commits exist.

---

## Notes / Follow-ups (Optional)

- If you later need the exact MovPay branding (logo/art), add assets under `navpay-landing/public/` and replace `Header` logo + `HeroIllustration`.
- If you need Android APK hosting or a dynamic download endpoint, keep the contract as `NEXT_PUBLIC_DOWNLOAD_URL` and avoid hardcoding URLs in UI.
