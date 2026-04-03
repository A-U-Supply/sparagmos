import { RECIPES, getRecipe } from "./recipes";
import type { Recipe } from "./recipes";
import type { RatingData, StarData } from "./kv";
import type { WorkflowRun } from "./types";
import { buildStatusBlocks } from "./blocks";

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

/** Check whether a recipe matches the active rating filters. */
function matchesRatingFilter(
  slug: string,
  ratings: Record<string, RatingData>,
  filters: string[],
): boolean {
  if (filters.length === 0) return true;
  const score = ratings[slug]?.score ?? 0;
  const isUnrated = !(slug in ratings) || score === 0;
  for (const f of filters) {
    if (f === "top" && score >= 3) return true;
    if (f === "positive" && score > 0) return true;
    if (f === "unrated" && isUnrated) return true;
    if (f === "underdogs" && score < 0) return true;
  }
  return false;
}

/** Build static option_groups for the recipe selector. */
function buildRecipeOptionGroups(
  ratings: Record<string, RatingData> = {},
  ratingFilters: string[] = [],
): object[] {
  const groups: Array<{ label: { type: string; text: string }; options: object[] }> = [];

  // Group recipes by input count, applying rating filter
  const byInputs = new Map<number, Recipe[]>();
  for (const r of RECIPES) {
    if (!matchesRatingFilter(r.slug, ratings, ratingFilters)) continue;
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

/** Count how many recipes pass the current rating filter. */
function countFilteredRecipes(
  ratings: Record<string, RatingData>,
  ratingFilters: string[],
): number {
  if (ratingFilters.length === 0) return RECIPES.length;
  return RECIPES.filter((r) => matchesRatingFilter(r.slug, ratings, ratingFilters)).length;
}

// ---------------------------------------------------------------------------
// Permalink helper
// ---------------------------------------------------------------------------

/** Build a Slack permalink from workspace subdomain, channel ID, and message ts. */
export function buildSlackPermalink(workspace: string, channel: string, ts: string): string {
  const tsNoDot = ts.replace(".", "");
  return `https://${workspace}.slack.com/archives/${channel}/p${tsNoDot}`;
}

// ---------------------------------------------------------------------------
// Info modal views (pushed on top of the main form)
// ---------------------------------------------------------------------------

/** Build the "Best Mucks" modal showing starred posts with permalink links. */
export function buildBestView(stars: StarData[], workspace: string): object {
  const blocks: object[] = [];

  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "\u2b50 Best Mucks", emoji: true },
  });

  if (stars.length === 0) {
    blocks.push({
      type: "section",
      text: {
        type: "mrkdwn",
        text: "No starred posts yet. Star outputs in #img-junkyard threads to build the Hall of Fame!",
      },
    });
  } else {
    const sorted = [...stars].sort((a, b) => b.star_count - a.star_count);
    blocks.push({
      type: "context",
      elements: [
        {
          type: "mrkdwn",
          text: `Top ${Math.min(sorted.length, 20)} starred outputs`,
        },
      ],
    });
    blocks.push({ type: "divider" });

    for (const star of sorted.slice(0, 20)) {
      const permalink = star.channel
        ? buildSlackPermalink(workspace, star.channel, star.posted_ts)
        : "";
      const block: any = {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `:star: *${star.star_count}* \u2014 \`${star.recipe}\` (${star.starred_date})`,
        },
      };
      if (permalink) {
        block.accessory = {
          type: "button",
          text: { type: "plain_text", text: "View" },
          url: permalink,
          action_id: `view_star:${star.posted_ts}`,
        };
      }
      blocks.push(block);
    }
  }

  return {
    type: "modal",
    callback_id: "sparagmos_best",
    title: { type: "plain_text", text: "Best Mucks" },
    close: { type: "plain_text", text: "Back" },
    blocks,
  };
}

