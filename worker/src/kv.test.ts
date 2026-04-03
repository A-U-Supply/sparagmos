import { describe, it, expect } from "vitest";
import {
  getRatings,
  getUserVotes,
  vote,
  getStars,
  toggleStar,
  getFavorites,
  toggleFavorite,
} from "./kv";
import type { RatingData, StarData } from "./kv";

// ---------------------------------------------------------------------------
// Mock KVNamespace backed by a simple Map
// ---------------------------------------------------------------------------

function createMockKV(): KVNamespace {
  const store = new Map<string, string>();
  return {
    get: async (key: string) => store.get(key) ?? null,
    put: async (key: string, value: string) => {
      store.set(key, value);
    },
    delete: async (key: string) => {
      store.delete(key);
    },
    list: async () => ({ keys: [], list_complete: true, cacheStatus: null }),
    getWithMetadata: async () => ({ value: null, metadata: null, cacheStatus: null }),
  } as unknown as KVNamespace;
}

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

describe("getRatings", () => {
  it("returns empty object when KV is empty", async () => {
    const kv = createMockKV();
    const ratings = await getRatings(kv);
    expect(ratings).toEqual({});
  });
});

describe("vote", () => {
  it("adds a new upvote and returns correct score", async () => {
    const kv = createMockKV();
    const result = await vote(kv, "acid-wash", "user1", 1);

    expect(result.up).toBe(1);
    expect(result.down).toBe(0);
    expect(result.score).toBe(1);
    expect(result.last_voted).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("adds a new downvote and returns correct score", async () => {
    const kv = createMockKV();
    const result = await vote(kv, "acid-wash", "user1", -1);

    expect(result.up).toBe(0);
    expect(result.down).toBe(1);
    expect(result.score).toBe(-1);
  });

  it("toggles off when same direction clicked again", async () => {
    const kv = createMockKV();

    // Vote up
    await vote(kv, "acid-wash", "user1", 1);
    // Vote up again — should toggle off
    const result = await vote(kv, "acid-wash", "user1", 1);

    expect(result.up).toBe(0);
    expect(result.down).toBe(0);
    expect(result.score).toBe(0);
  });

  it("changes vote from up to down", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", 1);
    const result = await vote(kv, "acid-wash", "user1", -1);

    expect(result.up).toBe(0);
    expect(result.down).toBe(1);
    expect(result.score).toBe(-1);
  });

  it("changes vote from down to up", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", -1);
    const result = await vote(kv, "acid-wash", "user1", 1);

    expect(result.up).toBe(1);
    expect(result.down).toBe(0);
    expect(result.score).toBe(1);
  });
});

describe("getUserVotes", () => {
  it("returns empty object for a user with no votes", async () => {
    const kv = createMockKV();
    const votes = await getUserVotes(kv, "user1");
    expect(votes).toEqual({});
  });

  it("tracks per-user votes correctly", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", 1);
    await vote(kv, "mosaic-dissolution", "user1", -1);

    const votes = await getUserVotes(kv, "user1");
    expect(votes["acid-wash"]).toBe(1);
    expect(votes["mosaic-dissolution"]).toBe(-1);
  });

  it("removes vote entry when toggled off", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", 1);
    await vote(kv, "acid-wash", "user1", 1); // toggle off

    const votes = await getUserVotes(kv, "user1");
    expect(votes["acid-wash"]).toBeUndefined();
  });
});

describe("multiple users voting on same recipe", () => {
  it("accumulates votes from different users", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", 1);
    await vote(kv, "acid-wash", "user2", 1);
    const result = await vote(kv, "acid-wash", "user3", -1);

    expect(result.up).toBe(2);
    expect(result.down).toBe(1);
    expect(result.score).toBe(1);
  });

  it("keeps per-user votes isolated", async () => {
    const kv = createMockKV();

    await vote(kv, "acid-wash", "user1", 1);
    await vote(kv, "acid-wash", "user2", -1);

    const user1Votes = await getUserVotes(kv, "user1");
    const user2Votes = await getUserVotes(kv, "user2");

    expect(user1Votes["acid-wash"]).toBe(1);
    expect(user2Votes["acid-wash"]).toBe(-1);
  });
});

// ---------------------------------------------------------------------------
// Stars
// ---------------------------------------------------------------------------

