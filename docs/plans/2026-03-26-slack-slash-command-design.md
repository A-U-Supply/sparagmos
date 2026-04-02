# Slack Slash Command for Sparagmos

**Date:** 2026-03-26
**Status:** Implemented

## Context

Sparagmos runs daily via a GitHub Actions cron job: it picks a random recipe, pulls source images from #image-gen in Slack, processes them through an effect pipeline, and posts the result to #img-junkyard. The workflow also supports manual `workflow_dispatch` with a recipe input, but triggering it requires navigating to the GitHub Actions UI.

This design adds a `/sparagmos` Slack slash command so users can trigger generation directly from Slack. It also fixes the current posting format where Slack unfurls source image permalink URLs, causing 4-5 images to render instead of just the output.

## Architecture

```
Slack slash command
  → Cloudflare Worker (verify signature, validate recipe, dispatch)
    → GitHub Actions API (workflow_dispatch)
      → sparagmos.yml (existing workflow, no changes)
        → Posts result to #img-junkyard
```

The Worker is the only new infrastructure. It's a stateless shim (~100 lines of JS) that translates Slack slash commands into GitHub Actions workflow dispatches.

## Slash Command Interface

| Command | Behavior | Response type |
|---------|----------|---------------|
| `/sparagmos` | Trigger random recipe | Ephemeral: "🎰 Firing up a random recipe..." |
| `/sparagmos <recipe>` | Trigger specific recipe | Ephemeral: "🎰 Firing up <recipe>..." |
| `/sparagmos list` | Show available recipes | Ephemeral: formatted recipe list with input counts |
| `/sparagmos help` | Show usage info | Ephemeral: usage text |

For invalid recipe names, respond with an error and suggest similar names (basic fuzzy match or just list all recipes).

## Component 1: Cloudflare Worker

**Location:** New directory `worker/` in the sparagmos repo.

**Runtime:** Cloudflare Workers free tier (100k requests/day, 0ms cold start).

**Secrets (stored in Cloudflare Workers):**
- `SLACK_SIGNING_SECRET` — from the Slack app settings, used to verify incoming requests
- `GITHUB_TOKEN` — a GitHub PAT from the `doo-nothing` account with `actions:write` scope

**Request flow:**
1. Receive POST from Slack at `/slack/commands`
2. Verify the `X-Slack-Signature` header against `SLACK_SIGNING_SECRET`
3. Parse the `text` field from the form-encoded body
4. Route based on text content:
   - Empty → dispatch with empty recipe (random)
   - `list` → return recipe list
   - `help` → return usage info
   - Anything else → validate against known recipe list, then dispatch or return error
5. For dispatch: `POST https://api.github.com/repos/au-supply/sparagmos/actions/workflows/sparagmos.yml/dispatches` with `{ "ref": "main", "inputs": { "recipe": "<recipe>" } }`
6. Return JSON `{ "response_type": "ephemeral", "text": "..." }`

**Recipe list:** Baked into the Worker source as a static array. Updated when recipes are added (could be automated via CI later, but manual is fine to start).

**Current recipe list (48 recipes):**
acid-wash, binary-archaeology, broadcast-static, broken-mirror, chimera-engine, collage-surgery, contrast-surgery, cutout-mosaic, data-rot, dissolve-cascade, double-exposure, dream-dissolve, edge-ghosts, edge-lattice, entropy-garden, exquisite-corpse, feedback-loop, fossil-record, fragment-storm, holographic-interference, kaleidoscope-collapse, letterpress, mask-cascade, mask-feedback, mosaic-dissolution, mosaic-rebirth, negative-space, neural-chimera, noise-cathedral, palimpsest, palimpsest-ii, phantom-limb, photogram, sediment-core, shape-imposition, signal-bleed, silhouette-swap, spectral-merge, stamp-collection, stencil-burn, stratum-shift, surveillance-decay, tectonic-overlap, text-ghost, torn-collage, voronoi-chimera, wax-museum, x-ray-composite

## Component 2: Unfurl Fix (sparagmos repo)

**Problem:** When the bot posts to #img-junkyard, the `initial_comment` includes permalink URLs to source images (`originals: view · view · view`). Slack unfurls these into image previews, so the post shows 5 images instead of just the output.

**Fix:** After calling `files_upload_v2`, call `chat_update` on the resulting message with `unfurl_links=False` and `unfurl_media=False`. This suppresses Slack's automatic URL previews while keeping the text links clickable.

**File to modify:** `sparagmos/cli.py` (lines ~323-328)

**Approach:**
```python
response = client.files_upload_v2(
    channel=junkyard_id,
    file=str(image_path),
    filename="sparagmos.png",
    initial_comment=comment,
)

# Suppress unfurling of source image permalink URLs
# files_upload_v2 doesn't support unfurl_* params directly,
# so we update the message after posting
posted_ts = response.get("ts", "")
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

**Note:** `chat_update` requires the `chat:write` scope, which the bot already has.

## Component 3: Slack App Configuration (manual, one-time)

In the Slack app settings at https://api.slack.com/apps:

1. Navigate to **Slash Commands** → **Create New Command**
2. Set:
   - Command: `/sparagmos`
   - Request URL: `https://<worker-name>.workers.dev/slack/commands`
   - Short Description: "Generate a sparagmos image"
   - Usage Hint: `[recipe-name | list | help]`
3. Add the `commands` scope if not already present (under OAuth & Permissions)
4. Reinstall the app to the workspace

## Component 4: GitHub PAT

Create a fine-grained PAT for the `doo-nothing` GitHub account:
- Repository access: `au-supply/sparagmos` only
- Permissions: Actions (read & write)
- Store as a Cloudflare Worker secret

## What Does NOT Change

- `sparagmos.yml` workflow — already supports `workflow_dispatch` with `recipe` input
- Recipe system, pipeline, effects — untouched
- Slack source/posting logic — only the unfurl fix is added
- State tracking — works the same whether triggered by cron or slash command
- Daily cron schedule — continues as before

## Verification

1. **Worker:** Deploy, then test with `curl` simulating a Slack request (or use Slack's slash command test)
2. **Unfurl fix:** Trigger a generation and confirm the posted message shows only the output image
3. **End-to-end:** Type `/sparagmos mosaic-dissolution` in Slack → see ephemeral ack → wait ~3 min → see result in #img-junkyard
4. **List/help:** Type `/sparagmos list` and `/sparagmos help` → see formatted responses
5. **Validation:** Type `/sparagmos nonexistent-recipe` → see error with suggestions
