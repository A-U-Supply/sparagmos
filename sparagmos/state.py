"""JSON state management for tracking processed images."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProcessedEntry:
    """Record of a processed image (supports multi-source inputs)."""

    source_file_ids: list[str]
    source_dates: list[str]
    source_users: list[str]
    recipe: str
    effects: list[str]
    processed_date: str
    posted_ts: str = ""


def _load_entry(data: dict) -> ProcessedEntry:
    """Construct a ProcessedEntry from raw dict, handling old single-source format."""
    # Backward compat: old format used singular keys
    if "source_file_id" in data:
        return ProcessedEntry(
            source_file_ids=[data["source_file_id"]],
            source_dates=[data["source_date"]],
            source_users=[data["source_user"]],
            recipe=data["recipe"],
            effects=data["effects"],
            processed_date=data["processed_date"],
            posted_ts=data.get("posted_ts", ""),
        )
    return ProcessedEntry(**data)


@dataclass
class State:
    """Manages the state.json file tracking processed images."""

    path: Path
    processed: list[ProcessedEntry] = field(default_factory=list)

    def __init__(self, path: Path):
        self.path = path
        self.processed = []
        if path.exists():
            data = json.loads(path.read_text())
            for entry in data.get("processed", []):
                self.processed.append(_load_entry(entry))

    def add(
        self,
        source_file_id: str,
        source_date: str,
        source_user: str,
        recipe: str,
        effects: list[str],
        processed_date: str,
        posted_ts: str = "",
    ) -> None:
        """Add a new processed entry (single-source, backward-compatible)."""
        self.add_multi(
            source_file_ids=[source_file_id],
            source_dates=[source_date],
            source_users=[source_user],
            recipe=recipe,
            effects=effects,
            processed_date=processed_date,
            posted_ts=posted_ts,
        )

    def add_multi(
        self,
        source_file_ids: list[str],
        source_dates: list[str],
        source_users: list[str],
        recipe: str,
        effects: list[str],
        processed_date: str,
        posted_ts: str = "",
    ) -> None:
        """Add a new processed entry with multiple source files."""
        self.processed.append(
            ProcessedEntry(
                source_file_ids=source_file_ids,
                source_dates=source_dates,
                source_users=source_users,
                recipe=recipe,
                effects=effects,
                processed_date=processed_date,
                posted_ts=posted_ts,
            )
        )

    def save(self) -> None:
        """Write state to disk."""
        data = {"processed": [asdict(e) for e in self.processed]}
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    def is_processed(self, file_id: str, recipe: str) -> bool:
        """Check if a file+recipe pair has been processed."""
        return (file_id, recipe) in self.processed_pairs()

    def all_file_ids(self) -> set[str]:
        """Return all source file IDs that have been processed."""
        return {fid for e in self.processed for fid in e.source_file_ids}

    def processed_pairs(self) -> set[tuple[str, str]]:
        """Return all (file_id, recipe) pairs that have been processed."""
        return {
            (fid, e.recipe)
            for e in self.processed
            for fid in e.source_file_ids
        }

    def processed_combos(self) -> set[tuple[frozenset[str], str]]:
        """Return all (frozenset(file_ids), recipe) combos that have been processed."""
        return {(frozenset(e.source_file_ids), e.recipe) for e in self.processed}
