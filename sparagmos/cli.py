"""CLI entry point for sparagmos."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import random
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sparagmos",
        description="σπαραγμός — Automated image destruction bot",
    )
    parser.add_argument(
        "--recipe",
        help="Recipe name to use (default: random)",
    )
    parser.add_argument(
        "--chain",
        help="Comma-separated recipe chain (output of each feeds into next)",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        help="Local image file(s) to process (skips Slack scraping)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (skips Slack posting)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process image but don't post to Slack",
    )
    parser.add_argument(
        "--list-recipes",
        action="store_true",
        help="List available recipes and exit",
    )
    parser.add_argument(
        "--list-effects",
        action="store_true",
        help="List available effects and exit",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate all recipes against effect schemas and exit",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducibility",
    )
    parser.add_argument(
        "--recipes-dir",
        default=None,
        help="Path to recipes directory (default: recipes/ in repo root)",
    )
    parser.add_argument(
        "--image-urls",
        default=None,
        help="Comma-separated image URLs to use as inputs (remaining filled from Slack)",
    )
    parser.add_argument(
        "--poster",
        default=None,
        help="Filter images by poster user ID",
    )
    parser.add_argument(
        "--age",
        default=None,
        help="Filter images by age (24h, 7d, 30d, 1-3mo, 3-6mo, 6-12mo, 1y+, 2y+, oldest50)",
    )
    parser.add_argument(
        "--freshness",
        default=None,
        help="Filter images by freshness (prefer_fresh_recipe, only_fresh_recipe, "
        "only_used_recipe, prefer_untouched, only_untouched, only_veterans)",
    )
    parser.add_argument(
        "--rating",
        default=None,
        help="Filter recipes by rating before selection (comma-separated: top,positive,unrated,underdogs)",
    )
    return parser


def _sample_inputs(
    pool: list[Image.Image], n: int, rng: random.Random
) -> list[Image.Image]:
    """Sample *n* images from *pool*, recycling if pool is smaller."""
    if len(pool) >= n:
        return rng.sample(pool, n)
    # Pool smaller than needed — sample with replacement
    return [rng.choice(pool) for _ in range(n)]


def _find_repo_root() -> Path:
    """Find the repository root (where recipes/ lives)."""
    # Try relative to this file first
    pkg_dir = Path(__file__).parent
    repo_root = pkg_dir.parent
    if (repo_root / "recipes").is_dir():
        return repo_root
    # Fall back to cwd
    if (Path.cwd() / "recipes").is_dir():
        return Path.cwd()
    return repo_root


def _load_ratings(repo_root: Path) -> dict[str, int]:
    """Load recipe ratings from ``ratings.json`` at repo root.

    Returns:
        Mapping of recipe slug → integer score, or empty dict if the
        file doesn't exist or is malformed.
    """
    path = repo_root / "ratings.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            result: dict[str, int] = {}
            for k, v in data.items():
                if isinstance(v, dict) and "score" in v:
                    result[k] = int(v["score"])
                elif isinstance(v, (int, float)):
                    result[k] = int(v)
            return result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse ratings.json: %s", exc)
    return {}


def _filter_by_rating(
    slugs: list[str], rating_csv: str, ratings: dict[str, int]
) -> list[str]:
    """Filter recipe slugs by rating categories.

    ``rating_csv`` is a comma-separated string of categories:
    top (score >= 3), positive (score > 0), unrated (score == 0 or absent),
    underdogs (score < 0).  Returns the union of matching slugs.
    """
    categories = {c.strip() for c in rating_csv.split(",") if c.strip()}
    if not categories:
        return slugs

    kept: list[str] = []
    for slug in slugs:
        score = ratings.get(slug, 0)
        if "top" in categories and score >= 3:
            kept.append(slug)
        elif "positive" in categories and score > 0:
            kept.append(slug)
        elif "unrated" in categories and (slug not in ratings or score == 0):
            kept.append(slug)
        elif "underdogs" in categories and score < 0:
            kept.append(slug)
    return kept if kept else slugs  # fall back to all if filter empties the list


def _pick_weighted_recipe(
    rng: random.Random, slugs: list[str], repo_root: Path
) -> str:
    """Pick a recipe slug, using ratings for weighted random if available.

    Weight formula: ``max(1, rating_score + 5)`` — so a rating of -4 maps
    to weight 1, rating 0 maps to 5, and rating 5 maps to 10.
    """
    ratings = _load_ratings(repo_root)
    if not ratings:
        return rng.choice(slugs)

    weights = [max(1, ratings.get(slug, 0) + 5) for slug in slugs]
    return rng.choices(slugs, weights=weights, k=1)[0]


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args(argv)

    # Import here to allow effects to register on import
    from sparagmos.effects import list_effects
    from sparagmos.config import load_all_recipes, validate_recipe

    # Register all effects
    _register_all_effects()

    repo_root = _find_repo_root()
    recipes_dir = Path(args.recipes_dir) if args.recipes_dir else repo_root / "recipes"

    # Handle --list-effects
    if args.list_effects:
        effects = list_effects()
        if not effects:
            print("No effects registered.")
            return
        print(f"{'Effect':<20} {'Description':<50} {'Deps'}")
        print("-" * 80)
        for name, effect in sorted(effects.items()):
            deps = ", ".join(effect.requires) if effect.requires else "none"
            print(f"{name:<20} {effect.description:<50} {deps}")
        return

    # Handle --list-recipes
    if args.list_recipes:
        if not recipes_dir.is_dir():
            print(f"Recipes directory not found: {recipes_dir}")
            sys.exit(1)
        recipes = load_all_recipes(recipes_dir)
        if not recipes:
            print("No recipes found.")
            return
        for slug, recipe in sorted(recipes.items()):
            print(f"  {slug:<25} {recipe.name}")
            if recipe.description:
                desc = recipe.description.strip().split("\n")[0][:60]
                print(f"  {'':25} {desc}")
            print()
        return

    # Handle --validate
    if args.validate:
        if not recipes_dir.is_dir():
            print(f"Recipes directory not found: {recipes_dir}")
            sys.exit(1)
        recipes = load_all_recipes(recipes_dir)
        all_valid = True
        for slug, recipe in sorted(recipes.items()):
            errors = validate_recipe(recipe)
            if errors:
                all_valid = False
                print(f"FAIL {slug}:")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"OK   {slug}")
        sys.exit(0 if all_valid else 1)

    # --- Main pipeline ---
    seed = args.seed if args.seed is not None else random.randint(0, 2**31)

    # Validate mutual exclusion
    if args.chain and args.recipe:
        logger.error("--chain and --recipe are mutually exclusive")
        sys.exit(1)

    # Load recipes
    if not recipes_dir.is_dir():
        logger.error("Recipes directory not found: %s", recipes_dir)
        sys.exit(1)
    recipes = load_all_recipes(recipes_dir)
    if not recipes:
        logger.error("No recipes found in %s", recipes_dir)
        sys.exit(1)

    # Parse chain if provided — first slug becomes the "recipe" for image loading
    chain_slugs: list[str] | None = None
    if args.chain:
        chain_slugs = [s.strip() for s in re.split(r'[\s,]+', args.chain) if s.strip()]
        if len(chain_slugs) < 2:
            logger.error("--chain requires at least 2 recipe slugs")
            sys.exit(1)
        for slug in chain_slugs:
            if slug not in recipes:
                logger.error("Unknown recipe in chain: %s", slug)
                sys.exit(1)
        # Use first recipe in chain for image loading / recipe selection
        args.recipe = chain_slugs[0]
        logger.info("Chain: %s", " → ".join(chain_slugs))

    # Pick recipe
    if args.recipe:
        if args.recipe not in recipes:
            logger.error("Unknown recipe: %s. Available: %s", args.recipe, sorted(recipes.keys()))
            sys.exit(1)
        recipe_slug = args.recipe
        recipe = recipes[recipe_slug]
        # Validate input count when --input is provided
        if args.input is not None and len(args.input) != recipe.inputs:
            logger.error(
                "Recipe '%s' expects %d input(s) but %d file(s) provided",
                recipe_slug,
                recipe.inputs,
                len(args.input),
            )
            sys.exit(1)
    else:
        rng = random.Random(seed)
        # Filter recipes by input count when --input files are given
        if args.input is not None:
            n_inputs = len(args.input)
            matching = {k: v for k, v in recipes.items() if v.inputs == n_inputs}
            if not matching:
                logger.error(
                    "No recipes accept %d input(s). Available input counts: %s",
                    n_inputs,
                    sorted({v.inputs for v in recipes.values()}),
                )
                sys.exit(1)
            eligible = list(matching.keys())
        elif args.image_urls is not None:
            # Prefer recipes that can use all provided URLs (remaining
            # slots are filled from Slack).  Fall back to all recipes if
            # no recipe accepts that many inputs — the CLI will truncate.
            url_count = len([u for u in re.split(r'[\s,]+', args.image_urls) if u.strip()])
            matching = {k: v for k, v in recipes.items() if v.inputs >= url_count}
            if matching:
                eligible = list(matching.keys())
            else:
                logger.warning(
                    "No recipes accept %d+ input(s); will truncate URLs to fit",
                    url_count,
                )
                eligible = list(recipes.keys())
        else:
            eligible = list(recipes.keys())
        # Apply rating filter before weighted pick
        if args.rating:
            ratings = _load_ratings(repo_root)
            eligible = _filter_by_rating(eligible, args.rating, ratings)
        recipe_slug = _pick_weighted_recipe(rng, eligible, repo_root)
        recipe = recipes[recipe_slug]

    logger.info("Using recipe: %s (%s)", recipe_slug, recipe.name)

    # Get source image(s)
    # source_images is always a list; source_metadata_list is a list of dicts
    if args.input is not None:
        # Local mode — args.input is a list of paths (nargs="+")
        source_images = [Image.open(p).convert("RGB") for p in args.input]
        source_metadata_list = [{"user": "local", "date": "local"} for _ in args.input]
        selected_list = [{"id": Path(p).name} for p in args.input]
    elif args.image_urls is not None:
        # URL mode — download provided URLs, fill remaining from Slack
        from slack_sdk import WebClient
        from sparagmos.slack_source import (
            find_channel_id,
            fetch_image_files,
            filter_images,
            pick_random_images,
            download_image,
            download_url,
        )
        from sparagmos.state import State

        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            logger.error("SLACK_BOT_TOKEN not set")
            sys.exit(1)

        client = WebClient(token=token)
        state = State(repo_root / "state.json")
        urls = [u.strip() for u in re.split(r'[\s,]+', args.image_urls) if u.strip()]

        if len(urls) > recipe.inputs:
            logger.warning(
                "Recipe '%s' expects %d input(s) but %d URL(s) provided; using first %d",
                recipe_slug, recipe.inputs, len(urls), recipe.inputs,
            )
            urls = urls[:recipe.inputs]

        source_images = []
        source_metadata_list = []
        selected_list = []
        for url in urls:
            logger.info("Downloading URL: %s", url)
            image_bytes = download_url(url, slack_token=token)
            source_images.append(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
            url_id = "url:" + hashlib.sha256(url.encode()).hexdigest()[:12]
            source_metadata_list.append({
                "user": "url",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "permalink": url,
            })
            selected_list.append({"id": url_id, "url": url})

        # Fill remaining slots from Slack if needed
        remaining = recipe.inputs - len(urls)
        if remaining > 0:

            channel_id = find_channel_id(client, "image-gen")
            if not channel_id:
                logger.error("Channel #image-gen not found")
                sys.exit(1)

            files = fetch_image_files(client, channel_id)
            if not files:
                logger.error("No images found in #image-gen")
                sys.exit(1)

            files = filter_images(
                files, poster=args.poster, age=args.age,
                freshness=args.freshness, recipe=recipe_slug, state=state,
            )
            if not files:
                logger.error("No images remaining after filters")
                sys.exit(1)

            slack_selected = pick_random_images(
                files, recipe_slug, remaining, state.processed_combos(), seed
            )
            if not slack_selected:
                logger.warning(
                    "No unused %d-image combinations for recipe %s", remaining, recipe_slug
                )
                sys.exit(0)

            for sel in slack_selected:
                logger.info("Selected image from Slack: %s", sel["id"])
                image_bytes = download_image(sel["url"], token)
                source_images.append(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
                ts = sel.get("timestamp", 0)
                source_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "unknown"
                source_metadata_list.append({
                    "user": sel["user"],
                    "date": source_date,
                    "permalink": sel.get("permalink", ""),
                })
                selected_list.append(sel)
    else:
        # Slack mode — all images from #image-gen
        from slack_sdk import WebClient
        from sparagmos.slack_source import (
            find_channel_id,
            fetch_image_files,
            filter_images,
            pick_random_image,
            pick_random_images,
            download_image,
        )
        from sparagmos.state import State

        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            logger.error("SLACK_BOT_TOKEN not set")
            sys.exit(1)

        client = WebClient(token=token)
        state = State(repo_root / "state.json")

        channel_id = find_channel_id(client, "image-gen")
        if not channel_id:
            logger.error("Channel #image-gen not found")
            sys.exit(1)

        files = fetch_image_files(client, channel_id)
        if not files:
            logger.error("No images found in #image-gen")
            sys.exit(1)

        files = filter_images(
            files, poster=args.poster, age=args.age,
            freshness=args.freshness, recipe=recipe_slug, state=state,
        )
        if not files:
            logger.error("No images remaining after filters")
            sys.exit(1)

        if recipe.inputs == 1:
            selected = pick_random_image(files, recipe_slug, state.processed_pairs(), seed)
            if not selected:
                logger.warning("All images processed with recipe %s", recipe_slug)
                sys.exit(0)
            selected_list = [selected]
        else:
            selected_list = pick_random_images(
                files, recipe_slug, recipe.inputs, state.processed_combos(), seed
            )
            if not selected_list:
                logger.warning(
                    "No unused %d-image combinations for recipe %s", recipe.inputs, recipe_slug
                )
                sys.exit(0)

        source_images = []
        source_metadata_list = []
        for sel in selected_list:
            logger.info("Selected image: %s", sel["id"])
            image_bytes = download_image(sel["url"], token)
            source_images.append(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
            ts = sel.get("timestamp", 0)
            source_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "unknown"
            source_metadata_list.append({
                "user": sel["user"],
                "date": source_date,
                "permalink": sel.get("permalink", ""),
            })

    # Vision analysis (if recipe needs it) — analyze the first source image
    vision_data = None
    if recipe.vision:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.warning("HF_TOKEN not set, skipping vision analysis")
        else:
            from sparagmos.vision import analyze_image
            vision_data = analyze_image(source_images[0], token=hf_token)

    # Run pipeline
    from sparagmos.pipeline import run_pipeline, IMAGE_NAMES

    # Build pipeline call arguments based on input count
    if recipe.inputs == 1:
        pipeline_kwargs = {"image": source_images[0]}
    else:
        pipeline_kwargs = {"images": dict(zip(IMAGE_NAMES, source_images))}

    # Use first source metadata for single-image compat; multi posts use all
    source_metadata = source_metadata_list[0]

    with tempfile.TemporaryDirectory(prefix="sparagmos_") as tmp:
        result = run_pipeline(
            **pipeline_kwargs,
            recipe=recipe,
            seed=seed,
            temp_dir=Path(tmp),
            vision=vision_data,
            source_metadata=source_metadata,
        )

        # --- Chain continuation (if --chain provided) ---
        if chain_slugs and len(chain_slugs) > 1:
            pool: list[Image.Image] = list(result.images) if result.images else [result.image]
            chain_rng = random.Random(seed)

            for ci in range(1, len(chain_slugs)):
                chain_rec = recipes[chain_slugs[ci]]
                chain_seed = seed + ci
                needed = chain_rec.inputs or 1

                # Re-run previous recipe if pool is too small
                if len(pool) < needed:
                    prev_rec = recipes[chain_slugs[ci - 1]]
                    for rerun in range(5):
                        if len(pool) >= needed:
                            break
                        logger.info(
                            "Pool has %d images, %s needs %d — re-running %s",
                            len(pool), chain_slugs[ci], needed, chain_slugs[ci - 1],
                        )
                        rerun_imgs = _sample_inputs(pool, prev_rec.inputs or 1, chain_rng)
                        if prev_rec.inputs == 1:
                            rkw = {"image": rerun_imgs[0]}
                        else:
                            rkw = {"images": dict(zip(IMAGE_NAMES, rerun_imgs))}
                        rr = run_pipeline(
                            **rkw, recipe=prev_rec, seed=chain_seed + 100 + rerun,
                            temp_dir=Path(tmp), source_metadata=source_metadata,
                        )
                        pool.extend(rr.images if rr.images else [rr.image])

                step_imgs = _sample_inputs(pool, needed, chain_rng)
                logger.info("Chain step %d/%d: %s (%d inputs from pool of %d)",
                            ci + 1, len(chain_slugs), chain_slugs[ci], needed, len(pool))

                if chain_rec.inputs == 1:
                    ckw = {"image": step_imgs[0]}
                else:
                    ckw = {"images": dict(zip(IMAGE_NAMES, step_imgs))}

                result = run_pipeline(
                    **ckw, recipe=chain_rec, seed=chain_seed,
                    temp_dir=Path(tmp), source_metadata=source_metadata,
                )
                pool = list(result.images) if result.images else [result.image]

            # Update slug for output/state to reflect the full chain
            recipe_slug = "+".join(chain_slugs)

        # Output
        if args.output:
            output_path = Path(args.output)
            if result.images and len(result.images) > 1:
                stem = output_path.stem
                suffix = output_path.suffix
                parent = output_path.parent
                for i, img in enumerate(result.images):
                    numbered = parent / f"{stem}_{i+1}{suffix}"
                    img.save(numbered, "PNG")
                    logger.info("Saved output %d/%d to %s", i + 1, len(result.images), numbered)
            else:
                result.image.save(args.output, "PNG")
                logger.info("Saved output to %s", args.output)
        elif args.dry_run:
            logger.info("Dry run — not posting to Slack")
            logger.info("Recipe: %s", result.recipe_name)
            for step in result.steps:
                logger.info("  %s: %s", step["effect"], step["resolved_params"])
        else:
            # Post to Slack
            from sparagmos.slack_post import post_result

            junkyard_id = find_channel_id(client, "img-junkyard")
            if not junkyard_id:
                logger.error("Channel #img-junkyard not found")
                sys.exit(1)

            posted_ts = post_result(
                client, junkyard_id, result, source_metadata_list, "image-gen", Path(tmp),
                recipe_slug=recipe_slug,
            )

            # Update state
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            state.add_multi(
                source_file_ids=[s["id"] for s in selected_list],
                source_dates=[m["date"] for m in source_metadata_list],
                source_users=[m["user"] for m in source_metadata_list],
                recipe=recipe_slug,
                effects=[s["effect"] for s in result.steps],
                processed_date=today,
                posted_ts=posted_ts,
            )
            state.save()
            logger.info("State saved. Done.")


def _register_all_effects():
    """Import all effect modules to trigger registration."""
    import importlib
    import pkgutil

    import sparagmos.effects as effects_pkg

    for importer, modname, ispkg in pkgutil.iter_modules(effects_pkg.__path__):
        try:
            importlib.import_module(f"sparagmos.effects.{modname}")
        except ImportError as e:
            logger.debug("Skipping effect %s: %s", modname, e)
