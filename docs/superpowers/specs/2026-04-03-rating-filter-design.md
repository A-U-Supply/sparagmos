# Rating Filter: Unified Checkboxes for Recipe Browsing & Selection

**Date:** 2026-04-03

## Problem

Three issues with the current rating system:

1. **Rating filter UI is dead** — the modal has a rating dropdown (All / Top / Positive / Unrated / Underdogs) but it's never extracted from form submission, never passed to the workflow, and never reaches the CLI. Pure decoration.

2. **`_load_ratings()` is broken** — `ratings.json` stores `{slug: {up, down, score, last_voted}}` but the parser expects `{slug: int}`. The `isinstance(v, (int, float))` check silently skips all entries, so weighted recipe selection has **never actually worked** — it always falls back to uniform random.

3. **No way to filter the recipe dropdown by rating** — the dropdown shows 100+ recipes with no way to narrow by quality while browsing.

## Solution: Unified Rating Checkboxes

Replace the broken rating dropdown with **checkboxes** that serve two purposes:
- **Browsing:** dynamically filter which recipes appear in the recipe dropdown via `views.update`
- **Random selection:** when no recipe is picked, the same checkboxes determine which pool the weighted random draws from

### Rating Categories

| Category | Criteria | Value |
|----------|----------|-------|
| Top rated | score >= 3 | `top` |
| Positive only | score > 0 | `positive` |
| Unrated | slug not in ratings or score == 0 | `unrated` |
| Underdogs | score < 0 | `underdogs` |

- None checked = all recipes (no filter)
- Multiple checked = union of matching recipes

## Design

### 1. Fix `_load_ratings()` (Bug fix)

**File:** `sparagmos/cli.py:109-125`

The parser does `int(v)` but `v` is a dict. Fix to extract `v["score"]` when `v` is a dict, fall back to `int(v)` for plain numbers.

### 2. Modal layout restructure

**File:** `worker/src/modal.ts`

New layout with titled sections:

```
Sparagmos
─────────────────────────
Pick a recipe and tweak the filters, then hit Destroy...

📊 Recipe
[Rating checkboxes: ☐ Top  ☐ Positive  ☐ Unrated  ☐ Underdogs]
[Recipe dropdown: 🎲 Random (pre-selected)]

🖼️ Images
[Image URLs]

🔍 Filters
[Poster] [Age] [Freshness]

─────────────────────────
🧰 Tools
_23 of 107 recipes shown_
[🏆 Best Mucks] [📌 My Pinned] [📡 Status] [❓ Help]
```

Changes:
- Replace `static_select` rating filter with `checkboxes` element
- Add `dispatch_action: true` on the checkboxes block so toggling fires `block_actions` immediately
- Pre-select "🎲 Random" in the recipe dropdown via `initial_option`
- Add section headers as `section` blocks with bold mrkdwn text
- Add divider before the tools section
- Move the recipe count context line into the tools section; make it dynamic (e.g., "23 of 107 recipes shown")
- Place checkboxes above the recipe dropdown within the Recipe section

### 3. Dynamic dropdown filtering via `views.update`

**Files:** `worker/src/interactions.ts`, `worker/src/modal.ts`

When rating checkboxes are toggled:
1. `block_actions` fires with `action_id: "rating_checkboxes"`
2. Worker reads selected checkbox values from `payload.view.state.values`
3. Worker fetches ratings from KV via `getRatings(env.RATINGS)`
4. Worker calls `buildRecipeOptionGroups(ratings, selectedFilters)` — modified to accept ratings and filter criteria, returning only matching recipes
5. Worker rebuilds the full modal view via `buildModalView(channelId, ratings, ratingFilters)` and calls `views.update` with the view ID from `payload.view.id`
6. Slack automatically preserves user input in other form fields

New helper: `updateView(env, viewId, view)` — similar to existing `pushView()` but calls `views.update` instead of `views.push`.

### 4. `buildModalView` signature change

**File:** `worker/src/modal.ts`

`buildModalView(channelId)` becomes `buildModalView(channelId, ratings?, ratingFilters?)`.

- `ratings`: `Record<string, RatingData>` from KV (optional — if not provided, no filtering)
- `ratingFilters`: `string[]` of selected filter values (optional — if empty/missing, show all)

`buildRecipeOptionGroups()` becomes `buildRecipeOptionGroups(ratings?, ratingFilters?)` with the same optional params. When filters are active, recipes that don't match any selected category are excluded from the option groups. Empty groups are omitted.

The recipe count context line uses the filtered count vs total: `"_23 of 107 recipes shown_"` or `"_107 recipes available_"` when unfiltered.

### 5. `openModal` fetches ratings

**File:** `worker/src/index.ts`

`openModal()` fetches ratings from KV before building the modal view, so the initial render has rating data available (needed for the count display and for potential pre-set filters).

### 6. Wire rating filter through the full pipeline

**Submission extraction** (`worker/src/interactions.ts`):
- Extract selected checkboxes from `vals.rating_block?.rating_checkboxes?.selected_options`
- Map to comma-separated string (e.g., `"top,unrated"`)
- Pass to `dispatchWorkflow()` as `filters.rating`

**Dispatch** (`worker/src/github.ts`):
- Add `if (filters?.rating) inputs.rating = filters.rating;`

**Workflow** (`.github/workflows/sparagmos.yml`):
- Add `rating` input with empty default
- Add CLI arg construction block

**CLI** (`sparagmos/cli.py`):
- Add `--rating` argument to parser (comma-separated values)
- New `_filter_by_rating(slugs, rating_values, ratings)` function
- Apply before `_pick_weighted_recipe()` — filter the slug list, then weighted-pick from the filtered set

### 7. Tests

- Fix existing `_load_ratings` tests to use nested dict format
- Test `_filter_by_rating()` with each category and combinations
- Test `buildRecipeOptionGroups()` filtering with mock ratings
