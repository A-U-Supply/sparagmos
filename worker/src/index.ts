import {
  isValidRecipe,
  formatRecipeList,
  suggestRecipes,
  getRecipe,
  RECIPES,
} from "./recipes";
import type { Env } from "./types";
import { verifySlackSignature, parseSlashCommand, slackResponse } from "./slack";
import { dispatchWorkflow, fetchWorkflowStatus } from "./github";
import { handleInteraction } from "./interactions";
import { getRatings, getStars } from "./kv";

// Re-export types and functions that tests (and consumers) depend on
export type { Env, ParsedCommand } from "./types";
export { parseSlashCommand } from "./slack";
export { fetchWorkflowStatus } from "./github";

// ---------------------------------------------------------------------------
// Help text
// ---------------------------------------------------------------------------

/** Build the comprehensive help text, with dynamic recipe count and input range. */
function buildHelpText(): string {
  const inputCounts = [...new Set(RECIPES.map((r) => r.inputs))].sort(
    (a, b) => a - b,
  );
  const rangeStr =
    inputCounts.length > 1
      ? `${inputCounts[0]}-${inputCounts[inputCounts.length - 1]}`
      : `${inputCounts[0]}`;

  return [
    "*Sparagmos* -- image collage bot :art:",
    "",
    "*Basic usage:*",
    "  `/sparagmos` -- run a random recipe on random images from #image-gen",
    "  `/sparagmos <recipe>` -- run a specific recipe with random images",
    "  `/sparagmos list` -- show all available recipes grouped by input count",
    "  `/sparagmos status` -- check recent run status",
    "  `/sparagmos help` -- show this message",
    "",
    "*Image URL support:*",
    "  `/sparagmos <recipe> <url1> [url2] [url3...]`",
    "  Pass specific image URLs instead of random selection from #image-gen.",
    "  - Works with Slack image permalinks and any public image URL",
    "  - If a recipe needs more images than you provide, the rest are picked randomly from #image-gen",
    "  - To get a Slack image permalink: right-click an image in #image-gen \u2192 *Copy link*",
    "",
    "*Examples:*",
    "  `/sparagmos` -- random recipe, random images",
    "  `/sparagmos double-exposure` -- specific recipe, random images",
    "  `/sparagmos mosaic-dissolution https://files.slack.com/.../img1.png` -- 1 specific + 4 random",
    "  `/sparagmos double-exposure https://url1.png https://url2.png` -- 2 specific images, no random fill",
    "",
    `*Recipes:*`,
    `  ${RECIPES.length} recipes available, each requiring ${rangeStr} input images.`,
    "  Use `/sparagmos list` to see them all, grouped by input count.",
    "",
    "*How it works:*",
    "  1. Your command triggers a processing pipeline (~2-5 minutes)",
    "  2. The recipe's effect chain runs on the input images (glitch, blend, sort, mask, corrupt, etc.)",
    "  3. The result is posted to #img-junkyard",
    "",
    "*Tips:*",
    "  - Recipe names are kebab-case (e.g., `double-exposure`, `mosaic-dissolution`)",
    "  - Misspell a recipe name? You'll get suggestions",
    "  - Slack image permalinks work automatically -- no special auth needed",
    "  - More inputs usually means more chaos",
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Command routing
// ---------------------------------------------------------------------------

/** Handle the parsed slash command body. */
async function handleSlashCommand(body: string, env: Env): Promise<Response> {
  const params = new URLSearchParams(body);
  const rawText = (params.get("text") ?? "").trim();
  const { command, urls } = parseSlashCommand(rawText);

  // Help
  if (command === "help") {
    return slackResponse(buildHelpText());
  }

  // List all recipes
  if (command === "list") {
    return slackResponse(formatRecipeList());
  }

  // Status
  if (command === "status") {
    const status = await fetchWorkflowStatus(env);
    return slackResponse(status);
  }

  // Random recipe (no args or explicit "random")
  // Empty recipe input tells the GitHub workflow to pick randomly
  if (!command || command === "random") {
    const dispatched = await dispatchWorkflow(env, "", urls);
    if (dispatched) {
      const urlNote =
        urls.length > 0
          ? ` with ${urls.length} provided image(s)`
          : "";
      return slackResponse(
        `:game_die: Firing up a random recipe${urlNote}... results in #img-junkyard in ~2-5 min.`,
      );
    }
    return slackResponse(
      ":warning: Failed to dispatch workflow. Check the GitHub token configuration.",
    );
  }

  // Specific recipe
  if (isValidRecipe(command)) {
    // Validate URL count against recipe input count
    const recipe = getRecipe(command)!;
    if (urls.length > recipe.inputs) {
      return slackResponse(
        `:x: Recipe \`${command}\` accepts ${recipe.inputs} input(s), but you provided ${urls.length} URLs.`,
      );
    }

    const dispatched = await dispatchWorkflow(env, command, urls);
    if (dispatched) {
      const urlNote =
        urls.length > 0
          ? ` with ${urls.length} provided image(s)`
          : "";
      return slackResponse(
        `:art: Firing up *${command}*${urlNote}... results in #img-junkyard in ~2-5 min.`,
      );
    }
    return slackResponse(
      ":warning: Failed to dispatch workflow. Check the GitHub token configuration.",
    );
  }

  // Invalid recipe -- suggest similar ones
  const suggestions = suggestRecipes(command);
  let errorText = `:x: Unknown recipe \`${command}\`.`;
  if (suggestions.length > 0) {
    const suggestionList = suggestions.map((r) => `\`${r.slug}\``).join(", ");
    errorText += `\n\nDid you mean: ${suggestionList}?`;
  }
  errorText += "\n\nUse `/sparagmos list` to see all available recipes.";

  return slackResponse(errorText);
}

// ---------------------------------------------------------------------------
// Worker entry point
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // --- API routes backed by KV (GET — no body needed) ---
    if (request.method === "GET" && url.pathname === "/api/ratings") {
      const ratings = await getRatings(env.RATINGS);
      return new Response(JSON.stringify(ratings), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (request.method === "GET" && url.pathname === "/api/stars") {
      const stars = await getStars(env.RATINGS);
      return new Response(JSON.stringify(stars), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // --- POST routes: read body once for shared signature verification ---
    if (request.method === "POST") {
      const body = await request.text();

      // Verify Slack signature for all POST endpoints
      const valid = await verifySlackSignature(
        request,
        body,
        env.SLACK_SIGNING_SECRET,
      );
      if (!valid) {
        return new Response("Invalid signature", { status: 401 });
      }

      // Slack interaction payloads (modals, buttons, etc.)
      if (url.pathname === "/slack/interactions") {
        return handleInteraction(body, env);
      }

      // Slash command endpoint
      if (url.pathname === "/slack/commands") {
        return handleSlashCommand(body, env);
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};
