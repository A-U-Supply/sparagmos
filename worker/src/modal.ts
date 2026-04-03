import { RECIPES } from "./recipes";
import type { Recipe } from "./recipes";
import { getFavorites, getRatings } from "./kv";
import type { RatingData } from "./kv";

// ---------------------------------------------------------------------------
// Modal view builder
// ---------------------------------------------------------------------------

/** Build the Slack modal view object for `views.open`. */
export function buildModalView(): object {
  return {
    type: "modal",
    callback_id: "sparagmos_run",
    title: { type: "plain_text", text: "Sparagmos" },
    submit: { type: "plain_text", text: "Destroy" },
    close: { type: "plain_text", text: "Cancel" },
    blocks: [
      // Recipe select (external data source for typeahead)
      {
        type: "input",
        block_id: "recipe_block",
        optional: true,
        label: { type: "plain_text", text: "Recipe" },
        element: {
          type: "external_select",
          action_id: "recipe_select",
          placeholder: {
            type: "plain_text",
            text: "Search recipes or leave empty for Random",
          },
          min_query_length: 0,
        },
      },
      // Image URLs (optional multiline text)
      {
        type: "input",
        block_id: "urls_block",
        optional: true,
        label: { type: "plain_text", text: "Image URLs" },
        element: {
          type: "plain_text_input",
          action_id: "image_urls",
          multiline: true,
          placeholder: {
            type: "plain_text",
            text: "Paste URLs, one per line (optional)",
          },
        },
      },
      // Poster filter
      {
        type: "input",
        block_id: "poster_block",
        optional: true,
        label: { type: "plain_text", text: "Poster" },
        element: {
          type: "static_select",
          action_id: "poster_filter",
          placeholder: { type: "plain_text", text: "Anyone" },
          options: [
            {
              text: { type: "plain_text", text: "Anyone" },
              value: "anyone",
            },
          ],
        },
      },
      // Age filter
      {
        type: "input",
        block_id: "age_block",
        optional: true,
        label: { type: "plain_text", text: "Age" },
        element: {
          type: "static_select",
          action_id: "age_filter",
          placeholder: { type: "plain_text", text: "Any time" },
          options: [
            {
              text: { type: "plain_text", text: "Any time" },
              value: "any",
            },
            {
              text: { type: "plain_text", text: "Last 24 hours" },
              value: "24h",
            },
            {
              text: { type: "plain_text", text: "Last 7 days" },
              value: "7d",
            },
            {
              text: { type: "plain_text", text: "Last 30 days" },
              value: "30d",
            },
            {
              text: { type: "plain_text", text: "1-3 months ago" },
              value: "1-3mo",
            },
            {
              text: { type: "plain_text", text: "3-6 months ago" },
              value: "3-6mo",
            },
            {
              text: { type: "plain_text", text: "6-12 months ago" },
              value: "6-12mo",
            },
            {
              text: { type: "plain_text", text: "Over 1 year ago" },
              value: "1y+",
            },
            {
              text: { type: "plain_text", text: "Over 2 years ago" },
              value: "2y+",
            },
            {
              text: {
                type: "plain_text",
                text: "The deep cut (oldest 50)",
              },
              value: "oldest50",
            },
          ],
        },
      },
      // Freshness filter
      {
        type: "input",
        block_id: "freshness_block",
        optional: true,
        label: { type: "plain_text", text: "Freshness" },
        element: {
          type: "static_select",
          action_id: "freshness_filter",
          placeholder: {
            type: "plain_text",
            text: "Prefer fresh for recipe",
          },
          options: [
            {
              text: { type: "plain_text", text: "No preference" },
              value: "none",
            },
            {
              text: {
                type: "plain_text",
                text: "Prefer fresh for recipe",
              },
              value: "prefer_fresh_recipe",
            },
            {
              text: {
                type: "plain_text",
                text: "Only fresh for recipe",
              },
              value: "only_fresh_recipe",
            },
            {
              text: {
                type: "plain_text",
                text: "Only used with recipe (remix)",
              },
              value: "only_used_recipe",
            },
            {
              text: { type: "plain_text", text: "Prefer untouched" },
              value: "prefer_untouched",
            },
            {
              text: { type: "plain_text", text: "Only untouched" },
              value: "only_untouched",
            },
            {
              text: {
                type: "plain_text",
                text: "Only veterans (3+ recipes)",
              },
              value: "only_veterans",
            },
          ],
        },
      },
      // Rating filter
      {
        type: "input",
        block_id: "rating_block",
        optional: true,
        label: { type: "plain_text", text: "Rating" },
        element: {
          type: "static_select",
          action_id: "rating_filter",
          placeholder: { type: "plain_text", text: "All recipes" },
          options: [
            {
              text: { type: "plain_text", text: "All recipes" },
              value: "all",
            },
            {
              text: {
                type: "plain_text",
                text: "Top rated (+3 or higher)",
              },
              value: "top",
            },
            {
              text: { type: "plain_text", text: "Positive only" },
              value: "positive",
            },
            {
              text: { type: "plain_text", text: "Unrated" },
              value: "unrated",
            },
            {
              text: {
                type: "plain_text",
                text: "Underdogs (below 0)",
              },
              value: "underdogs",
            },
          ],
        },
      },
      // Footer context
      {
        type: "context",
        elements: [
          {
            type: "mrkdwn",
            text: `_${RECIPES.length} recipes available_`,
          },
        ],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Typeahead options builder
// ---------------------------------------------------------------------------

/** Truncate a string to maxLen chars, adding ellipsis if needed. */
function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "\u2026";
}

/** Format a recipe as a Slack option for external_select. */
function recipeToOption(
  recipe: Recipe,
  ratings: Record<string, RatingData>,
): { text: { type: string; text: string }; description?: { type: string; text: string }; value: string } {
  const rating = ratings[recipe.slug];
  const scoreStr = rating && rating.score !== 0
    ? ` [${rating.score > 0 ? "+" : ""}${rating.score}]`
    : "";
  const text = truncate(
    `${recipe.name} (${recipe.inputs} inputs)${scoreStr}`,
    75,
  );
  const option: {
    text: { type: string; text: string };
    description?: { type: string; text: string };
    value: string;
  } = {
    text: { type: "plain_text", text },
    value: recipe.slug,
  };
  // Add effects chain as description (max 75 chars)
  if (recipe.effects) {
    option.description = {
      type: "plain_text",
      text: truncate(recipe.effects, 75),
    };
  }
  return option;
}

/**
 * Build typeahead option groups for the recipe external_select.
 *
 * Called on `block_suggestion` payloads when the user types in the
 * recipe selector. Returns option_groups with Random, Favorites,
 * and per-input-count groups.
 */
export async function buildTypeaheadOptions(
  query: string,
  userId: string,
  kv: KVNamespace,
): Promise<object> {
  const [favorites, ratings] = await Promise.all([
    getFavorites(kv, userId),
    getRatings(kv),
  ]);

  const lowerQuery = query.toLowerCase();

  // Filter recipes matching query (by slug or name)
  const matched = RECIPES.filter(
    (r) =>
      r.slug.includes(lowerQuery) ||
      r.name.toLowerCase().includes(lowerQuery),
  );

  // Sort helper: by rating score descending
  const byScore = (a: Recipe, b: Recipe): number => {
    const sa = ratings[a.slug]?.score ?? 0;
    const sb = ratings[b.slug]?.score ?? 0;
    return sb - sa;
  };

  const groups: Array<{
    label: { type: string; text: string };
    options: Array<object>;
  }> = [];

  // Random option (always present)
  groups.push({
    label: { type: "plain_text", text: "Special" },
    options: [
      {
        text: { type: "plain_text", text: "Random" },
        description: {
          type: "plain_text",
          text: "Let fate decide",
        },
        value: "random",
      },
    ],
  });

  // Favorites group
  const favSet = new Set(favorites);
  const favMatched = matched
    .filter((r) => favSet.has(r.slug))
    .sort(byScore);
  if (favMatched.length > 0) {
    groups.push({
      label: { type: "plain_text", text: "Favorites" },
      options: favMatched.map((r) => recipeToOption(r, ratings)),
    });
  }

  // Group by input count
  const byInputs = new Map<number, Recipe[]>();
  for (const r of matched) {
    const list = byInputs.get(r.inputs);
    if (list) {
      list.push(r);
    } else {
      byInputs.set(r.inputs, [r]);
    }
  }

  const sortedCounts = [...byInputs.keys()].sort((a, b) => a - b);
  for (const count of sortedCounts) {
    const recipes = byInputs.get(count)!.sort(byScore);
    groups.push({
      label: { type: "plain_text", text: `${count} inputs` },
      options: recipes.map((r) => recipeToOption(r, ratings)),
    });
  }

  // Slack limits external_select to 100 options total.
  // Trim from the end of the last groups if we exceed that.
  let total = 0;
  for (const g of groups) {
    total += g.options.length;
  }
  while (total > 100) {
    // Remove options from the last group
    const lastGroup = groups[groups.length - 1];
    if (lastGroup.options.length > 1) {
      lastGroup.options.pop();
      total--;
    } else {
      groups.pop();
      total--;
    }
  }

  // Remove any groups that ended up empty (shouldn't happen, but defensive)
  const nonEmpty = groups.filter((g) => g.options.length > 0);

  return { option_groups: nonEmpty };
}
