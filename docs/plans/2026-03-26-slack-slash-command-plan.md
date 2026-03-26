# Slack Slash Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/sparagmos` Slack slash command that triggers image generation via the existing GitHub Actions workflow, and fix Slack URL unfurling so only the output image renders.

**Architecture:** A Cloudflare Worker acts as a thin shim between Slack and the GitHub Actions API. It verifies Slack request signatures, validates recipe names, and dispatches `workflow_dispatch` events. A small fix in `cli.py` suppresses URL unfurling on posted messages.

**Tech Stack:** Cloudflare Workers (JS/TypeScript), Wrangler CLI, existing Python codebase (slack_sdk)

---

## File Structure

### New files (Cloudflare Worker)
- `worker/src/index.ts` — Main Worker entry point: request verification, routing, GitHub dispatch
- `worker/src/recipes.ts` — Static recipe list with input counts (exported const)
- `worker/wrangler.toml` — Wrangler configuration
- `worker/package.json` — Dependencies (none beyond wrangler)
- `worker/tsconfig.json` — TypeScript config for Workers

### Modified files
- `sparagmos/cli.py` — Add `chat_update` call to suppress unfurling after `files_upload_v2`

### Test files
- `worker/src/index.test.ts` — Worker handler tests (Vitest, built into Wrangler)
- `tests/test_slack.py` — Add test for unfurl suppression

---

### Task 1: Scaffold the Cloudflare Worker

**Files:**
- Create: `worker/package.json`
- Create: `worker/wrangler.toml`
- Create: `worker/tsconfig.json`
- Create: `worker/src/index.ts` (minimal hello-world)

- [ ] **Step 1: Create `worker/package.json`**

```json
{
  "name": "sparagmos-slash-command",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "test": "vitest run"
  },
  "devDependencies": {
    "wrangler": "^4",
    "vitest": "^3",
    "@cloudflare/vitest-pool-workers": "^0.8"
  }
}
```

- [ ] **Step 2: Create `worker/wrangler.toml`**

```toml
name = "sparagmos-slash-command"
main = "src/index.ts"
compatibility_date = "2026-03-26"

[vars]
# Non-secret config vars can go here

# Secrets are set via `wrangler secret put`:
# wrangler secret put SLACK_SIGNING_SECRET
# wrangler secret put GITHUB_TOKEN
```

- [ ] **Step 3: Create `worker/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,
    "lib": ["ES2022"],
    "types": ["@cloudflare/workers-types"]
  },
  "include": ["src/**/*.ts"]
}
```

- [ ] **Step 4: Create minimal `worker/src/index.ts`**

```typescript
export interface Env {
  SLACK_SIGNING_SECRET: string;
  GITHUB_TOKEN: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return new Response("sparagmos worker is alive", { status: 200 });
  },
};
```

- [ ] **Step 5: Install dependencies and verify**

```bash
cd worker && npm install
npx wrangler dev --local
# In another terminal:
curl http://localhost:8787
# Expected: "sparagmos worker is alive"
```

- [ ] **Step 6: Commit**

```bash
git add worker/
git commit -m "feat: scaffold Cloudflare Worker for slash command

Add minimal Worker project with wrangler config, TypeScript setup,
and hello-world handler. This will become the shim between Slack
slash commands and GitHub Actions workflow_dispatch."
```

---

### Task 2: Add the static recipe list

**Files:**
- Create: `worker/src/recipes.ts`

- [ ] **Step 1: Create `worker/src/recipes.ts`**

