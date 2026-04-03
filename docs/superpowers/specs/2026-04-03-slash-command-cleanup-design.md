# Slash Command Cleanup: Modals, Help, Best, and Pinned Recipes

**Date:** 2026-04-03
**Status:** Design

## Context

Sparagmos recently gained a modal system (recipe select with filters, interactive voting/starring buttons in thread replies). But the slash command interface hasn't been updated to match:

- `/sparagmos help` still returns plain text and doesn't mention ratings, starring, pinning, modals, or filters
- `/sparagmos best` returns bare ephemeral text instead of a modal with links
- There's no way to browse starred posts with clickable links to the originals
- There's no way to see your pinned recipes
- The main modal (bare `/sparagmos`) doesn't tell users about other commands
- "Star" (per-post, Hall of Fame) and "Save Recipe" (per-recipe, personal) use confusingly similar star icons

This cleanup makes the slash command coherent with the modal-based features.

## Changes

### 1. Icon/Label Differentiation

Disambiguate Star (per-post) from Save (per-recipe):

| Feature | Old | New |
|---------|-----|-----|
| Star a post (Hall of Fame) | ⭐ Star / ⭐ Starred | ⭐ Star / ⭐ Starred (unchanged) |
| Save a recipe (personal) | ☆ Save Recipe / ★ Saved | 📌 Pin Recipe / 📌 Pinned |

Files: `sparagmos/slack_post.py` (initial render), `worker/src/interactions.ts` (rebuild after toggle).

### 2. Main Modal Footer Buttons

Add an `actions` block at the bottom of `buildModalView()`, before the recipe count context:

```
[ 🏆 Best Mucks ]  [ 📌 My Pinned Recipes ]  [ ❓ Help ]
```

Each button fires `block_actions` → handler calls `views.push` to show the relevant info modal on top. The main form stays intact underneath (Slack preserves the view stack). User clicks back arrow to return.

### 3. Best Mucks Modal

**Triggered by:** Footer button `modal_open_best` OR `/sparagmos best`

- Pushed modal view (close/back only, no submit)
- Fetches `StarData[]` from KV, sorted by `star_count` desc, top 20
- Each entry is a `section` block:
  ```
  ⭐ 3 — `mosaic-dissolution` (2026-04-01)
  ```
  With a "View" button linking to the Slack permalink of the original post.
- Permalink constructed: `https://{SLACK_WORKSPACE}.slack.com/archives/{channel}/p{ts_no_dot}`
- Requires `SLACK_WORKSPACE` env var (just the subdomain, e.g. `"myworkspace"` not the full URL)
- Empty state: "No starred posts yet. Star outputs in #img-junkyard threads to build the Hall of Fame!"

### 4. Pinned Recipes Modal

**Triggered by:** Footer button `modal_open_pinned`

- Pushed modal view (close/back only, no submit)
- Fetches user's favorites from KV via `getFavorites(userId)`
- Each entry is a `section` block with recipe name, input count, and a "Run" accessory button
- Run button dispatches the workflow, clears the modal stack, sends ephemeral confirmation
- Empty state: "No pinned recipes yet. Pin recipes from thread replies in #img-junkyard!"

### 5. Help Modal

**Triggered by:** Footer button `modal_open_help` OR `/sparagmos help`

- Pushed modal view (close/back only, no submit)
- Comprehensive reference in mrkdwn section blocks with dividers:
  1. **Quick Start** — `/sparagmos` opens modal, pick recipe, hit Destroy
  2. **Commands** — all slash commands with descriptions
  3. **The Modal** — recipe select, poster/age/freshness/rating filters explained
  4. **Rating & Voting** — 👍👎 in threads, how it affects the rating filter
  5. **⭐ Starring Posts** — star outputs in threads, builds Hall of Fame
  6. **📌 Pinning Recipes** — save recipes to personal collection, accessible from modal
  7. **Image URLs** — how to pass specific images, permalink copying
  8. **How It Works** — pipeline, timing (~2-5 min), results in #img-junkyard
  9. **Tips** — kebab-case, typo suggestions, more inputs = more chaos

### 6. `/sparagmos help` and `/sparagmos best` Open Modals

Currently these commands return ephemeral text. Change them to open modals instead:

- `help` command: needs `trigger_id` from the slash command params → `views.open` with help view
- `best` command: needs `trigger_id` → `views.open` with best mucks view
- These use `views.open` (not `views.push`) since they're top-level, not stacked on the form

## Technical Constraints

- **Max modal stack depth:** 3 views (we use at most 2: main form + pushed info view)
- **trigger_id expires in 3 seconds:** KV reads are sub-100ms on CF Workers
- **`actions` blocks don't conflict with `input` blocks** in the same modal — actions fire `block_actions`, inputs go to `view_submission`
- **Pushed views with only `close` (no `submit`)** show a back arrow automatically
- **100 blocks max per view** — help modal is the largest, ~20 blocks max
- **Pinned "Run" button:** dispatches workflow in `ctx.waitUntil`, then posts ephemeral confirmation. The modal doesn't auto-close (Slack's `response_action: "clear"` only works on `view_submission`, not `block_actions`), but user can close manually. Alternatively, could use `views.update` to replace the pushed view with a "Dispatched!" confirmation.

## Files to Modify

| File | Changes |
|------|---------|
| `worker/src/modal.ts` | Add footer `actions` block; add `buildBestView()`, `buildPinnedView()`, `buildHelpView()` |
| `worker/src/interactions.ts` | Handle `modal_open_best`, `modal_open_pinned`, `modal_open_help`, `run_pinned`; add `pushView()` helper; update pin label from ☆→📌 |
| `worker/src/index.ts` | `help` and `best` commands open modals via `views.open` (need `trigger_id` + `ctx.waitUntil`); remove or keep text fallback for no-trigger_id edge case |
| `worker/src/types.ts` | Add `SLACK_WORKSPACE` to `Env` interface |
| `worker/wrangler.toml` | Add `SLACK_WORKSPACE` variable |
| `sparagmos/slack_post.py` | Change `☆ Save Recipe` → `📌 Pin Recipe` in `_build_thread_blocks()` |

## Verification

1. **Pin label:** Run a recipe, check thread reply shows `📌 Pin Recipe` (not `☆ Save Recipe`)
2. **Main modal footer:** Type `/sparagmos` → modal has footer buttons
3. **Best Mucks:** Click 🏆 button → pushed modal shows starred posts with clickable links
4. **Pinned Recipes:** Click 📌 button → pushed modal shows pinned recipes with Run buttons
5. **Help:** Click ❓ button → comprehensive help modal
6. **`/sparagmos help`:** Opens help modal directly (not ephemeral text)
7. **`/sparagmos best`:** Opens best modal directly (not ephemeral text)
8. **Run from pinned:** Click Run on a pinned recipe → workflow dispatches, modal clears, ephemeral confirmation
9. **Back navigation:** From any pushed view, back arrow returns to main form with state preserved
