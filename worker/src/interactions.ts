import type { Env } from "./types";
import { vote, toggleStar, toggleFavorite, getRatings, getUserVotes, getFavorites } from "./kv";
import { dispatchWorkflow } from "./github";
import { buildTypeaheadOptions } from "./modal";

// ---------------------------------------------------------------------------
// Slack interaction payload types
// ---------------------------------------------------------------------------

interface SlackInteractionPayload {
  type: string;
  user: { id: string };
  /** Typed query text sent by block_suggestion payloads. */
  value?: string;
  actions?: Array<{
    action_id: string;
    value: string;
    block_id: string;
  }>;
  view?: {
    callback_id: string;
    state: { values: Record<string, Record<string, any>> };
    private_metadata: string;
  };
  trigger_id?: string;
  container?: { channel_id: string; message_ts: string; thread_ts?: string };
  channel?: { id: string };
  message?: {
    ts: string;
    blocks: any[];
  };
  /** Action ID for block_suggestion payloads. */
  action_id?: string;
}

/** Shape returned by getRatings from kv.ts */
interface RatingData {
  up: number;
  down: number;
  score: number;
  last_voted: string;
}

// ---------------------------------------------------------------------------
// Block builders
// ---------------------------------------------------------------------------

/** Build the recipe actions block with current vote counts. */
function buildVoteButtons(
  slug: string,
  ratings: RatingData,
  userVotes: { vote: number; starred: boolean; favorited: boolean },
): any {
  const upLabel = ratings.up > 0 ? `\ud83d\udc4d ${ratings.up}` : "\ud83d\udc4d";
  const downLabel = ratings.down > 0 ? `\ud83d\udc4e ${ratings.down}` : "\ud83d\udc4e";
  const favLabel = userVotes.favorited ? "\u2605 Saved" : "\u2606 Save Recipe";

  return {
    type: "actions",
    block_id: `recipe_actions:${slug}`,
    elements: [
      {
        type: "button",
        text: { type: "plain_text", text: upLabel, emoji: true },
        action_id: "upvote",
        value: slug,
      },
      {
        type: "button",
        text: { type: "plain_text", text: downLabel, emoji: true },
        action_id: "downvote",
        value: slug,
      },
      {
        type: "button",
        text: { type: "plain_text", text: favLabel, emoji: true },
        action_id: "favorite",
        value: slug,
      },
    ],
  };
}

/** Build the post actions block with current star state. */
function buildStarButton(
  postedTs: string,
  slug: string,
  starred: boolean,
): any {
  const label = starred ? "\u2b50 Starred" : "\u2b50 Star";
  return {
    type: "actions",
    block_id: `post_actions:${postedTs}`,
    elements: [
      {
        type: "button",
        text: { type: "plain_text", text: label, emoji: true },
        action_id: "star_post",
        value: `${slug}:${postedTs}`,
      },
    ],
  };
}

/**
 * Rebuild message blocks after a state change (vote, star, favorite).
 *
 * Preserves non-action blocks (section, divider) and rebuilds the
 * action blocks with updated counts/labels.
 */
function rebuildBlocks(
  existingBlocks: any[],
  slug: string,
  postedTs: string,
  ratings: RatingData,
  userVotes: { vote: number; starred: boolean; favorited: boolean },
): any[] {
  return existingBlocks.map((block: any) => {
    if (block.block_id?.startsWith("post_actions:")) {
      return buildStarButton(postedTs, slug, userVotes.starred);
    }
    if (block.block_id?.startsWith("recipe_actions:")) {
      return buildVoteButtons(slug, ratings, userVotes);
    }
    return block;
  });
}

// ---------------------------------------------------------------------------
// Slack API helpers
// ---------------------------------------------------------------------------