```typescript
export interface Recipe {
  slug: string;
  inputs: number;
}

export const RECIPES: Recipe[] = [
  { slug: "acid-wash", inputs: 3 },
  { slug: "binary-archaeology", inputs: 4 },
  { slug: "broadcast-static", inputs: 3 },
  { slug: "broken-mirror", inputs: 5 },
  { slug: "chimera-engine", inputs: 5 },
  { slug: "collage-surgery", inputs: 4 },
  { slug: "contrast-surgery", inputs: 4 },
  { slug: "cutout-mosaic", inputs: 5 },
  { slug: "data-rot", inputs: 3 },
  { slug: "dissolve-cascade", inputs: 4 },
  { slug: "double-exposure", inputs: 2 },
  { slug: "dream-dissolve", inputs: 2 },
  { slug: "edge-ghosts", inputs: 3 },
  { slug: "edge-lattice", inputs: 5 },
  { slug: "entropy-garden", inputs: 5 },
  { slug: "exquisite-corpse", inputs: 3 },
  { slug: "feedback-loop", inputs: 2 },
  { slug: "fossil-record", inputs: 3 },
  { slug: "fragment-storm", inputs: 5 },
  { slug: "holographic-interference", inputs: 3 },
  { slug: "kaleidoscope-collapse", inputs: 5 },
  { slug: "letterpress", inputs: 4 },
  { slug: "mask-cascade", inputs: 4 },
  { slug: "mask-feedback", inputs: 5 },
  { slug: "mosaic-dissolution", inputs: 5 },
  { slug: "mosaic-rebirth", inputs: 5 },
  { slug: "negative-space", inputs: 4 },
  { slug: "neural-chimera", inputs: 3 },
  { slug: "noise-cathedral", inputs: 4 },
  { slug: "palimpsest", inputs: 4 },
  { slug: "palimpsest-ii", inputs: 5 },
  { slug: "phantom-limb", inputs: 2 },
  { slug: "photogram", inputs: 4 },
  { slug: "sediment-core", inputs: 3 },
  { slug: "shape-imposition", inputs: 5 },
  { slug: "signal-bleed", inputs: 3 },
  { slug: "silhouette-swap", inputs: 5 },
  { slug: "spectral-merge", inputs: 2 },
  { slug: "stamp-collection", inputs: 5 },
  { slug: "stencil-burn", inputs: 4 },
  { slug: "stratum-shift", inputs: 4 },
  { slug: "surveillance-decay", inputs: 4 },
  { slug: "tectonic-overlap", inputs: 4 },
  { slug: "text-ghost", inputs: 4 },
  { slug: "torn-collage", inputs: 4 },
  { slug: "voronoi-chimera", inputs: 3 },
  { slug: "wax-museum", inputs: 3 },
  { slug: "x-ray-composite", inputs: 2 },
];

const RECIPE_SET = new Set(RECIPES.map((r) => r.slug));

export function isValidRecipe(slug: string): boolean {
  return RECIPE_SET.has(slug);
}

export function formatRecipeList(): string {
  const grouped: Record<number, string[]> = {};
  for (const r of RECIPES) {
    if (!grouped[r.inputs]) grouped[r.inputs] = [];
    grouped[r.inputs].push(r.slug);
  }

  const lines: string[] = ["*Available recipes:*\n"];
  for (const count of Object.keys(grouped).map(Number).sort()) {
    lines.push(`*${count}-input:*`);
    lines.push(grouped[count].join(", "));
    lines.push("");
  }
  return lines.join("\n");
}

export function suggestRecipes(input: string): string[] {
  return RECIPES.map((r) => r.slug).filter(
    (slug) => slug.includes(input) || input.includes(slug)
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add worker/src/recipes.ts
git commit -m "feat: add static recipe list for Worker validation

48 recipes with input counts. Includes validation, formatted list
output for /sparagmos list, and substring-based suggestion for
invalid recipe names."
```

---

### Task 3: Implement Slack request signature verification

**Files:**
- Modify: `worker/src/index.ts`

- [ ] **Step 1: Add signature verification to `worker/src/index.ts`**

Replace the entire file content:

```typescript
import { RECIPES, isValidRecipe, formatRecipeList, suggestRecipes } from "./recipes";

export interface Env {
  SLACK_SIGNING_SECRET: string;
  GITHUB_TOKEN: string;
}

async function verifySlackSignature(
  request: Request,
  signingSecret: string
): Promise<{ valid: boolean; body: string }> {
  const timestamp = request.headers.get("X-Slack-Request-Timestamp") || "";
  const signature = request.headers.get("X-Slack-Signature") || "";
  const body = await request.text();

  // Reject requests older than 5 minutes to prevent replay attacks
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - parseInt(timestamp, 10)) > 300) {
    return { valid: false, body };
  }

  const baseString = `v0:${timestamp}:${body}`;
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(baseString));
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const expected = `v0=${hex}`;

  // Constant-time comparison
  if (expected.length !== signature.length) {
    return { valid: false, body };
  }
  const a = encoder.encode(expected);
  const b = encoder.encode(signature);
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) {
    mismatch |= a[i] ^ b[i];
  }
  return { valid: mismatch === 0, body };
}

function slackResponse(text: string, ephemeral = true): Response {
  return new Response(
    JSON.stringify({
      response_type: ephemeral ? "ephemeral" : "in_channel",
      text,
    }),
    {
      headers: { "Content-Type": "application/json" },
    }
  );
}

async function dispatchWorkflow(env: Env, recipe: string): Promise<boolean> {
  const response = await fetch(
    "https://api.github.com/repos/au-supply/sparagmos/actions/workflows/sparagmos.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "sparagmos-slash-command",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: { recipe },
      }),
    }
  );
  // GitHub returns 204 No Content on success
  return response.status === 204;
}

const HELP_TEXT = `*Usage:*
\`/sparagmos\` — generate with a random recipe
\`/sparagmos <recipe-name>\` — generate with a specific recipe
\`/sparagmos list\` — show available recipes
\`/sparagmos help\` — show this message

Result will be posted to #img-junkyard when processing completes (~2-5 min).`;

