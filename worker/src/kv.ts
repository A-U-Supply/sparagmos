// ---------------------------------------------------------------------------
// KV operations for ratings, stars, and favorites
// ---------------------------------------------------------------------------

/** Per-recipe rating data stored in KV. */
export interface RatingData {
  up: number;
  down: number;
  score: number;
  last_voted: string;
  up_voters: string[];
  down_voters: string[];
}

/** A starred recipe entry stored in KV. */
export interface StarData {
  posted_ts: string;
  recipe: string;
  star_count: number;
  channel: string;
  starred_date: string;
}

// ---------------------------------------------------------------------------
// Ratings
// ---------------------------------------------------------------------------

/** Get all ratings from KV. Returns empty object if none exist. */
export async function getRatings(
  kv: KVNamespace,
): Promise<Record<string, RatingData>> {
  const raw = await kv.get("ratings");
  if (!raw) return {};
  return JSON.parse(raw) as Record<string, RatingData>;
}

/** Get a specific user's votes. Returns empty object if none exist. */
export async function getUserVotes(
  kv: KVNamespace,
  userId: string,
): Promise<Record<string, number>> {
  const raw = await kv.get(`votes:${userId}`);
  if (!raw) return {};
  return JSON.parse(raw) as Record<string, number>;
}

/**
 * Cast or toggle a vote on a recipe.
 *
 * - If the user has no existing vote, add the vote.
 * - If the user's existing vote matches the direction, toggle it off (remove).
 * - If the user's existing vote differs, change the vote.
 *
 * Returns the updated rating for that recipe.
 */
export async function vote(
  kv: KVNamespace,
  slug: string,
  userId: string,
  direction: 1 | -1,
): Promise<RatingData> {
  const ratings = await getRatings(kv);
  const userVotes = await getUserVotes(kv, userId);

  const existing = userVotes[slug] as 1 | -1 | undefined;
  const rating: RatingData = ratings[slug] ?? {
    up: 0,
    down: 0,
    score: 0,
    last_voted: "",
    up_voters: [],
    down_voters: [],
  };

  // Backfill voter arrays for legacy data
  if (!rating.up_voters) rating.up_voters = [];
  if (!rating.down_voters) rating.down_voters = [];

  if (existing === direction) {
    // Toggle off: remove the vote
    if (direction === 1) {
      rating.up -= 1;
      rating.up_voters = rating.up_voters.filter((id) => id !== userId);
    } else {
      rating.down -= 1;
      rating.down_voters = rating.down_voters.filter((id) => id !== userId);
    }
    delete userVotes[slug];
  } else if (existing !== undefined) {
    // Change vote: undo old, apply new
    if (existing === 1) {
      rating.up -= 1;
      rating.up_voters = rating.up_voters.filter((id) => id !== userId);
    } else {
      rating.down -= 1;
      rating.down_voters = rating.down_voters.filter((id) => id !== userId);
    }
    if (direction === 1) {
      rating.up += 1;
      rating.up_voters.push(userId);
    } else {
      rating.down += 1;
      rating.down_voters.push(userId);
    }
    userVotes[slug] = direction;
  } else {
    // New vote
    if (direction === 1) {
      rating.up += 1;
      rating.up_voters.push(userId);
    } else {
      rating.down += 1;
      rating.down_voters.push(userId);
    }
    userVotes[slug] = direction;
  }

  rating.score = rating.up - rating.down;
  rating.last_voted = new Date().toISOString().slice(0, 10);

  ratings[slug] = rating;
  await kv.put("ratings", JSON.stringify(ratings));
  await kv.put(`votes:${userId}`, JSON.stringify(userVotes));

  return rating;
}

// ---------------------------------------------------------------------------
// Stars
// ---------------------------------------------------------------------------

/** Get all starred recipes from KV. Returns empty array if none exist. */
export async function getStars(kv: KVNamespace): Promise<StarData[]> {
  const raw = await kv.get("stars");
  if (!raw) return [];
  return JSON.parse(raw) as StarData[];
}

/** Get the list of user IDs who starred a specific post. */
async function getStarVoters(
  kv: KVNamespace,
  postedTs: string,
): Promise<string[]> {
  const raw = await kv.get(`star_voters:${postedTs}`);
  if (!raw) return [];
  return JSON.parse(raw) as string[];
}

/**
 * Toggle a star on a recipe post.
 *
 * - If the user already starred it, remove their star (decrement count).
 *   If count reaches 0, remove the entry entirely.
 * - If the user hasn't starred it, add their star (increment count,
 *   create entry if needed).
 */
export async function toggleStar(
  kv: KVNamespace,
  postedTs: string,
  recipe: string,
  userId: string,
  channel: string,
): Promise<{ starred: boolean; star_count: number }> {
  const stars = await getStars(kv);
  const voters = await getStarVoters(kv, postedTs);

  const userIndex = voters.indexOf(userId);
  const entryIndex = stars.findIndex((s) => s.posted_ts === postedTs);

  if (userIndex !== -1) {
    // User already starred — remove their star
    voters.splice(userIndex, 1);

    if (entryIndex !== -1) {
      stars[entryIndex].star_count -= 1;

      if (stars[entryIndex].star_count <= 0) {
        // Remove the entry entirely
        stars.splice(entryIndex, 1);
        await kv.put("stars", JSON.stringify(stars));
        await kv.delete(`star_voters:${postedTs}`);
        return { starred: false, star_count: 0 };
      }
    }

    await kv.put("stars", JSON.stringify(stars));
    await kv.put(`star_voters:${postedTs}`, JSON.stringify(voters));
    return {
      starred: false,
      star_count: entryIndex !== -1 ? stars[entryIndex].star_count : 0,
    };
  }

  // User hasn't starred — add their star
  voters.push(userId);

  if (entryIndex !== -1) {
    stars[entryIndex].star_count += 1;
  } else {
    stars.push({
      posted_ts: postedTs,
      recipe,
      star_count: 1,
      channel,
      starred_date: new Date().toISOString().slice(0, 10),
    });
  }

  await kv.put("stars", JSON.stringify(stars));
  await kv.put(`star_voters:${postedTs}`, JSON.stringify(voters));

  const currentEntry = stars.find((s) => s.posted_ts === postedTs)!;
  return { starred: true, star_count: currentEntry.star_count };
}

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

/** Get a user's favorite recipe slugs. Returns empty array if none exist. */
export async function getFavorites(
  kv: KVNamespace,
  userId: string,
): Promise<string[]> {
  const raw = await kv.get(`favorites:${userId}`);
  if (!raw) return [];
  return JSON.parse(raw) as string[];
}

/**
 * Toggle a recipe in a user's favorites list.
 *
 * - If the slug is already in the list, remove it.
 * - If the slug is not in the list, add it.
 */
export async function toggleFavorite(
  kv: KVNamespace,
  userId: string,
  slug: string,
): Promise<{ favorited: boolean }> {
  const favorites = await getFavorites(kv, userId);
  const index = favorites.indexOf(slug);

  if (index !== -1) {
    favorites.splice(index, 1);
    await kv.put(`favorites:${userId}`, JSON.stringify(favorites));
    return { favorited: false };
  }

  favorites.push(slug);
  await kv.put(`favorites:${userId}`, JSON.stringify(favorites));
  return { favorited: true };
}
