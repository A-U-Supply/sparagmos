"""JSON state management for tracking processed images."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProcessedEntry:
    """Record of a processed image."""

    source_file_id: str
    source_date: str
    source_user: str
    recipe: str
    effects: list[str]
    processed_date: str
    posted_ts: str = ""


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
                self.processed.append(ProcessedEntry(**entry))

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
        """Add a new processed entry."""
        self.processed.append(
            ProcessedEntry(
                source_file_id=source_file_id,
                source_date=source_date,
                source_user=source_user,
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
        return {e.source_file_id for e in self.processed}

    def processed_pairs(self) -> set[tuple[str, str]]:
        """Return all (file_id, recipe) pairs that have been processed."""
        return {(e.source_file_id, e.recipe) for e in self.processed}
