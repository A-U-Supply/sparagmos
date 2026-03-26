/** A sparagmos recipe definition. */
export interface Recipe {
  slug: string;
  inputs: number;
}

/** All available recipes with their required input counts. */
export const RECIPES: readonly Recipe[] = [
  { slug: "acid-wash", inputs: 3 },
  { slug: "binary-archaeology", inputs: 4 },
  { slug: "broadcast-static", inputs: 3 },
  { slug: "broken-mirror", inputs: 5 },
  { slug: "chimera-engine", inputs: 5 },
  { slug: "collage-surgery", inputs: 4 },
  { slug: "contrast-surgery", inputs: 4 },
  { slug: "cutout-mosaic", inputs: 5 },
  { slug: "data-rot", inputs: 3 },
  { slug: "dissolve-cascade", inputs: 4 },
  { slug: "double-exposure", inputs: 2 },
  { slug: "dream-dissolve", inputs: 2 },
  { slug: "edge-ghosts", inputs: 3 },
  { slug: "edge-lattice", inputs: 5 },
  { slug: "entropy-garden", inputs: 5 },
  { slug: "exquisite-corpse", inputs: 3 },
  { slug: "feedback-loop", inputs: 2 },
  { slug: "fossil-record", inputs: 3 },
  { slug: "fragment-storm", inputs: 5 },
  { slug: "holographic-interference", inputs: 3 },
  { slug: "kaleidoscope-collapse", inputs: 5 },
  { slug: "letterpress", inputs: 4 },
  { slug: "mask-cascade", inputs: 4 },
  { slug: "mask-feedback", inputs: 5 },
  { slug: "mosaic-dissolution", inputs: 5 },
  { slug: "mosaic-rebirth", inputs: 5 },
  { slug: "negative-space", inputs: 4 },
  { slug: "neural-chimera", inputs: 3 },
  { slug: "noise-cathedral", inputs: 4 },
  { slug: "palimpsest", inputs: 4 },
  { slug: "palimpsest-ii", inputs: 5 },
  { slug: "phantom-limb", inputs: 2 },
  { slug: "photogram", inputs: 4 },
  { slug: "sediment-core", inputs: 3 },
  { slug: "shape-imposition", inputs: 5 },
  { slug: "signal-bleed", inputs: 3 },
  { slug: "silhouette-swap", inputs: 5 },
  { slug: "spectral-merge", inputs: 2 },
  { slug: "stamp-collection", inputs: 5 },
  { slug: "stencil-burn", inputs: 4 },
  { slug: "stratum-shift", inputs: 4 },
  { slug: "surveillance-decay", inputs: 4 },
  { slug: "tectonic-overlap", inputs: 4 },
  { slug: "text-ghost", inputs: 4 },
  { slug: "torn-collage", inputs: 4 },
  { slug: "voronoi-chimera", inputs: 3 },
  { slug: "wax-museum", inputs: 3 },
  { slug: "x-ray-composite", inputs: 2 },
] as const;

const slugSet = new Set(RECIPES.map((r) => r.slug));

/** Check whether a slug corresponds to a valid recipe. */
export function isValidRecipe(slug: string): boolean {
  return slugSet.has(slug);
}

/**
 * Format the full recipe list for Slack display, grouped by input count.
 * Uses Slack mrkdwn formatting.
 */
export function formatRecipeList(): string {
  const grouped = new Map<number, string[]>();

  for (const recipe of RECIPES) {
    const list = grouped.get(recipe.inputs);
    if (list) {
      list.push(recipe.slug);
    } else {
      grouped.set(recipe.inputs, [recipe.slug]);
    }
  }

  const sortedKeys = [...grouped.keys()].sort((a, b) => a - b);

  const sections = sortedKeys.map((count) => {
    const slugs = grouped.get(count)!;
    const slugList = slugs.map((s) => `\`${s}\``).join(", ");
    return `*${count} inputs:*\n${slugList}`;
  });

  return `*Available Recipes (${RECIPES.length} total):*\n\n${sections.join("\n\n")}`;
}

/**
 * Find recipes whose slugs contain the given substring.
 * Returns up to 5 matches for use in "did you mean?" suggestions.
 */
export function suggestRecipes(input: string): Recipe[] {
  const lower = input.toLowerCase();
  return RECIPES.filter((r) => r.slug.includes(lower)).slice(0, 5);
}
