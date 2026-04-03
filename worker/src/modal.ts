import { RECIPES } from "./recipes";
import type { Recipe } from "./recipes";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Truncate a string, adding ellipsis if needed. */
function truncate(s: string, maxLen: number): string {
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "\u2026";
}

// ---------------------------------------------------------------------------
// Modal view builder
// ---------------------------------------------------------------------------

/** Build static option_groups for the recipe selector. */
function buildRecipeOptionGroups(): object[] {
  const groups: Array<{ label: { type: string; text: string }; options: object[] }> = [];

  // Group recipes by input count
  const byInputs = new Map<number, Recipe[]>();
  for (const r of RECIPES) {
    const list = byInputs.get(r.inputs);
    if (list) list.push(r);
    else byInputs.set(r.inputs, [r]);
  }

  // Random option first
  groups.push({
    label: { type: "plain_text", text: "Special" },
    options: [{ text: { type: "plain_text", text: "\ud83c\udfb2 Random" }, value: "random" }],
  });

  // Then by input count ascending
  for (const count of [...byInputs.keys()].sort((a, b) => a - b)) {
    const recipes = byInputs.get(count)!;
    groups.push({
      label: { type: "plain_text", text: `${count} inputs` },
      options: recipes.map((r) => ({
        text: { type: "plain_text", text: truncate(r.name, 75) },
        value: r.slug,
      })),
    });
  }

  return groups;
}

/** Build the Slack modal view object for `views.open`. */
export function buildModalView(channelId: string = ""): object {
  return {
    type: "modal",
    callback_id: "sparagmos_run",
    private_metadata: channelId,
    title: { type: "plain_text", text: "Sparagmos" },
    submit: { type: "plain_text", text: "Destroy" },
    close: { type: "plain_text", text: "Cancel" },
    blocks: [
      // Recipe select (static with built-in Slack typeahead filtering)
      {
        type: "input",
        block_id: "recipe_block",
        optional: true,
        label: { type: "plain_text", text: "Recipe" },
        element: {
          type: "static_select",
          action_id: "recipe_select",
          placeholder: {
            type: "plain_text",
            text: "Search recipes or leave empty for Random",
          },
          option_groups: buildRecipeOptionGroups(),
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
      // Poster filter (native Slack user picker)
      {
        type: "input",
        block_id: "poster_block",
        optional: true,
        label: { type: "plain_text", text: "Poster" },
        element: {
          type: "users_select",
          action_id: "poster_filter",
          placeholder: { type: "plain_text", text: "Anyone" },
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
