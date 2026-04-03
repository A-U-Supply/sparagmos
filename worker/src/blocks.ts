import type { WorkflowRun } from "./types";
import { formatDuration } from "./github";

// ---------------------------------------------------------------------------
// Block Kit builders for rich Slack status messages
// ---------------------------------------------------------------------------

/**
 * Build Block Kit blocks for displaying recent workflow run status.
 *
 * Shows a header, per-run sections with status/timing/action buttons,
 * and a footer with summary stats.
 */
export function buildStatusBlocks(runs: WorkflowRun[]): object[] {
  const blocks: object[] = [];

  // Header
  blocks.push({
    type: "header",
    text: {
      type: "plain_text",
      text: "Recent Runs",
      emoji: true,
    },
  });

  blocks.push({
    type: "context",
    elements: [
      {
        type: "mrkdwn",
        text: `Showing the last ${runs.length} workflow run${runs.length === 1 ? "" : "s"}`,
      },
    ],
  });

  blocks.push({ type: "divider" });

  // Per-run sections
  for (const run of runs) {
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
    const durationSec = Math.round(
      (updated.getTime() - started.getTime()) / 1000,
    );
    const duration =
      run.status === "completed" ? ` in ${formatDuration(durationSec)}` : "";

    const timeAgo = Math.round((Date.now() - started.getTime()) / 60000);
    const when = timeAgo < 1 ? "just now" : `${timeAgo}m ago`;

    const trigger = run.event === "schedule" ? "scheduled" : "manual";

    const buttonText =
      run.conclusion === "failure" ? "Retry" : "Run again";
    const actionId =
      run.conclusion === "failure" ? "retry" : "rerun";

    blocks.push({
      type: "section",
      text: {
        type: "mrkdwn",
        text: `${statusEmoji} *${label}* (${trigger}, ${when}${duration}) -- <${run.html_url}|logs>`,
      },
      accessory: {
        type: "button",
        text: { type: "plain_text", text: buttonText },
        action_id: actionId,
        value: "",
      },
    });
  }

  // Footer with summary stats
  const passed = runs.filter(
    (r) => r.status === "completed" && r.conclusion === "success",
  ).length;
  const failed = runs.filter(
    (r) => r.status === "completed" && r.conclusion !== "success",
  ).length;
  const running = runs.filter((r) => r.status !== "completed").length;

  const parts: string[] = [];
  if (passed > 0) parts.push(`:white_check_mark: ${passed} passed`);
  if (failed > 0) parts.push(`:x: ${failed} failed`);
  if (running > 0) parts.push(`:hourglass_flowing_sand: ${running} running`);

  if (parts.length > 0) {
    blocks.push({ type: "divider" });
    blocks.push({
      type: "context",
      elements: [
        {
          type: "mrkdwn",
          text: parts.join("  |  "),
        },
      ],
    });
  }

  return blocks;
}
