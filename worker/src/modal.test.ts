import { describe, it, expect } from "vitest";
import {
  buildSlackPermalink,
  buildBestView,
  buildPinnedView,
  buildHelpView,
  buildModalView,
} from "./modal";
import type { StarData } from "./kv";
import { RECIPES } from "./recipes";

// ---------------------------------------------------------------------------
// buildSlackPermalink
// ---------------------------------------------------------------------------

describe("buildSlackPermalink", () => {
  it("constructs a correct permalink from components", () => {
    const link = buildSlackPermalink("au-supply", "C12345", "1711234567.123456");
    expect(link).toBe(
      "https://au-supply.slack.com/archives/C12345/p1711234567123456",
    );
  });

  it("handles timestamps without dots", () => {
    const link = buildSlackPermalink("au-supply", "C99", "1711234567");
    expect(link).toBe(
      "https://au-supply.slack.com/archives/C99/p1711234567",
    );
  });
});

// ---------------------------------------------------------------------------
// buildBestView
// ---------------------------------------------------------------------------

describe("buildBestView", () => {
  it("returns empty state when no stars", () => {
    const view = buildBestView([], "au-supply") as any;
    expect(view.type).toBe("modal");
    expect(view.callback_id).toBe("sparagmos_best");
    expect(view.submit).toBeUndefined();
    expect(view.close).toBeDefined();

    const sectionText = view.blocks
      .filter((b: any) => b.type === "section")
      .map((b: any) => b.text.text);
    expect(sectionText.some((t: string) => t.includes("No starred posts"))).toBe(true);
  });

  it("shows starred posts sorted by star_count descending", () => {
    const stars: StarData[] = [
      { posted_ts: "ts1", recipe: "acid-wash", star_count: 1, channel: "C1", starred_date: "2026-04-01" },
      { posted_ts: "ts2", recipe: "mosaic-dissolution", star_count: 5, channel: "C1", starred_date: "2026-04-02" },
      { posted_ts: "ts3", recipe: "double-exposure", star_count: 3, channel: "C1", starred_date: "2026-04-03" },
    ];
    const view = buildBestView(stars, "au-supply") as any;
    const sections = view.blocks.filter((b: any) => b.type === "section");

    // First section should be the highest-starred
    expect(sections[0].text.text).toContain("mosaic-dissolution");
    expect(sections[0].text.text).toContain("5");
    // Second should be 3 stars
    expect(sections[1].text.text).toContain("double-exposure");
    // Third should be 1 star
    expect(sections[2].text.text).toContain("acid-wash");
  });

  it("includes View button with permalink", () => {
    const stars: StarData[] = [
      { posted_ts: "1711234567.123456", recipe: "acid-wash", star_count: 2, channel: "C12345", starred_date: "2026-04-01" },
    ];
    const view = buildBestView(stars, "au-supply") as any;
    const section = view.blocks.find(
      (b: any) => b.type === "section" && b.accessory,
    );
    expect(section).toBeDefined();
    expect(section.accessory.type).toBe("button");
    expect(section.accessory.url).toBe(
      "https://au-supply.slack.com/archives/C12345/p1711234567123456",
    );
  });

  it("caps at 20 entries", () => {
    const stars: StarData[] = Array.from({ length: 30 }, (_, i) => ({
      posted_ts: `ts${i}`,
      recipe: `recipe-${i}`,
      star_count: 30 - i,
      channel: "C1",
      starred_date: "2026-04-01",
    }));
    const view = buildBestView(stars, "au-supply") as any;
    const sections = view.blocks.filter((b: any) => b.type === "section");
    expect(sections.length).toBeLessThanOrEqual(20);
  });
});

// ---------------------------------------------------------------------------
// buildPinnedView
// ---------------------------------------------------------------------------

describe("buildPinnedView", () => {
  it("returns empty state when no favorites", () => {
    const view = buildPinnedView([]) as any;
    expect(view.type).toBe("modal");
    expect(view.callback_id).toBe("sparagmos_pinned");
    expect(view.submit).toBeUndefined();

    const sectionText = view.blocks
      .filter((b: any) => b.type === "section")
      .map((b: any) => b.text.text);
    expect(sectionText.some((t: string) => t.includes("No pinned recipes"))).toBe(true);
  });

  it("shows pinned recipes with Run buttons", () => {
    const view = buildPinnedView(["acid-wash", "mosaic-dissolution"]) as any;
    const sections = view.blocks.filter(
      (b: any) => b.type === "section" && b.accessory,
    );
    expect(sections).toHaveLength(2);

    // Check first recipe
    expect(sections[0].text.text).toContain("Acid Wash");
    expect(sections[0].accessory.action_id).toBe("run_pinned");
    expect(sections[0].accessory.value).toBe("acid-wash");

    // Check second recipe
    expect(sections[1].text.text).toContain("Mosaic Dissolution");
    expect(sections[1].accessory.value).toBe("mosaic-dissolution");
  });

  it("handles unknown recipe slugs gracefully", () => {
    const view = buildPinnedView(["nonexistent-recipe"]) as any;
    const sections = view.blocks.filter(
      (b: any) => b.type === "section" && b.accessory,
    );
    expect(sections).toHaveLength(1);
    expect(sections[0].text.text).toContain("nonexistent-recipe");
    expect(sections[0].accessory.action_id).toBe("run_pinned");
  });
});

// ---------------------------------------------------------------------------
// buildHelpView
// ---------------------------------------------------------------------------

describe("buildHelpView", () => {
  it("returns a modal with no submit", () => {
    const view = buildHelpView() as any;
    expect(view.type).toBe("modal");
    expect(view.callback_id).toBe("sparagmos_help");
    expect(view.submit).toBeUndefined();
    expect(view.close).toBeDefined();
  });

  it("contains all expected sections", () => {
    const view = buildHelpView() as any;
    const headers = view.blocks
      .filter((b: any) => b.type === "header")
      .map((b: any) => b.text.text);

    expect(headers).toContain("Quick Start");
    expect(headers).toContain("Commands");
    expect(headers).toContain("The Modal");
    expect(headers).toContain("Rating & Voting");
    expect(headers).toContain("Tips");
  });

  it("mentions starring and pinning", () => {
    const view = buildHelpView() as any;
    const allText = view.blocks
      .filter((b: any) => b.type === "section")
      .map((b: any) => b.text.text)
      .join("\n");

    expect(allText).toContain("Star");
    expect(allText).toContain("Pin Recipe");
  });

  it("includes recipe count in tips", () => {
    const view = buildHelpView() as any;
    const allText = view.blocks
      .filter((b: any) => b.type === "section")
      .map((b: any) => b.text.text)
      .join("\n");

    expect(allText).toContain(`${RECIPES.length} recipes available`);
  });
});

// ---------------------------------------------------------------------------
// buildModalView (footer buttons)
// ---------------------------------------------------------------------------

describe("buildModalView footer", () => {
  it("contains footer action buttons", () => {
    const view = buildModalView("C123") as any;
    const footerActions = view.blocks.find(
      (b: any) => b.block_id === "modal_footer_actions",
    );
    expect(footerActions).toBeDefined();
    expect(footerActions.type).toBe("actions");

    const actionIds = footerActions.elements.map((e: any) => e.action_id);
    expect(actionIds).toContain("modal_open_best");
    expect(actionIds).toContain("modal_open_pinned");
    expect(actionIds).toContain("modal_open_help");
  });
});
