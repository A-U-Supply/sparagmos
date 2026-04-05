import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  isValidRecipe,
  formatRecipeList,
  suggestRecipes,
  getRecipe,
  RECIPES,
} from "./recipes";
import { parseSlashCommand, fetchWorkflowRuns, handleSlashCommand } from "./index";
import type { Env } from "./types";

// ---------------------------------------------------------------------------
// isValidRecipe
// ---------------------------------------------------------------------------

describe("isValidRecipe", () => {
  it("returns true for a known recipe", () => {
    expect(isValidRecipe("acid-wash")).toBe(true);
  });

  it("returns true for another known recipe", () => {
    expect(isValidRecipe("mosaic-dissolution")).toBe(true);
  });

  it("returns false for an unknown recipe", () => {
    expect(isValidRecipe("nonexistent-recipe")).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(isValidRecipe("")).toBe(false);
  });

  it("returns false for a partial slug", () => {
    expect(isValidRecipe("acid")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getRecipe
// ---------------------------------------------------------------------------

describe("getRecipe", () => {
  it("returns a recipe for a known slug", () => {
    const r = getRecipe("acid-wash");
    expect(r).toBeDefined();
    expect(r!.inputs).toBe(3);
    expect(r!.name).toBe("Acid Wash");
  });

  it("returns undefined for an unknown slug", () => {
    expect(getRecipe("nope")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// formatRecipeList
// ---------------------------------------------------------------------------

describe("formatRecipeList", () => {
  it("includes the total recipe count", () => {
    const list = formatRecipeList();
    expect(list).toContain(`${RECIPES.length} total`);
  });

  it("groups recipes by input count", () => {
    const list = formatRecipeList();
    expect(list).toContain("*2 inputs:*");
    expect(list).toContain("*3 inputs:*");
    expect(list).toContain("*4 inputs:*");
    expect(list).toContain("*5 inputs:*");
  });

  it("contains recipe slugs with names", () => {
    const list = formatRecipeList();
    expect(list).toContain("`double-exposure`");
    expect(list).toContain("`mosaic-dissolution`");
    expect(list).toContain("`acid-wash`");
  });

  it("shows human-readable names alongside slugs", () => {
    const list = formatRecipeList();
    expect(list).toContain("Double Exposure");
    expect(list).toContain("Acid Wash");
  });
});

// ---------------------------------------------------------------------------
// suggestRecipes
// ---------------------------------------------------------------------------

describe("suggestRecipes", () => {
  it("finds substring matches", () => {
    const results = suggestRecipes("mosaic");
    expect(results.length).toBeGreaterThan(0);
    expect(results.every((r) => r.slug.includes("mosaic"))).toBe(true);
  });

  it("returns empty array for no matches", () => {
    const results = suggestRecipes("zzzzzzzznotarecipe");
    expect(results).toEqual([]);
  });

  it("returns at most 5 results", () => {
    // "a" is common enough to appear in many slugs
    const results = suggestRecipes("a");
    expect(results.length).toBeLessThanOrEqual(5);
  });

  it("is case-insensitive", () => {
    const results = suggestRecipes("ACID");
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].slug).toBe("acid-wash");
  });
});

// ---------------------------------------------------------------------------
// RECIPES collection
// ---------------------------------------------------------------------------

describe("RECIPES", () => {
  it("has recipes (auto-generated from YAML)", () => {
    expect(RECIPES.length).toBeGreaterThanOrEqual(48);
  });

  it("all slugs are lowercase kebab-case", () => {
    const kebabRegex = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
    for (const recipe of RECIPES) {
      expect(recipe.slug).toMatch(kebabRegex);
    }
  });

  it("all input counts are between 1 and 5", () => {
    for (const recipe of RECIPES) {
      expect(recipe.inputs).toBeGreaterThanOrEqual(1);
      expect(recipe.inputs).toBeLessThanOrEqual(5);
    }
  });

  it("slugs are unique", () => {
    const slugs = RECIPES.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("all recipes have non-empty name and description", () => {
    for (const recipe of RECIPES) {
      expect(recipe.name.length).toBeGreaterThan(0);
      expect(recipe.description.length).toBeGreaterThan(0);
    }
  });
});

// ---------------------------------------------------------------------------
// parseSlashCommand
// ---------------------------------------------------------------------------

describe("parseSlashCommand", () => {
  it("parses empty text as random", () => {
    const result = parseSlashCommand("");
    expect(result.command).toBe("");
    expect(result.urls).toEqual([]);
  });

  it("parses a recipe name", () => {
    const result = parseSlashCommand("acid-wash");
    expect(result.command).toBe("acid-wash");
    expect(result.urls).toEqual([]);
  });

  it("parses help command", () => {
    const result = parseSlashCommand("help");
    expect(result.command).toBe("help");
  });

  it("parses list command", () => {
    const result = parseSlashCommand("list");
    expect(result.command).toBe("list");
  });

  it("parses status command", () => {
    const result = parseSlashCommand("status");
    expect(result.command).toBe("status");
  });

  it("parses recipe with image URLs", () => {
    const result = parseSlashCommand(
      "double-exposure https://files.slack.com/T123/img1.png https://example.com/photo.jpg"
    );
    expect(result.command).toBe("double-exposure");
    expect(result.urls).toEqual([
      "https://files.slack.com/T123/img1.png",
      "https://example.com/photo.jpg",
    ]);
  });

  it("preserves URL case", () => {
    const result = parseSlashCommand(
      "acid-wash https://Example.Com/MyPhoto.JPG"
    );
    expect(result.urls[0]).toBe("https://Example.Com/MyPhoto.JPG");
  });

  it("lowercases command but not URLs", () => {
    const result = parseSlashCommand(
      "ACID-WASH https://example.com/img.png"
    );
    expect(result.command).toBe("acid-wash");
    expect(result.urls[0]).toBe("https://example.com/img.png");
  });

  it("ignores non-URL tokens after command", () => {
    const result = parseSlashCommand("acid-wash notaurl also-not");
    expect(result.command).toBe("acid-wash");
    expect(result.urls).toEqual([]);
  });

  it("handles http URLs", () => {
    const result = parseSlashCommand("acid-wash http://example.com/img.png");
    expect(result.urls).toEqual(["http://example.com/img.png"]);
  });

  it("handles whitespace-heavy input", () => {
    const result = parseSlashCommand("  acid-wash   https://a.com/1.png   https://b.com/2.png  ");
    expect(result.command).toBe("acid-wash");
    expect(result.urls).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// handleSlashCommand — regression tests for invalid_command_response
// ---------------------------------------------------------------------------

/**
 * Slack rejects slash command responses that have response_type but no text
 * field, returning "invalid_command_response" to the user. These tests ensure
 * every command path returns either:
 *   - An empty body (silent ack, used when a modal is the response), OR
 *   - JSON with a `text` field
 *
 * This bug has been re-introduced multiple times by CI state commits
 * reverting fixes. These tests prevent that from ever shipping again.
 */
describe("handleSlashCommand — no invalid_command_response", () => {
  const mockKV = {
    get: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue({ keys: [] }),
    delete: vi.fn().mockResolvedValue(undefined),
    getWithMetadata: vi.fn().mockResolvedValue({ value: null, metadata: null }),
  } as unknown as KVNamespace;

  const mockEnv: Env = {
    SLACK_SIGNING_SECRET: "test-secret",
    GITHUB_TOKEN: "test-gh-token",
    SLACK_BOT_TOKEN: "test-slack-token",
    SLACK_WORKSPACE: "test-workspace",
    RATINGS: mockKV,
  };

  const mockCtx: ExecutionContext = {
    waitUntil: vi.fn(),
    passThroughOnException: vi.fn(),
  };

  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    // Mock all external HTTP calls (Slack API, GitHub API)
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === "string" && url.includes("views.open")) {
        return Promise.resolve(new Response(JSON.stringify({ ok: true })));
      }
      if (typeof url === "string" && url.includes("dispatches")) {
        return Promise.resolve(new Response("", { status: 204 }));
      }
      if (typeof url === "string" && url.includes("/runs")) {
        return Promise.resolve(
          new Response(JSON.stringify({ workflow_runs: [] })),
        );
      }
      if (typeof url === "string" && url.includes("billing")) {
        return Promise.resolve(
          new Response(JSON.stringify({
            usageItems: [{
              date: "2026-04-05",
              product: "actions",
              sku: "actions",
              quantity: 42,
              unitType: "Minutes",
              repositoryName: "sparagmos",
            }],
          })),
        );
      }
      return Promise.resolve(new Response("", { status: 200 }));
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  /** Build a URL-encoded slash command body like Slack sends. */
  function slashBody(text: string): string {
    const params = new URLSearchParams();
    params.set("text", text);
    params.set("trigger_id", "test-trigger-123");
    params.set("channel_id", "C_TEST");
    params.set("user_id", "U_TEST");
    return params.toString();
  }

  /**
   * Assert a Response is a valid Slack slash command response:
   * either empty body OR JSON with a `text` field.
   */
  async function assertValidSlackResponse(response: Response, label: string) {
    const body = await response.text();
    if (body === "") {
      // Empty 200 is always valid (silent ack)
      expect(response.status).toBe(200);
      return;
    }
    // If there's a body, it must be JSON with a `text` field
    const parsed = JSON.parse(body);
    expect(parsed, `${label}: response JSON must have a 'text' field`).toHaveProperty("text");
    expect(typeof parsed.text, `${label}: 'text' must be a string`).toBe("string");
    expect(parsed.text.length, `${label}: 'text' must not be empty`).toBeGreaterThan(0);
  }

  it("bare /sparagmos (opens modal) returns valid response", async () => {
    const response = await handleSlashCommand(slashBody(""), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos");
  });

  it("/sparagmos help (opens modal) returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("help"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos help");
  });

  it("/sparagmos best (opens modal) returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("best"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos best");
  });

  it("/sparagmos list returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("list"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos list");
  });

  it("/sparagmos status returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("status"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos status");
  });

  it("/sparagmos random returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("random"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos random");
  });

  it("/sparagmos <valid-recipe> returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("acid-wash"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos acid-wash");
  });

  it("/sparagmos <invalid-recipe> returns valid response", async () => {
    const response = await handleSlashCommand(slashBody("not-a-recipe"), mockEnv, mockCtx);
    await assertValidSlackResponse(response, "/sparagmos not-a-recipe");
  });
});
