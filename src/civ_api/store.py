"""Data loader for CI-V reference data.

Loads the per-radio command tables (CSV), the radio registry + capabilities
JSON, and builds an in-memory index at startup. The data files live in the
bundled ``data/`` directory and are the source of truth for the API.
"""

from __future__ import annotations

import csv
import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from .models import Capability, Command, RadioSummary

# Canonical radio id -> model name (kept in sync with civ-radio-capabilities.json).
# The 9700 is the multi-band satellite/VHF+UHF/SHF rig; the rest are HF/50 MHz.
RADIOS_ORDER: tuple[str, ...] = (
    "705",
    "7100",
    "7300",
    "7300mk2",
    "7610",
    "7760",
    "9700",
)

# Matches manual page references in the source command tables, e.g. a standalone
# "See p. 20", "See pp. 18 and 19", "See pp. 14, 15", a leading "See p. 20. "
# prefix, or a trailing " See p. 16.". These are source-document artifacts (Icom
# CI-V manual page numbers) that are not meaningful in this reference API and
# must not surface in the UI or API responses. The page list may be a single
# number, comma-separated, or "and"-separated (e.g. "pp. 19 and 22").
_SEE_PAGE_RE = re.compile(
    r"\s*See p+p?\.\s*[\d,\s]+(?:and\s+\d+)?\s*\.?\s*", re.IGNORECASE
)


def _strip_page_refs(value: str) -> str:
    """Remove manual page references ("See p. <n>") from a CSV field value."""
    # Remove any occurrence (standalone, leading, trailing, or mid-string),
    # collapsing leftover whitespace and stray leading separators.
    cleaned = _SEE_PAGE_RE.sub(" ", value)
    # Tidy a leading separator left by a stripped leading "See p. N. ".
    cleaned = re.sub(r"^\s*\.?\s*", "", cleaned)
    return " ".join(cleaned.split()).strip()


def _data_dir() -> Path:
    """Return the path to the bundled data directory."""
    with resources.as_file(resources.files("civ_api").joinpath("data")) as p:
        return Path(p)


def _load_capabilities_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_command_csv(path: Path, radio_id: str) -> list[Command]:
    """Parse a CI-V command table CSV into :class:`Command` rows.

    The CSV has 4 quoted columns: ``Cmd.``, ``Sub cmd.``, ``Data``,
    ``Description``. Rows where Cmd is empty are skipped (they are
    continuation/formatting artifacts in the source tables).
    """
    commands: list[Command] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cmd = (row.get("Cmd.") or "").strip()
            if not cmd:
                continue
            commands.append(
                Command(
                    radio_id=radio_id,
                    cmd=cmd,
                    sub_cmd=(row.get("Sub cmd.") or "").strip(),
                    data=_strip_page_refs((row.get("Data") or "").strip()),
                    description=_strip_page_refs((row.get("Description") or "").strip()),
                )
            )
    return commands


class DataStore:
    """In-memory index of radios, commands, and capabilities.

    Built once at startup and shared across requests (the reference data is
    read-only). Feedback submissions are appended to a JSONL file and never
    modify this index.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.radios: dict[str, RadioSummary] = {}
        self.capabilities: list[Capability] = []
        self.commands: list[Command] = []
        self._by_radio: dict[str, list[Command]] = {}
        self._radio_meta: dict[str, dict[str, Any]] = {}

        self._load()

    @classmethod
    def default(cls) -> "DataStore":
        return cls(_data_dir())

    def _load(self) -> None:
        caps_path = self.data_dir / "civ-radio-capabilities.json"
        raw = _load_capabilities_json(caps_path)

        for entry in raw["radios"]:
            radio_id = entry["id"]
            csv_name = entry["csv"]
            csv_path = self.data_dir / csv_name
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"Command table for radio {radio_id} not found: {csv_path}"
                )
            rows = _load_command_csv(csv_path, radio_id)
            self._by_radio[radio_id] = rows
            self.commands.extend(rows)
            self._radio_meta[radio_id] = entry
            self.radios[radio_id] = RadioSummary(
                id=radio_id,
                name=entry["name"],
                address=entry["address"],
                command_count=len(rows),
            )

        for cap in raw.get("capabilities", []):
            self.capabilities.append(Capability(**cap))

    def list_radios(self) -> list[RadioSummary]:
        """Radios in canonical order."""
        return [self.radios[rid] for rid in RADIOS_ORDER if rid in self.radios]

    def get_radio(self, radio_id: str) -> RadioSummary | None:
        return self.radios.get(radio_id)

    def radio_commands(self, radio_id: str) -> list[Command] | None:
        return self._by_radio.get(radio_id)

    def capabilities_for_radio(self, radio_id: str) -> list[Capability]:
        """Capabilities that mention the radio, with that radio's value exposed."""
        out: list[Capability] = []
        for cap in self.capabilities:
            if radio_id in cap.radios:
                out.append(cap)
        return out

    def search_commands(
        self,
        *,
        radio_id: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Command], int]:
        """Search commands by radio and/or free-text query.

        The query matches against ``cmd``, ``sub_cmd``, ``data``, and
        ``description`` (case-insensitive). A command matches if *any* field
        contains the query string.
        """
        pool = self._by_radio.get(radio_id, []) if radio_id else self.commands

        if query:
            tokens = query.lower().split()
            def matches(c: Command) -> bool:
                hay = (c.cmd + " " + c.sub_cmd + " " + c.data + " " + c.description).lower()
                return all(tok in hay for tok in tokens)
            filtered = [c for c in pool if matches(c)]
        else:
            filtered = list(pool)

        total = len(filtered)
        return filtered[offset : offset + limit], total