/** Build the "My Pinned Recipes" modal showing a user's favorited recipes. */
export function buildPinnedView(favorites: string[]): object {
  const blocks: object[] = [];

  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "\ud83d\udccc My Pinned Recipes", emoji: true },
  });

  if (favorites.length === 0) {
    blocks.push({
      type: "section",
      text: {
        type: "mrkdwn",
        text: "No pinned recipes yet. Pin recipes from thread replies in #img-junkyard!",
      },
    });
  } else {
    blocks.push({
      type: "context",
      elements: [
        { type: "mrkdwn", text: `${favorites.length} pinned recipe${favorites.length === 1 ? "" : "s"}` },
      ],
    });
    blocks.push({ type: "divider" });

    for (const slug of favorites) {
      const recipe = getRecipe(slug);
      const name = recipe ? recipe.name : slug;
      const inputs = recipe ? `${recipe.inputs} input${recipe.inputs === 1 ? "" : "s"}` : "";
      blocks.push({
        type: "section",
        text: {
          type: "mrkdwn",
          text: `*${name}*${inputs ? ` (${inputs})` : ""}`,
        },
        accessory: {
          type: "button",
          text: { type: "plain_text", text: "\u25b6\ufe0f Run", emoji: true },
          action_id: "run_pinned",
          value: slug,
        },
      });
    }
  }

  return {
    type: "modal",
    callback_id: "sparagmos_pinned",
    title: { type: "plain_text", text: "Pinned Recipes" },
    close: { type: "plain_text", text: "Back" },
    blocks,
  };
}

/** Build the comprehensive Help modal. */
export function buildHelpView(): object {
  const inputCounts = [...new Set(RECIPES.map((r) => r.inputs))].sort(
    (a, b) => a - b,
  );
  const rangeStr =
    inputCounts.length > 1
      ? `${inputCounts[0]}\u2013${inputCounts[inputCounts.length - 1]}`
      : `${inputCounts[0]}`;

  const blocks: object[] = [];

  // Quick Start
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "Quick Start", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "Type `/sparagmos` and hit enter to open the recipe picker.",
        "Choose a recipe (or leave it on Random), tweak the filters, and hit *Destroy*.",
        "Results appear in #img-junkyard in ~2\u20135 minutes.",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // Commands
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "Commands", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "`/sparagmos` \u2014 Open the recipe picker modal",
        "`/sparagmos <recipe>` \u2014 Run a specific recipe directly",
        "`/sparagmos <recipe> <url1> [url2]...` \u2014 Run with specific images",
        "`/sparagmos list` \u2014 Show all recipes grouped by input count",
        "`/sparagmos best` \u2014 Hall of Fame (starred outputs)",
        "`/sparagmos status` \u2014 Recent workflow run status",
        "`/sparagmos help` \u2014 This help screen",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // The Modal
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "The Modal", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "*Recipe* \u2014 Pick a recipe or leave on Random. Type to search.",
        "*Image URLs* \u2014 Paste Slack image permalinks (one per line). If you provide fewer than the recipe needs, the rest are picked randomly from #image-gen.",
        "*Poster* \u2014 Only use images from a specific person.",
        "*Age* \u2014 Filter source images by how old they are.",
        "*Freshness* \u2014 Prefer images that haven't been used before, or remix veterans.",
        "*Rating checkboxes* \u2014 Check one or more to filter the recipe dropdown by rating. Also controls which pool random picks from.",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // Rating & Voting
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "Rating and Voting", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "Every output posted to #img-junkyard has \ud83d\udc4d and \ud83d\udc4e buttons in its thread.",
        "Votes are tracked per recipe \u2014 they affect the *Rating* checkboxes and weighted random selection.",
        "Click again to toggle your vote off. Change your vote any time.",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // Starring Posts
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "\u2b50 Starring Posts", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "The \u2b50 *Star* button in threads marks an output for the *Hall of Fame*.",
        "Stars are per-post (not per-recipe) \u2014 star the specific outputs you love.",
        "View all starred outputs via `/sparagmos best` or the \ud83c\udfc6 button in the modal.",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // Pinning Recipes
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "\ud83d\udccc Pinning Recipes", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "The \ud83d\udccc *Pin Recipe* button saves a recipe to your personal collection.",
        "View your pinned recipes via the \ud83d\udccc button in the modal \u2014 run them directly from there.",
        "Pin/unpin any time; it's a toggle.",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // How It Works
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "How It Works", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        "1. Your command triggers a GitHub Actions pipeline (~2\u20135 min)",
        "2. Source images are pulled from #image-gen (or your URLs)",
        "3. The recipe's effect chain runs: glitch, blend, sort, mask, corrupt, etc.",
        "4. The result is posted to #img-junkyard with source attribution in a thread",
      ].join("\n"),
    },
  });

  blocks.push({ type: "divider" });

  // Tips
  blocks.push({
    type: "header",
    text: { type: "plain_text", text: "Tips", emoji: true },
  });
  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: [
        `\u2022 ${RECIPES.length} recipes available, each requiring ${rangeStr} input images`,
        "\u2022 Recipe names are kebab-case (e.g. `mosaic-dissolution`, `double-exposure`)",
        "\u2022 Misspell a name? You'll get suggestions",
        "\u2022 To get a Slack image permalink: right-click an image \u2192 Copy link",
        "\u2022 More inputs usually means more chaos",
      ].join("\n"),
    },
  });

  return {
    type: "modal",
    callback_id: "sparagmos_help",
    title: { type: "plain_text", text: "Help" },
    close: { type: "plain_text", text: "Back" },
    blocks,
  };
}

