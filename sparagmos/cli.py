"""CLI entry point for sparagmos."""

from __future__ import annotations

import argparse
import logging
import os
import random
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
    return parser


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

    # Load recipes
    if not recipes_dir.is_dir():
        logger.error("Recipes directory not found: %s", recipes_dir)
        sys.exit(1)
    recipes = load_all_recipes(recipes_dir)
    if not recipes:
        logger.error("No recipes found in %s", recipes_dir)
        sys.exit(1)

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
            recipe_slug = rng.choice(list(matching.keys()))
        else:
            recipe_slug = rng.choice(list(recipes.keys()))
        recipe = recipes[recipe_slug]

    logger.info("Using recipe: %s (%s)", recipe_slug, recipe.name)

    # Get source image(s)
    # source_images is always a list; source_metadata_list is a list of dicts
    if args.input is not None:
        # Local mode — args.input is a list of paths (nargs="+")
        source_images = [Image.open(p).convert("RGB") for p in args.input]
        source_metadata_list = [{"user": "local", "date": "local"} for _ in args.input]
        selected_list = [{"id": Path(p).name} for p in args.input]
    else:
        # Slack mode
        from slack_sdk import WebClient
        from sparagmos.slack_source import (
            find_channel_id,
            fetch_image_files,
            pick_random_image,
            pick_random_images,
            download_image,
        )
        from sparagmos.state import State
        import io

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

        # Output
        if args.output:
            result.image.save(args.output, "PNG")
            logger.info("Saved output to %s", args.output)
        elif args.dry_run:
            logger.info("Dry run — not posting to Slack")
            logger.info("Recipe: %s", result.recipe_name)
            for step in result.steps:
                logger.info("  %s: %s", step["effect"], step["resolved_params"])
        else:
            # Post to Slack
            from sparagmos.slack_post import format_provenance_multi

            junkyard_id = find_channel_id(client, "img-junkyard")
            if not junkyard_id:
                logger.error("Channel #img-junkyard not found")
                sys.exit(1)

            comment = format_provenance_multi(result, source_metadata_list, "image-gen")
            image_path = Path(tmp) / "sparagmos_output.png"
            result.image.save(image_path, "PNG")
            logger.info("Posting to channel %s with comment:\n%s", junkyard_id, comment)
            response = client.files_upload_v2(
                channel=junkyard_id,
                file=str(image_path),
                filename="sparagmos.png",
                initial_comment=comment,
            )
            posted_ts = response.get("ts", "")

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
