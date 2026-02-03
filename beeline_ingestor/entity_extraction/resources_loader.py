"""Utility helpers for loading NZ-specific entity data."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(slots=True)
class NamedResource:
    name: str
    aliases: List[str]
    metadata: dict


def load_named_resources(path: Path) -> list[NamedResource]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    resources: list[NamedResource] = []
    for entry in data:
        resources.append(
            NamedResource(
                name=entry["name"],
                aliases=list(entry.get("aliases", [])),
                metadata={key: value for key, value in entry.items() if key not in {"name", "aliases"}},
            )
        )
    return resources


def iter_named_strings(resources: Iterable[NamedResource]) -> list[str]:
    values: list[str] = []
    for resource in resources:
        values.append(resource.name)
        values.extend(resource.aliases)
    return values
