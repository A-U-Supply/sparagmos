# Source Images in Thread Reply — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move source image attribution and permalink links from the main Slack message into a thread reply, so only the output image dominates the #img-junkyard feed.

**Architecture:** Split the single Slack post into two: a `files_upload_v2` main message (recipe + effects only) and a `chat.postMessage` thread reply (source attributions with plain display names + unfurling permalink links). Consolidate the duplicated posting logic in `cli.py` into a single `post_result` call.

**Tech Stack:** Python, slack_sdk (WebClient), pytest

**Spec:** `docs/superpowers/specs/2026-04-02-source-images-in-thread-design.md`

---

### Task 1: New formatting functions — `format_main_comment` and `format_thread_reply`

**Files:**
- Modify: `sparagmos/slack_post.py:16-104`
- Test: `tests/test_slack.py`

- [ ] **Step 1: Write failing tests for `format_main_comment`**

In `tests/test_slack.py`, add:

```python
from sparagmos.slack_post import format_main_comment, format_thread_reply


def test_format_main_comment():
    steps = [
        {"effect": "deepdream", "image": "a"},
        {"effect": "blend", "images": ["a", "b"], "into": "canvas"},
        {"effect": "jpeg_destroy"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Mosaic Dissolution",
        steps=steps,
    )
    text = format_main_comment(result)
    assert text == "~ Mosaic Dissolution\ndeepdream(a) → blend(a,b→canvas) → jpeg_destroy"


def test_format_main_comment_no_source_info():
    """Main comment must not contain user mentions, dates, or links."""
    steps = [{"effect": "invert", "image": "a"}]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Simple",
        steps=steps,
    )
    text = format_main_comment(result)
    assert "<@" not in text
    assert "source" not in text.lower()
    assert "original" not in text.lower()
    assert "http" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack.py::test_format_main_comment tests/test_slack.py::test_format_main_comment_no_source_info -v`
Expected: ImportError — `format_main_comment` does not exist yet.

- [ ] **Step 3: Implement `format_main_comment`**

In `sparagmos/slack_post.py`, add after the existing imports:

```python
def format_main_comment(result: PipelineResult) -> str:
    """Format the main Slack message: recipe name + annotated effect chain.

    Source attribution is posted separately in a thread reply.
    """
    chain = " → ".join(_annotate_step(step) for step in result.steps)
    return f"~ {result.recipe_name}\n{chain}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack.py::test_format_main_comment tests/test_slack.py::test_format_main_comment_no_source_info -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for `format_thread_reply`**

In `tests/test_slack.py`, add:

```python
def test_format_thread_reply_multi():
    sources = [
        {"display_name": "brendan", "date": "2026-04-01", "permalink": "https://link1"},
        {"display_name": "jake", "date": "2026-03-30", "permalink": "https://link2"},
    ]
    text = format_thread_reply(sources, "image-gen")
    assert "sources: brendan (2026-04-01), jake (2026-03-30) in #image-gen" in text
    assert "originals: <https://link1|view> · <https://link2|view>" in text
    assert "<@" not in text  # no mentions


def test_format_thread_reply_single():
    sources = [
        {"display_name": "brendan", "date": "2026-04-01", "permalink": "https://link1"},
    ]
    text = format_thread_reply(sources, "image-gen")
    assert "source: brendan (2026-04-01) in #image-gen" in text
    assert "original: <https://link1|view>" in text


def test_format_thread_reply_no_permalink():
    sources = [{"display_name": "brendan", "date": "2026-04-01"}]
    text = format_thread_reply(sources, "image-gen")
    assert "source: brendan (2026-04-01) in #image-gen" in text
    assert "original" not in text
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack.py::test_format_thread_reply_multi tests/test_slack.py::test_format_thread_reply_single tests/test_slack.py::test_format_thread_reply_no_permalink -v`
Expected: ImportError — `format_thread_reply` does not exist yet.

- [ ] **Step 7: Implement `format_thread_reply`**

In `sparagmos/slack_post.py`, add after `format_main_comment`:

```python
def format_thread_reply(
    sources: list[dict],
    channel_name: str = "image-gen",
) -> str:
    """Format the thread reply with source attribution and permalink links.

    Args:
        sources: List of source dicts with 'display_name', 'date', and
            optional 'permalink' keys.
        channel_name: Source channel name for attribution.

    Returns:
        Formatted string for the thread reply text.
    """
    source_label = "source" if len(sources) == 1 else "sources"
    attributions = ", ".join(
        f"{s['display_name']} ({s.get('date', 'unknown')})" for s in sources
    )
    lines = [f"{source_label}: {attributions} in #{channel_name}"]

    permalinks = [s.get("permalink", "") for s in sources if s.get("permalink")]
    if permalinks:
        link_label = "original" if len(permalinks) == 1 else "originals"
        links = " · ".join(f"<{url}|view>" for url in permalinks)
        lines.append(f"{link_label}: {links}")

    return "\n".join(lines)