async function handleSlashCommand(body: string, env: Env): Promise<Response> {
  const params = new URLSearchParams(body);
  const text = (params.get("text") || "").trim().toLowerCase();

  // Route: help
  if (text === "help") {
    return slackResponse(HELP_TEXT);
  }

  // Route: list
  if (text === "list") {
    return slackResponse(formatRecipeList());
  }

  // Route: specific recipe or random
  const recipe = text;

  if (recipe && !isValidRecipe(recipe)) {
    const suggestions = suggestRecipes(recipe);
    let msg = `Unknown recipe: \`${recipe}\`.`;
    if (suggestions.length > 0) {
      msg += `\nDid you mean: ${suggestions.map((s) => `\`${s}\``).join(", ")}?`;
    }
    msg += `\nUse \`/sparagmos list\` to see all recipes.`;
    return slackResponse(msg);
  }

  const ok = await dispatchWorkflow(env, recipe);
  if (!ok) {
    return slackResponse("Failed to trigger workflow. Check GitHub token permissions.");
  }

  const label = recipe || "a random recipe";
  return slackResponse(`🎰 Firing up ${label}... result will appear in #img-junkyard in ~2-5 min.`);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Only accept POST to /slack/commands
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/slack/commands") {
      return new Response("Not found", { status: 404 });
    }

    // Verify Slack signature
    const { valid, body } = await verifySlackSignature(request, env.SLACK_SIGNING_SECRET);
    if (!valid) {
      return new Response("Invalid signature", { status: 401 });
    }

    return handleSlashCommand(body, env);
  },
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd worker && npx wrangler dev --local
# Should start without errors. Ctrl+C to stop.
```

- [ ] **Step 3: Commit**

```bash
git add worker/src/index.ts
git commit -m "feat: implement slash command handler

Routes /sparagmos, /sparagmos <recipe>, /sparagmos list, and
/sparagmos help. Verifies Slack request signatures with HMAC-SHA256
and constant-time comparison. Dispatches GitHub Actions
workflow_dispatch via the REST API. Returns ephemeral responses."
```

---

### Task 4: Add Worker tests

**Files:**
- Create: `worker/vitest.config.ts`
- Create: `worker/src/index.test.ts`

- [ ] **Step 1: Create `worker/vitest.config.ts`**

```typescript
import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        wrangler: { configPath: "./wrangler.toml" },
      },
    },
  },
});
```

- [ ] **Step 2: Add workers-types to devDependencies**

In `worker/package.json`, add to `devDependencies`:

```json
"@cloudflare/workers-types": "^4"
```

Then run:

```bash
cd worker && npm install
```

- [ ] **Step 3: Create `worker/src/index.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { isValidRecipe, formatRecipeList, suggestRecipes, RECIPES } from "./recipes";

// --- Recipe module unit tests ---

describe("isValidRecipe", () => {
  it("returns true for known recipes", () => {
    expect(isValidRecipe("mosaic-dissolution")).toBe(true);
    expect(isValidRecipe("acid-wash")).toBe(true);
  });

  it("returns false for unknown recipes", () => {
    expect(isValidRecipe("nonexistent")).toBe(false);
    expect(isValidRecipe("")).toBe(false);
  });
});

describe("formatRecipeList", () => {
  it("groups recipes by input count", () => {
    const list = formatRecipeList();
    expect(list).toContain("2-input:");
    expect(list).toContain("3-input:");
    expect(list).toContain("4-input:");
    expect(list).toContain("5-input:");
    expect(list).toContain("mosaic-dissolution");
    expect(list).toContain("acid-wash");
  });
});