/** Build the Status modal showing recent workflow runs. */
export function buildStatusView(runs: WorkflowRun[]): object {
  const blocks: object[] = runs.length > 0
    ? buildStatusBlocks(runs)
    : [{
        type: "section",
        text: { type: "mrkdwn", text: "No recent runs found." },
      }];

  return {
    type: "modal",
    callback_id: "sparagmos_status",
    title: { type: "plain_text", text: "Status" },
    close: { type: "plain_text", text: "Back" },
    blocks,
  };
}

// ---------------------------------------------------------------------------
// Main modal view builder
// ---------------------------------------------------------------------------

/** Build the Slack modal view object for `views.open`. */
export function buildModalView(
  channelId: string = "",
  ratings: Record<string, RatingData> = {},
  ratingFilters: string[] = [],
): object {
  const RANDOM_OPTION = { text: { type: "plain_text", text: "\ud83c\udfb2 Random" }, value: "random" };
  const filteredCount = countFilteredRecipes(ratings, ratingFilters);
  const countText = ratingFilters.length > 0
    ? `_${filteredCount} of ${RECIPES.length} recipes shown_`
    : `_${RECIPES.length} recipes available_`;

  // Build checkboxes with current selection preserved
  const ratingCheckboxOptions = [
    { text: { type: "plain_text", text: "Top rated (+3 or higher)" }, value: "top" },
    { text: { type: "plain_text", text: "Positive only" }, value: "positive" },
    { text: { type: "plain_text", text: "Unrated" }, value: "unrated" },
    { text: { type: "plain_text", text: "Underdogs (below 0)" }, value: "underdogs" },
  ];
  const ratingCheckboxElement: Record<string, unknown> = {
    type: "checkboxes",
    action_id: "rating_checkboxes",
    options: ratingCheckboxOptions,
  };
  if (ratingFilters.length > 0) {
    ratingCheckboxElement.initial_options = ratingCheckboxOptions.filter(
      (o) => ratingFilters.includes(o.value),
    );
  }

  return {
    type: "modal",
    callback_id: "sparagmos_run",
    private_metadata: channelId,
    title: { type: "plain_text", text: "Sparagmos" },
    submit: { type: "plain_text", text: "Destroy" },
    close: { type: "plain_text", text: "Cancel" },
    blocks: [
      // Description
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "Pick a recipe, tweak the filters, and hit *Destroy* to feed images from #image-gen through glitch/collage/corruption effects. Results land in #img-junkyard in ~2\u20135 min.",
        },
      },
      { type: "divider" },
      // ── Recipe section ──
      {
        type: "section",
        text: { type: "mrkdwn", text: "*:bar_chart: Recipe*" },
      },
      // Rating checkboxes (dispatch_action triggers views.update on toggle)
      {
        type: "actions",
        block_id: "rating_block",
        elements: [ratingCheckboxElement],
      },
      // Recipe select (static with built-in Slack typeahead filtering)
      {
        type: "input",
        block_id: "recipe_block",
        optional: true,
        label: { type: "plain_text", text: "Recipe" },
        element: {
          type: "static_select",
          action_id: "recipe_select",
          initial_option: RANDOM_OPTION,
          placeholder: {
            type: "plain_text",
            text: "Search recipes\u2026",
          },
          option_groups: buildRecipeOptionGroups(ratings, ratingFilters),
        },
      },
      // ── Images section ──
      {
        type: "section",
        text: { type: "mrkdwn", text: "*:frame_with_picture: Images*" },
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
      // ── Filters section ──
      {
        type: "section",
        text: { type: "mrkdwn", text: "*:mag: Filters*" },
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
            { text: { type: "plain_text", text: "Any time" }, value: "any" },
            { text: { type: "plain_text", text: "Last 24 hours" }, value: "24h" },
            { text: { type: "plain_text", text: "Last 7 days" }, value: "7d" },
            { text: { type: "plain_text", text: "Last 30 days" }, value: "30d" },
            { text: { type: "plain_text", text: "1-3 months ago" }, value: "1-3mo" },
            { text: { type: "plain_text", text: "3-6 months ago" }, value: "3-6mo" },
            { text: { type: "plain_text", text: "6-12 months ago" }, value: "6-12mo" },
            { text: { type: "plain_text", text: "Over 1 year ago" }, value: "1y+" },
            { text: { type: "plain_text", text: "Over 2 years ago" }, value: "2y+" },
            { text: { type: "plain_text", text: "The deep cut (oldest 50)" }, value: "oldest50" },
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
          placeholder: { type: "plain_text", text: "Prefer fresh for recipe" },
          options: [
            { text: { type: "plain_text", text: "No preference" }, value: "none" },
            { text: { type: "plain_text", text: "Prefer fresh for recipe" }, value: "prefer_fresh_recipe" },
            { text: { type: "plain_text", text: "Only fresh for recipe" }, value: "only_fresh_recipe" },
            { text: { type: "plain_text", text: "Only used with recipe (remix)" }, value: "only_used_recipe" },
            { text: { type: "plain_text", text: "Prefer untouched" }, value: "prefer_untouched" },
            { text: { type: "plain_text", text: "Only untouched" }, value: "only_untouched" },
            { text: { type: "plain_text", text: "Only veterans (3+ recipes)" }, value: "only_veterans" },
          ],
        },
      },
      // ── Tools section ──
      { type: "divider" },
      {
        type: "section",
        text: { type: "mrkdwn", text: "*:toolbox: Tools*" },
      },
      {
        type: "context",
        elements: [{ type: "mrkdwn", text: countText }],
      },
      // Footer actions
      {
        type: "actions",
        block_id: "modal_footer_actions",
        elements: [
          {
            type: "button",
            text: { type: "plain_text", text: "\ud83c\udfc6 Best Mucks", emoji: true },
            action_id: "modal_open_best",
          },
          {
            type: "button",
            text: { type: "plain_text", text: "\ud83d\udccc My Pinned Recipes", emoji: true },
            action_id: "modal_open_pinned",
          },
          {
            type: "button",
            text: { type: "plain_text", text: "\ud83d\udce1 Status", emoji: true },
            action_id: "modal_open_status",
          },
          {
            type: "button",
            text: { type: "plain_text", text: "\u2753 Help", emoji: true },
            action_id: "modal_open_help",
          },
        ],
      },
    ],
  };
}