```

- [ ] **Step 8: Run all new tests**

Run: `uv run pytest tests/test_slack.py::test_format_main_comment tests/test_slack.py::test_format_main_comment_no_source_info tests/test_slack.py::test_format_thread_reply_multi tests/test_slack.py::test_format_thread_reply_single tests/test_slack.py::test_format_thread_reply_no_permalink -v`
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add sparagmos/slack_post.py tests/test_slack.py
git commit -m "feat: add format_main_comment and format_thread_reply functions

Split provenance formatting into two parts: a main comment (recipe +
effects only) and a thread reply (source attribution with plain display
names + permalink links). These replace format_provenance and
format_provenance_multi for the new thread-based posting flow."
```

---

### Task 2: Add `resolve_display_name` helper

**Files:**
- Modify: `sparagmos/slack_post.py`
- Test: `tests/test_slack.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_slack.py`, add:

```python
from sparagmos.slack_post import resolve_display_name


def test_resolve_display_name_uses_display_name():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan Smith"}}
    }
    assert resolve_display_name(client, "U123") == "brendan"
    client.users_info.assert_called_once_with(user="U123")


def test_resolve_display_name_falls_back_to_real_name():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "", "real_name": "Brendan Smith"}}
    }
    assert resolve_display_name(client, "U123") == "Brendan Smith"


def test_resolve_display_name_falls_back_to_user_id():
    client = MagicMock()
    client.users_info.side_effect = Exception("API error")
    assert resolve_display_name(client, "U123") == "U123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack.py::test_resolve_display_name_uses_display_name tests/test_slack.py::test_resolve_display_name_falls_back_to_real_name tests/test_slack.py::test_resolve_display_name_falls_back_to_user_id -v`
Expected: ImportError

- [ ] **Step 3: Implement `resolve_display_name`**

In `sparagmos/slack_post.py`, add:

```python
def resolve_display_name(client: WebClient, user_id: str) -> str:
    """Resolve a Slack user ID to a plain display name.

    Falls back to real_name, then the raw user_id on failure.
    """
    try:
        resp = client.users_info(user=user_id)
        profile = resp["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        logger.warning("Failed to resolve display name for %s", user_id)
        return user_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack.py::test_resolve_display_name_uses_display_name tests/test_slack.py::test_resolve_display_name_falls_back_to_real_name tests/test_slack.py::test_resolve_display_name_falls_back_to_user_id -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_post.py tests/test_slack.py
git commit -m "feat: add resolve_display_name helper

Resolves Slack user IDs to plain display names via users.info API.
Falls back to real_name, then the raw user ID on API failure."
```

---

### Task 3: Update `post_result` to use thread reply and accept multi-source

**Files:**
- Modify: `sparagmos/slack_post.py:107-168`
- Test: `tests/test_slack.py:216-264`

- [ ] **Step 1: Write failing tests for the new `post_result` behavior**

Replace the two existing `post_result` tests in `tests/test_slack.py` with:

```python
def test_post_result_uploads_with_main_comment_only(tmp_path):
    """Main message contains recipe + effects, no source info."""
    client = MagicMock()
    client.files_upload_v2.return_value = {"ok": True}
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15", "permalink": "https://link1"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    call_kwargs = client.files_upload_v2.call_args[1]
    comment = call_kwargs["initial_comment"]
    assert "Test Recipe" in comment
    assert "invert" in comment
    # No source info in main comment
    assert "<@" not in comment
    assert "source" not in comment.lower()
    assert "http" not in comment


def test_post_result_posts_thread_reply(tmp_path):
    """After upload, a thread reply is posted with source attribution."""
    client = MagicMock()
    client.files_upload_v2.return_value = {
        "ok": True,
        "file": {
            "shares": {
                "public": {
                    "C456": [{"ts": "1234567890.123456"}]
                }
            }
        },
    }
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15", "permalink": "https://link1"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    # Thread reply posted
    client.chat_postMessage.assert_called_once()
    reply_kwargs = client.chat_postMessage.call_args[1]
    assert reply_kwargs["channel"] == "C456"
    assert reply_kwargs["thread_ts"] == "1234567890.123456"
    assert "brendan" in reply_kwargs["text"]
    assert "https://link1" in reply_kwargs["text"]

    # chat_update (unfurl suppression) is NOT called
    client.chat_update.assert_not_called()


def test_post_result_no_thread_without_ts(tmp_path):
    """If we can't extract the message ts, skip the thread reply gracefully."""
    client = MagicMock()
    client.files_upload_v2.return_value = {"ok": True}
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    client.chat_postMessage.assert_not_called()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_slack.py::test_post_result_uploads_with_main_comment_only tests/test_slack.py::test_post_result_posts_thread_reply tests/test_slack.py::test_post_result_no_thread_without_ts -v`
Expected: FAIL — `post_result` still uses old signature/behavior.

- [ ] **Step 3: Rewrite `post_result`**