describe("suggestRecipes", () => {
  it("suggests recipes containing the input", () => {
    const suggestions = suggestRecipes("mosaic");
    expect(suggestions).toContain("mosaic-dissolution");
    expect(suggestions).toContain("mosaic-rebirth");
  });

  it("returns empty for no matches", () => {
    const suggestions = suggestRecipes("zzzzzzz");
    expect(suggestions).toEqual([]);
  });
});

describe("RECIPES", () => {
  it("has 48 recipes", () => {
    expect(RECIPES.length).toBe(48);
  });

  it("all slugs are lowercase kebab-case", () => {
    for (const r of RECIPES) {
      expect(r.slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
    }
  });

  it("all input counts are 2-5", () => {
    for (const r of RECIPES) {
      expect(r.inputs).toBeGreaterThanOrEqual(2);
      expect(r.inputs).toBeLessThanOrEqual(5);
    }
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd worker && npm test
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add worker/vitest.config.ts worker/src/index.test.ts worker/package.json worker/package-lock.json
git commit -m "test: add Worker recipe validation and formatting tests

Unit tests for isValidRecipe, formatRecipeList, suggestRecipes,
and RECIPES data integrity (count, slug format, input ranges)."
```

---

### Task 5: Fix Slack URL unfurling in sparagmos posting

**Files:**
- Modify: `sparagmos/cli.py:323-329`
- Modify: `tests/test_slack.py` (add unfurl test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_slack.py`:

```python
def test_post_suppresses_unfurls(tmp_path):
    """After files_upload_v2, chat_update is called with unfurl_* = False."""
    client = MagicMock()
    # files_upload_v2 returns a file object; the posted message ts
    # comes from the file's shares
    client.files_upload_v2.return_value = {
        "ok": True,
        "file": {
            "shares": {
                "public": {
                    "C456": [{"ts": "1234567890.123456"}]
                }
            }
        },
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "dummy", "description": "test"}],
    )
    source = {"user": "U123", "date": "2026-01-15"}

    post_result(client, "C456", result, source, "image-gen", tmp_path)

    client.chat_update.assert_called_once()
    update_kwargs = client.chat_update.call_args[1]
    assert update_kwargs["unfurl_links"] is False
    assert update_kwargs["unfurl_media"] is False
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/jake/au-supply/sparagmos && python -m pytest tests/test_slack.py::test_post_suppresses_unfurls -v
```

Expected: FAIL — `chat_update` is never called.

- [ ] **Step 3: Implement the unfurl fix in `slack_post.py`**

Modify the `post_result` function in `sparagmos/slack_post.py`. After the `files_upload_v2` call, extract the message timestamp from the file's share data and call `chat_update`:

In `sparagmos/slack_post.py`, replace the `post_result` function body (lines 107-146) with:

```python
def post_result(
    client: WebClient,
    channel_id: str,
    result: PipelineResult,
    source: dict,
    source_channel_name: str,
    temp_dir: Path,
) -> str:
    """Post a processed image to Slack as a single message.

    Uses files_upload_v2 with initial_comment to combine image and
    text in one message (no threads). Suppresses URL unfurling so
    only the output image renders (not source image previews).

    Args:
        client: Slack WebClient.
        channel_id: Target channel ID (#img-junkyard).
        result: Pipeline result with image and metadata.
        source: Source image metadata.
        source_channel_name: Name of source channel for attribution.
        temp_dir: Temp directory for saving the image file.

    Returns:
        Message timestamp of the posted message.
    """
    comment = format_provenance(result, source, source_channel_name)

    # Save image to temp file for upload
    image_path = temp_dir / "sparagmos_output.png"
    result.image.save(image_path, "PNG")

    logger.info("Posting to channel %s with comment:\n%s", channel_id, comment)

    response = client.files_upload_v2(
        channel=channel_id,
        file=str(image_path),
        filename="sparagmos.png",
        initial_comment=comment,
    )

    # Extract posted message timestamp from file share data
    posted_ts = ""
    file_obj = response.get("file", {})
    shares = file_obj.get("shares", {})
    public_shares = shares.get("public", {})
    channel_shares = public_shares.get(channel_id, [])
    if channel_shares:
        posted_ts = channel_shares[0].get("ts", "")

    # Suppress unfurling so source image permalink URLs don't render
    # as image previews — only the output image should display
    if posted_ts:
        try:
            client.chat_update(
                channel=channel_id,
                ts=posted_ts,
                text=comment,
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception:
            logger.warning("Failed to suppress unfurls, continuing")

    return posted_ts
```

- [ ] **Step 4: Also update `cli.py` to extract ts from the same share structure**

In `sparagmos/cli.py`, the inline posting code (lines 323-329) does the same thing but without `post_result`. Update it to also suppress unfurls. Replace lines 323-329:

```python
            response = client.files_upload_v2(
                channel=junkyard_id,
                file=str(image_path),
                filename="sparagmos.png",
                initial_comment=comment,
            )

            # Extract ts from file share data
            posted_ts = ""
            file_obj = response.get("file", {})
            shares = file_obj.get("shares", {})
            public_shares = shares.get("public", {})
            channel_shares = public_shares.get(junkyard_id, [])
            if channel_shares:
                posted_ts = channel_shares[0].get("ts", "")

            # Suppress URL unfurling so only the output image renders
            if posted_ts:
                try:
                    client.chat_update(
                        channel=junkyard_id,
                        ts=posted_ts,
                        text=comment,
                        unfurl_links=False,
                        unfurl_media=False,
                    )
                except Exception:
                    logger.warning("Failed to suppress unfurls, continuing")
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd /Users/jake/au-supply/sparagmos && python -m pytest tests/test_slack.py -v
```

Expected: All tests pass, including the new `test_post_suppresses_unfurls`.

- [ ] **Step 6: Commit**

```bash
git add sparagmos/slack_post.py sparagmos/cli.py tests/test_slack.py
git commit -m "fix: suppress Slack URL unfurling on posted images

After files_upload_v2, call chat_update with unfurl_links=False
and unfurl_media=False so that source image permalink URLs render
as plain text links instead of image previews. Only the output
image should display in the message."
```

---

### Task 6: Deploy Worker and configure Slack app (manual steps)

This task is a checklist of manual steps — no code changes.

- [ ] **Step 1: Create a Cloudflare account (if needed)**

Go to https://dash.cloudflare.com/sign-up — free, no credit card.

- [ ] **Step 2: Deploy the Worker**

```bash
cd worker
npx wrangler login
npx wrangler deploy
```

Note the deployed URL (e.g., `https://sparagmos-slash-command.<account>.workers.dev`).

- [ ] **Step 3: Set Worker secrets**

```bash
npx wrangler secret put SLACK_SIGNING_SECRET
# Paste the signing secret from Slack app settings → Basic Information → Signing Secret

npx wrangler secret put GITHUB_TOKEN
# Paste a fine-grained PAT from doo-nothing account:
#   Repository: au-supply/sparagmos
#   Permissions: Actions (read & write)
```

- [ ] **Step 4: Configure the Slack slash command**

In https://api.slack.com/apps → your app:
1. **Slash Commands** → **Create New Command**
   - Command: `/sparagmos`
   - Request URL: `https://sparagmos-slash-command.<account>.workers.dev/slack/commands`
   - Short Description: "Generate a sparagmos image"
   - Usage Hint: `[recipe-name | list | help]`
2. **OAuth & Permissions** → ensure `commands` scope is present
3. **Reinstall** the app to the workspace

- [ ] **Step 5: End-to-end test**

In Slack:
1. `/sparagmos help` → should see usage text
2. `/sparagmos list` → should see recipes grouped by input count
3. `/sparagmos nonexistent` → should see error with suggestions
4. `/sparagmos mosaic-dissolution` → should see ack, then result in #img-junkyard ~2-5 min later
5. `/sparagmos` → should see ack with "random recipe", then result in #img-junkyard

- [ ] **Step 6: Verify unfurl fix**

After a generation completes and posts to #img-junkyard, confirm:
- Only 1 image (the output) displays
- The "originals: view · view · view" links are clickable text, not image previews

---

### Task 7: Update documentation

**Files:**
- Modify: `README.md` (if it exists, add slash command docs)
- Modify: `docs/plans/2026-03-26-slack-slash-command-design.md` (mark as implemented)

- [ ] **Step 1: Add slash command usage to README**

Add a section documenting the `/sparagmos` slash command with usage examples.

- [ ] **Step 2: Mark design doc status as Implemented**

In `docs/plans/2026-03-26-slack-slash-command-design.md`, change `**Status:** Draft` to `**Status:** Implemented`.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/plans/2026-03-26-slack-slash-command-design.md
git commit -m "docs: add slash command usage and mark design as implemented"
```