describe("getStars", () => {
  it("returns empty array when KV is empty", async () => {
    const kv = createMockKV();
    const stars = await getStars(kv);
    expect(stars).toEqual([]);
  });
});

describe("toggleStar", () => {
  it("adds a star and returns starred: true", async () => {
    const kv = createMockKV();
    const result = await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");

    expect(result.starred).toBe(true);
    expect(result.star_count).toBe(1);

    const stars = await getStars(kv);
    expect(stars).toHaveLength(1);
    expect(stars[0].posted_ts).toBe("ts1");
    expect(stars[0].recipe).toBe("acid-wash");
    expect(stars[0].channel).toBe("#img-junkyard");
    expect(stars[0].starred_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("removes star on second call and returns starred: false", async () => {
    const kv = createMockKV();

    await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");
    const result = await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");

    expect(result.starred).toBe(false);
    expect(result.star_count).toBe(0);
  });

  it("removes entry when star count reaches 0", async () => {
    const kv = createMockKV();

    await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");
    await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");

    const stars = await getStars(kv);
    expect(stars).toHaveLength(0);
  });

  it("accumulates stars from multiple users", async () => {
    const kv = createMockKV();

    await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");
    const result = await toggleStar(kv, "ts1", "acid-wash", "user2", "#img-junkyard");

    expect(result.starred).toBe(true);
    expect(result.star_count).toBe(2);
  });

  it("only removes one user's star, not all", async () => {
    const kv = createMockKV();

    await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");
    await toggleStar(kv, "ts1", "acid-wash", "user2", "#img-junkyard");
    const result = await toggleStar(kv, "ts1", "acid-wash", "user1", "#img-junkyard");

    expect(result.starred).toBe(false);
    expect(result.star_count).toBe(1);

    const stars = await getStars(kv);
    expect(stars).toHaveLength(1);
    expect(stars[0].star_count).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

describe("getFavorites", () => {
  it("returns empty array for a new user", async () => {
    const kv = createMockKV();
    const favorites = await getFavorites(kv, "user1");
    expect(favorites).toEqual([]);
  });
});

describe("toggleFavorite", () => {
  it("adds a slug to favorites", async () => {
    const kv = createMockKV();
    const result = await toggleFavorite(kv, "user1", "acid-wash");

    expect(result.favorited).toBe(true);

    const favorites = await getFavorites(kv, "user1");
    expect(favorites).toContain("acid-wash");
  });

  it("removes a slug on second toggle", async () => {
    const kv = createMockKV();

    await toggleFavorite(kv, "user1", "acid-wash");
    const result = await toggleFavorite(kv, "user1", "acid-wash");

    expect(result.favorited).toBe(false);

    const favorites = await getFavorites(kv, "user1");
    expect(favorites).not.toContain("acid-wash");
  });

  it("handles multiple favorites for one user", async () => {
    const kv = createMockKV();

    await toggleFavorite(kv, "user1", "acid-wash");
    await toggleFavorite(kv, "user1", "mosaic-dissolution");
    await toggleFavorite(kv, "user1", "double-exposure");

    const favorites = await getFavorites(kv, "user1");
    expect(favorites).toHaveLength(3);
    expect(favorites).toContain("acid-wash");
    expect(favorites).toContain("mosaic-dissolution");
    expect(favorites).toContain("double-exposure");
  });

  it("only removes the targeted slug", async () => {
    const kv = createMockKV();

    await toggleFavorite(kv, "user1", "acid-wash");
    await toggleFavorite(kv, "user1", "mosaic-dissolution");
    await toggleFavorite(kv, "user1", "acid-wash"); // remove

    const favorites = await getFavorites(kv, "user1");
    expect(favorites).toHaveLength(1);
    expect(favorites).toContain("mosaic-dissolution");
  });

  it("keeps favorites isolated between users", async () => {
    const kv = createMockKV();

    await toggleFavorite(kv, "user1", "acid-wash");
    await toggleFavorite(kv, "user2", "mosaic-dissolution");

    const user1Favs = await getFavorites(kv, "user1");
    const user2Favs = await getFavorites(kv, "user2");

    expect(user1Favs).toEqual(["acid-wash"]);
    expect(user2Favs).toEqual(["mosaic-dissolution"]);
  });
});
