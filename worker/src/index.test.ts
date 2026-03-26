import { describe, it, expect } from "vitest";
import { isValidRecipe, formatRecipeList, suggestRecipes, RECIPES } from "./recipes";

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

  it("contains expected recipes in the output", () => {
    const list = formatRecipeList();
    expect(list).toContain("`double-exposure`");
    expect(list).toContain("`mosaic-dissolution`");
    expect(list).toContain("`acid-wash`");
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
  it("has 48 entries", () => {
    expect(RECIPES.length).toBe(48);
  });

  it("all slugs are lowercase kebab-case", () => {
    const kebabRegex = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
    for (const recipe of RECIPES) {
      expect(recipe.slug).toMatch(kebabRegex);
    }
  });

  it("all input counts are between 2 and 5", () => {
    for (const recipe of RECIPES) {
      expect(recipe.inputs).toBeGreaterThanOrEqual(2);
      expect(recipe.inputs).toBeLessThanOrEqual(5);
    }
  });

  it("slugs are unique", () => {
    const slugs = RECIPES.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});
