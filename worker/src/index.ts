import {
  isValidRecipe,
  formatRecipeList,
  suggestRecipes,
  getRecipe,
  RECIPES,
} from "./recipes";

/** Worker environment bindings (secrets set via wrangler). */
export interface Env {
  SLACK_SIGNING_SECRET: string;
  GITHUB_TOKEN: string;
}

/** Parsed result from a slash command text field. */
export interface ParsedCommand {
  command: string;
  urls: string[];
}

// ---------------------------------------------------------------------------
// Slash command parsing
// ---------------------------------------------------------------------------

/**
 * Parse a Slack slash command text field into a command and optional image URLs.
 *
 * The first non-URL token is the command (lowercased). All tokens matching
 * http(s):// are collected as image URLs with original case preserved.
 */
export function parseSlashCommand(text: string): ParsedCommand {
  const parts = text.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return { command: "", urls: [] };
  }

  const first = parts[0];
  const isUrl = /^https?:\/\//i;

  // If the first token is a URL, there's no command — treat as random with URLs
  if (isUrl.test(first)) {
    return {
      command: "",
      urls: parts.filter((s) => isUrl.test(s)),
    };
  }

  return {
    command: first.toLowerCase(),
    urls: parts.slice(1).filter((s) => isUrl.test(s)),
  };
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
 * Dispatch the collage-bot gif-speed workflow via the REST API.
 * Returns true on success, false on failure.
 */
async function dispatchGifSpeedWorkflow(
  env: Env,
  frameDuration: string,
  messageLink: string,
): Promise<boolean> {
  const response = await fetch(
    "https://api.github.com/repos/A-U-Supply/collage-bot/actions/workflows/run-gif-speed.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "sparagmos-slash-command/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        ref: "master",
        inputs: { frame_duration: frameDuration, message_link: messageLink },
      }),
    },
  );

  if (response.status !== 204) {
    const text = await response.text();
    console.error(`GitHub dispatch failed: ${response.status} ${text}`);
  }
  return response.status === 204;
}

/**
 * Dispatch the sparagmos GitHub Actions workflow via the REST API.
 * Returns true on success, false on failure.
 */
async function dispatchWorkflow(
  env: Env,
  recipe: string,
  images: string[] = [],
): Promise<boolean> {
  const inputs: Record<string, string> = { recipe };
  if (images.length > 0) {
    inputs.images = images.join(",");
  }

  const response = await fetch(
    "https://api.github.com/repos/A-U-Supply/sparagmos/actions/workflows/sparagmos.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "sparagmos-slash-command/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main", inputs }),
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
// Status
// ---------------------------------------------------------------------------

interface WorkflowRun {
  status: string;
  conclusion: string | null;
  created_at: string;
  updated_at: string;
  html_url: string;
  run_started_at: string;
  event: string;
}

/** Format a duration in seconds to a human-readable string. */
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

/** Format a single workflow run for Slack display. */
function formatRun(run: WorkflowRun): string {
  const statusEmoji =
    run.status === "completed"
      ? run.conclusion === "success"
        ? ":white_check_mark:"
        : ":x:"
      : run.status === "in_progress"
        ? ":hourglass_flowing_sand:"
        : ":clock1:";

  const label =
    run.status === "completed"
      ? run.conclusion === "success"
        ? "success"
        : (run.conclusion ?? "failed")
      : run.status;

  const started = new Date(run.run_started_at || run.created_at);
  const updated = new Date(run.updated_at);
  const durationSec = Math.round((updated.getTime() - started.getTime()) / 1000);
  const duration =
    run.status === "completed" ? ` in ${formatDuration(durationSec)}` : "";

  const timeAgo = Math.round((Date.now() - started.getTime()) / 60000);
  const when = timeAgo < 1 ? "just now" : `${timeAgo}m ago`;

  const trigger = run.event === "schedule" ? "scheduled" : "manual";

  return `${statusEmoji} *${label}* (${trigger}, ${when}${duration}) -- <${run.html_url}|logs>`;
}

/**
 * Fetch recent sparagmos workflow runs from the GitHub Actions API.
 * Returns a formatted Slack message.
 */
export async function fetchWorkflowStatus(env: Env): Promise<string> {
  const response = await fetch(
    "https://api.github.com/repos/A-U-Supply/sparagmos/actions/workflows/sparagmos.yml/runs?per_page=3",
    {
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "sparagmos-slash-command/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    },
  );

  if (!response.ok) {
    return ":warning: Failed to fetch workflow status from GitHub.";
  }

  const data = (await response.json()) as { workflow_runs: WorkflowRun[] };
  const runs = data.workflow_runs;

  if (runs.length === 0) {
    return "No recent runs found.";
  }

  const lines = ["*Recent sparagmos runs:*", ""];
  for (const run of runs) {
    lines.push(formatRun(run));
  }

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Command routing
// ---------------------------------------------------------------------------

/** Handle a /gif-speed slash command. */
async function handleGifSpeedCommand(
  body: string,
  env: Env,
): Promise<Response> {
  const params = new URLSearchParams(body);
  const parts = (params.get("text") ?? "").trim().split(/\s+/).filter(Boolean);

  // Expect: /gif-speed <frame_duration_ms> <message_link>
  const frameDuration = parts[0];
  const messageLink = parts[1];

  if (!frameDuration || !/^\d+$/.test(frameDuration)) {
    return slackResponse(
      ":x: Usage: `/gif-speed <frame_duration_ms> <message_link>`\n" +
        "Example: `/gif-speed 200 https://a-u-supply.slack.com/archives/C.../p...`",
    );
  }

  if (!messageLink || !/^https?:\/\//i.test(messageLink)) {
    return slackResponse(
      ":x: A Slack message link is required.\n" +
        "Usage: `/gif-speed <frame_duration_ms> <message_link>`",
    );
  }

  const dispatched = await dispatchGifSpeedWorkflow(
    env,
    frameDuration,
    messageLink,
  );
  if (dispatched) {
    return slackResponse(
      `:scissors: Re-rendering GIF at *${frameDuration}ms/frame*... result in #img-junkyard shortly.`,
    );
  }
  return slackResponse(
    ":warning: Failed to dispatch workflow. Check the GitHub token configuration.",
  );
}

/** Handle the parsed slash command body. */
async function handleSlashCommand(body: string, env: Env): Promise<Response> {
  const params = new URLSearchParams(body);
  const slashCommand = (params.get("command") ?? "").toLowerCase();

  // Route /gif-speed to its own handler
  if (slashCommand === "/gif-speed") {
    return handleGifSpeedCommand(body, env);
  }

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

    // Only accept POST to /slack/commands
    if (request.method !== "POST" || url.pathname !== "/slack/commands") {
      return new Response("Not Found", { status: 404 });
    }

    const body = await request.text();

    // Verify Slack signature
    const valid = await verifySlackSignature(
      request,
      body,
      env.SLACK_SIGNING_SECRET,
    );
    if (!valid) {
      return new Response("Invalid signature", { status: 401 });
    }

    return handleSlashCommand(body, env);
  },
};
