import type { Env } from "./types";

/**
 * Handle Slack interactive payloads (e.g. modal submissions, button clicks).
 *
 * This is a placeholder that will be filled in when modal support is added.
 */
export async function handleInteraction(
  _request: Request,
  _env: Env,
): Promise<Response> {
  return new Response("", { status: 200 });
}