Replace the entire `post_result` function in `sparagmos/slack_post.py` (lines 107-168) with:

```python
def post_result(
    client: WebClient,
    channel_id: str,
    result: PipelineResult,
    sources: list[dict],
    source_channel_name: str,
    temp_dir: Path,
) -> str:
    """Post a processed image to Slack with source info in a thread reply.

    Uploads the output image with a main comment (recipe + effects only),
    then posts source attribution and permalink links as a thread reply.

    Args:
        client: Slack WebClient.
        channel_id: Target channel ID (#img-junkyard).
        result: Pipeline result with image and metadata.
        sources: List of source metadata dicts (user, date, permalink).
        source_channel_name: Name of source channel for attribution.
        temp_dir: Temp directory for saving the image file.

    Returns:
        Message timestamp of the posted message.
    """
    comment = format_main_comment(result)

    # Resolve display names for source attribution
    for s in sources:
        s["display_name"] = resolve_display_name(client, s["user"])

    # Save image to temp file for upload
    image_path = temp_dir / "sparagmos_output.png"
    result.image.save(image_path, "PNG")

    logger.info("Posting to channel %s with comment:\n%s", channel_id, comment)

    response = client.files_upload_v2(
        channel=channel_id,
        file=str(image_path),
        filename="sparagmos.png",
        initial_comment=comment,
    )

    # Extract posted message timestamp from file share data
    posted_ts = ""
    file_obj = response.get("file", {})
    shares = file_obj.get("shares", {})
    public_shares = shares.get("public", {})
    channel_shares = public_shares.get(channel_id, [])
    if channel_shares:
        posted_ts = channel_shares[0].get("ts", "")

    # Post source attribution as a thread reply
    if posted_ts:
        thread_text = format_thread_reply(sources, source_channel_name)
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=posted_ts,
                text=thread_text,
            )
        except Exception:
            logger.warning("Failed to post thread reply, continuing")

    return posted_ts
```

- [ ] **Step 4: Remove old `test_post_suppresses_unfurls` and `test_post_result_calls_upload`**

These two tests (the ones replaced in Step 1) should be removed from the test file. Also remove the old `test_format_provenance` and `test_format_provenance_multi` and `test_format_provenance_multi_single_source` tests — they test functions that will be removed in Task 4.

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/test_slack.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add sparagmos/slack_post.py tests/test_slack.py
git commit -m "feat: post source images in thread reply instead of main message

Update post_result to accept a list of sources, post the output image
with recipe+effects only in the main message, and post source
attribution with plain display names and permalink links as a thread
reply. Remove unfurl suppression (no longer needed)."
```

---

### Task 4: Clean up old functions and update `cli.py`

**Files:**
- Modify: `sparagmos/slack_post.py` — remove `format_provenance` and `format_provenance_multi`
- Modify: `sparagmos/cli.py:394-448` — replace inline posting with `post_result` call

- [ ] **Step 1: Remove `format_provenance` and `format_provenance_multi` from `slack_post.py`**

Delete the `format_provenance` function (lines 16-44) and `format_provenance_multi` function (lines 69-104) from `sparagmos/slack_post.py`. Keep `_annotate_step` — it's used by `format_main_comment`.

- [ ] **Step 2: Update imports in `tests/test_slack.py`**

Change the import line:

```python
# Old:
from sparagmos.slack_post import format_provenance, format_provenance_multi, post_result
# New:
from sparagmos.slack_post import format_main_comment, format_thread_reply, resolve_display_name, post_result
```

(The individual test imports added in Tasks 1-2 can be consolidated into this line.)

- [ ] **Step 3: Replace inline posting in `cli.py`**

Replace `cli.py` lines 394-448 (the `else` block starting with `# Post to Slack`) with:

```python
        else:
            # Post to Slack
            from sparagmos.slack_post import post_result

            junkyard_id = find_channel_id(client, "img-junkyard")
            if not junkyard_id:
                logger.error("Channel #img-junkyard not found")
                sys.exit(1)

            posted_ts = post_result(
                client, junkyard_id, result, source_metadata_list, "image-gen", Path(tmp)
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
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_post.py sparagmos/cli.py tests/test_slack.py
git commit -m "refactor: consolidate cli.py posting into post_result, remove old formatters

Replace inline Slack posting logic in cli.py with a single post_result
call. Remove format_provenance and format_provenance_multi (replaced by
format_main_comment and format_thread_reply)."
```

---

### Task 5: Manual verification

- [ ] **Step 1: Dry run to verify main comment formatting**

Run: `uv run python -m sparagmos --dry-run`
Verify the log output shows the recipe + effect chain with no source info.

- [ ] **Step 2: Live test against Slack**

Run sparagmos normally (or via the GitHub workflow) and verify in #img-junkyard:
- Output image appears expanded in the channel feed
- Main message shows only recipe name + effect chain
- Thread reply shows source attributions with plain display names (not @mentions)
- Source permalink links unfurl in the thread showing image previews
