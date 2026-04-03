# Source Images in Thread Reply

## Problem

When sparagmos posts to #img-junkyard, both the output image and source image
context appear in the same top-level message. The output image should dominate
the channel feed; source images should be accessible but not clutter it.

## Design

Split the Slack post into two parts:

### Main message (channel feed)

Uploaded via `files_upload_v2` with `initial_comment`:

```
~ Mosaic Dissolution
deepdream(a) -> blend(a,b->canvas) -> jpeg_destroy
```

Contains only the recipe name and annotated effect chain. No source attribution,
no permalink links, no user mentions.

The `chat_update` call to suppress unfurling is removed -- there are no links to
unfurl in the main message.

### Thread reply

Posted via `chat.postMessage` with `thread_ts` set to the main message timestamp:

```
sources: brendan (2026-04-01), jake (2026-03-30) in #image-gen
originals: <permalink1|view> · <permalink2|view>
```

Or for single-source:

```
source: brendan (2026-04-01) in #image-gen
original: <permalink1|view>
```

Source permalink links are **not** suppressed -- they unfurl naturally in the
thread, showing source image previews.

User attribution uses **plain display names** (not `<@USER_ID>` mentions).
Display names are resolved via `client.users_info(user=user_id)`, using
`profile.display_name` with `real_name` as fallback.

## Changes

### `sparagmos/slack_post.py`

1. **Split `format_provenance_multi`** into:
   - `format_main_comment(result)` -- recipe name + annotated effect chain only
   - `format_thread_reply(sources, channel_name)` -- source attributions + links
     with plain display names (names passed in, already resolved)

2. **Update `post_result`**:
   - Use `format_main_comment` for `initial_comment`
   - After upload, post thread reply via `client.chat_postMessage(channel, thread_ts, text)`
   - Remove the `chat_update` unfurl suppression call

3. **Add `resolve_display_name(client, user_id)`** helper:
   - Calls `client.users_info(user=user_id)`
   - Returns `profile.display_name` or `real_name` or `user_id` as fallback

### `sparagmos/cli.py` (~lines 395-448)

The inline posting code duplicates `post_result`. Consolidate: replace the
inline logic with a call to the updated `post_result`. This requires updating
`post_result`'s signature to accept `sources: list[dict]` (multi-source) and
the Slack `client` for name resolution.

### `format_provenance` (single-source version)

This function is used by `post_result`. It will be replaced by the new
`format_main_comment` + `format_thread_reply` pair, so it can be removed.

## Verification

1. Run existing tests to confirm nothing breaks
2. Do a dry run (`--dry-run`) to verify the main comment formatting
3. Test against a real Slack workspace:
   - Output image appears expanded in #img-junkyard
   - Thread reply shows source attributions with plain names
   - Source permalink links unfurl in the thread showing image previews
   - No `@` mentions in thread reply
