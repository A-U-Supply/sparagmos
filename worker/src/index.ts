import { isValidRecipe, formatRecipeList, suggestRecipes, RECIPES } from "./recipes";

/** Worker environment bindings (secrets set via wrangler). */
export interface Env {
  SLACK_SIGNING_SECRET: string;
  GITHUB_TOKEN: string;
}

// ---------------------------------------------------------------------------
// Slack signature verification
// ---------------------------------------------------------------------------

/**
 * Verify the Slack request signature using HMAC-SHA256.
 *
 * Checks the `x-slack-signature` and `x-slack-request-timestamp` headers
 * against the raw request body. Rejects requests older than 5 minutes to
 * prevent replay attacks. Uses constant-time comparison via the Web Crypto
 * subtle.timingSafeEqual-equivalent approach.
 */
async function verifySlackSignature(
  request: Request,
  body: string,
  signingSecret: string,
): Promise<boolean> {
  const timestamp = request.headers.get("x-slack-request-timestamp");
  const slackSignature = request.headers.get("x-slack-signature");

  if (!timestamp || !slackSignature) {
    return false;
  }

  // Reject requests older than 5 minutes
  const now = Math.floor(Date.now() / 1000);
  const ts = Number(timestamp);
  if (Number.isNaN(ts) || Math.abs(now - ts) > 300) {
    return false;
  }

  const sigBasestring = `v0:${timestamp}:${body}`;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );

  const signatureBytes = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(sigBasestring),
  );

  const expectedSignature =
    "v0=" +
    [...new Uint8Array(signatureBytes)]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

  // Constant-time comparison: compare every character regardless of mismatch
  if (expectedSignature.length !== slackSignature.length) {
    return false;
  }
  let mismatch = 0;
  for (let i = 0; i < expectedSignature.length; i++) {
    mismatch |= expectedSignature.charCodeAt(i) ^ slackSignature.charCodeAt(i);
  }
  return mismatch === 0;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a JSON response that Slack understands. */
function slackResponse(text: string, ephemeral = true): Response {
  return new Response(
    JSON.stringify({
      response_type: ephemeral ? "ephemeral" : "in_channel",
      text,
    }),
    {
      headers: { "Content-Type": "application/json" },
    },
  );
}

/**
 * Dispatch the sparagmos GitHub Actions workflow via the REST API.
 * Returns true on success, false on failure.
 */
async function dispatchWorkflow(env: Env, recipe: string): Promise<boolean> {
  const response = await fetch(
    "https://api.github.com/repos/au-supply/sparagmos/actions/workflows/sparagmos.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "sparagmos-slash-command/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: { recipe },
      }),
    },
  );

  // GitHub returns 204 No Content on success
  if (response.status !== 204) {
    const text = await response.text();
    console.error(`GitHub dispatch failed: ${response.status} ${text}`);
  }
  return response.status === 204;
}

// ---------------------------------------------------------------------------
// Command routing
// ---------------------------------------------------------------------------

const HELP_TEXT = [
  "*Sparagmos* — image collage bot :art:",
  "",
  "Usage:",
  "  `/sparagmos` — run a random recipe",
  "  `/sparagmos <recipe>` — run a specific recipe",
  "  `/sparagmos list` — show all available recipes",
  "  `/sparagmos help` — show this message",
  "",
  `${RECIPES.length} recipes available. Results appear in #img-junkyard (~2-5 min).`,
].join("\n");

/** Handle the parsed slash command body. */
async function handleSlashCommand(body: string, env: Env): Promise<Response> {
  const params = new URLSearchParams(body);
  const rawText = (params.get("text") ?? "").trim().toLowerCase();

  // Help
  if (rawText === "help") {
    return slackResponse(HELP_TEXT);
  }

  // List all recipes
  if (rawText === "list") {
    return slackResponse(formatRecipeList());
  }

  // Random recipe (no args or explicit "random")
  // Empty recipe input tells the GitHub workflow to pick randomly
  if (!rawText || rawText === "random") {
    const dispatched = await dispatchWorkflow(env, "");
    if (dispatched) {
      return slackResponse(
        ":game_die: Firing up a random recipe... results in #img-junkyard in ~2-5 min.",
      );
    }
    return slackResponse(
      ":warning: Failed to dispatch workflow. Check the GitHub token configuration.",
    );
  }

  // Specific recipe
  if (isValidRecipe(rawText)) {
    const dispatched = await dispatchWorkflow(env, rawText);
    if (dispatched) {
      return slackResponse(
        `:art: Firing up *${rawText}*... results in #img-junkyard in ~2-5 min.`,
      );
    }
    return slackResponse(
      ":warning: Failed to dispatch workflow. Check the GitHub token configuration.",
    );
  }

  // Invalid recipe — suggest similar ones
  const suggestions = suggestRecipes(rawText);
  let errorText = `:x: Unknown recipe \`${rawText}\`.`;
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

    // Only accept POST to /slack/commands
    if (request.method !== "POST" || url.pathname !== "/slack/commands") {
      return new Response("Not Found", { status: 404 });
    }

    const body = await request.text();

    // Verify Slack signature
    const valid = await verifySlackSignature(request, body, env.SLACK_SIGNING_SECRET);
    if (!valid) {
      return new Response("Invalid signature", { status: 401 });
    }

    return handleSlashCommand(body, env);
  },
};
