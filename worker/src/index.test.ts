import { describe, it, expect } from "vitest";
import {
  isValidRecipe,
  formatRecipeList,
  suggestRecipes,
  getRecipe,
  RECIPES,
} from "./recipes";
import { parseSlashCommand } from "./index";

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