/** Update an existing Slack message with new blocks. */
async function updateMessage(
  env: Env,
  channel: string,
  ts: string,
  blocks: any[],
): Promise<void> {
  const resp = await fetch("https://slack.com/api/chat.update", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${env.SLACK_BOT_TOKEN}`,
    },
    body: JSON.stringify({
      channel,
      ts,
      blocks,
      text: "Updated",
    }),
  });
  if (!resp.ok) {
    console.error(`chat.update failed: ${resp.status}`);
  }
}

// ---------------------------------------------------------------------------
// Action handlers
// ---------------------------------------------------------------------------

/** Gather user state for rebuilding message blocks after an action. */
async function gatherUserState(
  env: Env,
  userId: string,
  slug: string,
  postedTs: string,
): Promise<{ rating: RatingData; userVotes: { vote: number; starred: boolean; favorited: boolean } }> {
  const [allRatings, allUserVotes, favorites] = await Promise.all([
    getRatings(env.RATINGS),
    getUserVotes(env.RATINGS, userId),
    getFavorites(env.RATINGS, userId),
  ]);
  const rating: RatingData = allRatings[slug] ?? { up: 0, down: 0, score: 0, last_voted: "" };
  const starVotersRaw = await env.RATINGS.get(`star_voters:${postedTs}`);
  const starVoters: string[] = starVotersRaw ? JSON.parse(starVotersRaw) : [];
  return {
    rating,
    userVotes: {
      vote: allUserVotes[slug] ?? 0,
      starred: starVoters.includes(userId),
      favorited: favorites.includes(slug),
    },
  };
}

/** Handle an upvote or downvote action. */
async function handleVote(
  env: Env,
  payload: SlackInteractionPayload,
  slug: string,
  direction: 1 | -1,
): Promise<void> {
  await vote(env.RATINGS, slug, payload.user.id, direction);

  const channel = payload.channel?.id || payload.container?.channel_id;
  const ts = payload.message?.ts || payload.container?.message_ts;
  if (!channel || !ts || !payload.message?.blocks) return;

  const postBlock = payload.message.blocks.find((b: any) =>
    b.block_id?.startsWith("post_actions:"),
  );
  const postedTs = postBlock?.block_id?.split(":").slice(1).join(":") || ts;

  const { rating, userVotes } = await gatherUserState(env, payload.user.id, slug, postedTs);
  const updatedBlocks = rebuildBlocks(payload.message.blocks, slug, postedTs, rating, userVotes);
  await updateMessage(env, channel, ts, updatedBlocks);
}

/** Handle a star toggle action. */
async function handleStar(
  env: Env,
  payload: SlackInteractionPayload,
  value: string,
): Promise<void> {
  // value format: "recipe-slug:posted_ts"
  const colonIdx = value.indexOf(":");
  const slug = colonIdx >= 0 ? value.substring(0, colonIdx) : value;
  const postedTs = colonIdx >= 0 ? value.substring(colonIdx + 1) : "";
  const channel = payload.channel?.id || payload.container?.channel_id || "";

  await toggleStar(env.RATINGS, postedTs, slug, payload.user.id, channel);

  const ts = payload.message?.ts || payload.container?.message_ts;
  if (!channel || !ts || !payload.message?.blocks) return;

  const { rating, userVotes } = await gatherUserState(env, payload.user.id, slug, postedTs);
  const updatedBlocks = rebuildBlocks(payload.message.blocks, slug, postedTs, rating, userVotes);
  await updateMessage(env, channel, ts, updatedBlocks);
}

/** Handle a favorite toggle action. */
async function handleFavorite(
  env: Env,
  payload: SlackInteractionPayload,
  slug: string,
): Promise<void> {
  await toggleFavorite(env.RATINGS, payload.user.id, slug);

  const channel = payload.channel?.id || payload.container?.channel_id;
  const ts = payload.message?.ts || payload.container?.message_ts;
  if (!channel || !ts || !payload.message?.blocks) return;

  const postBlock = payload.message.blocks.find((b: any) =>
    b.block_id?.startsWith("post_actions:"),
  );
  const postedTs = postBlock?.block_id?.split(":").slice(1).join(":") || ts;

  const { rating, userVotes } = await gatherUserState(env, payload.user.id, slug, postedTs);
  const updatedBlocks = rebuildBlocks(payload.message.blocks, slug, postedTs, rating, userVotes);
  await updateMessage(env, channel, ts, updatedBlocks);
}

/** Handle a rerun/retry action. */
async function handleRerun(
  env: Env,
  recipe: string,
): Promise<void> {
  await dispatchWorkflow(env, recipe);
  // Future: post ephemeral message confirming dispatch
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

/**
 * Handle Slack interactive payloads (button clicks, modal submissions, etc.).
 *
 * Accepts the raw request body string (already read for signature
 * verification) and routes by payload type and action ID.
 */
export async function handleInteraction(
  body: string,
  env: Env,
): Promise<Response> {
  const params = new URLSearchParams(body);
  const payloadStr = params.get("payload");
  if (!payloadStr) {
    return new Response("Missing payload", { status: 400 });
  }

  let payload: SlackInteractionPayload;
  try {
    payload = JSON.parse(payloadStr);
  } catch {
    return new Response("Invalid JSON payload", { status: 400 });
  }

  // Route by payload type
  switch (payload.type) {
    case "block_actions": {
      const actions = payload.actions || [];
      for (const action of actions) {
        switch (action.action_id) {
          case "upvote":
            await handleVote(env, payload, action.value, 1);
            break;
          case "downvote":
            await handleVote(env, payload, action.value, -1);
            break;
          case "star_post":
            await handleStar(env, payload, action.value);
            break;
          case "favorite":
            await handleFavorite(env, payload, action.value);
            break;
          case "rerun":
          case "retry":
            await handleRerun(env, action.value);
            break;
          default:
            console.warn(`Unknown action_id: ${action.action_id}`);
        }
      }
      // Slack expects 200 OK for block_actions acknowledgement
      return new Response("", { status: 200 });
    }

    case "view_submission": {
      if (payload.view?.callback_id === "sparagmos_run") {
        const vals = payload.view.state.values;
        const recipe =
          vals.recipe_block?.recipe_select?.selected_option?.value ?? null;
        const rawUrls: string = vals.urls_block?.image_urls?.value ?? "";
        const urls = rawUrls
          .split("\n")
          .map((u: string) => u.trim())
          .filter(Boolean);
        const poster =
          vals.poster_block?.poster_filter?.selected_option?.value ?? "anyone";
        const age =
          vals.age_block?.age_filter?.selected_option?.value ?? "any";
        const freshness =
          vals.freshness_block?.freshness_filter?.selected_option?.value ??
          "none";

        // Dispatch in the background — modal must respond quickly
        const resolvedRecipe =
          recipe && recipe !== "random" ? recipe : "";
        dispatchWorkflow(env, resolvedRecipe, urls, {
          poster: poster !== "anyone" ? poster : undefined,
          age: age !== "any" ? age : undefined,
          freshness: freshness !== "none" ? freshness : undefined,
        }).catch(console.error);
      }
      return new Response(JSON.stringify({ response_action: "clear" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    case "block_suggestion": {
      if (payload.action_id === "recipe_select") {
        const query = payload.value ?? "";
        const result = await buildTypeaheadOptions(
          query,
          payload.user.id,
          env.RATINGS,
        );
        return new Response(JSON.stringify(result), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ options: [] }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    default:
      return new Response("", { status: 200 });
  }
}
