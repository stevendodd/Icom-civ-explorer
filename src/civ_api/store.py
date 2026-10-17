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

from .models import Capability, Command, CommandNote, RadioSummary

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
# number, comma-separated, "and"-separated (e.g. "pp. 19 and 22"), or a
# hyphenated chapter-page range (e.g. "see p. 20-11"). A bare prefix without
# "See" (e.g. "p. 19-9 Send/read ...", printed in some manuals) is stripped
# only when it occurs at the very start of the field — mid-string "p. N"
# wording ("per manual p. 28") is kept.
_PAGE_NUM = r"\d+(?:\s*-\s*\d+)?"
_PAGES_LIST = rf"{_PAGE_NUM}(?:\s*(?:,\s*{_PAGE_NUM}|and\s+{_PAGE_NUM}))*"
_PAGES_TAIL = r"\s*\.?\s*"
_SEE_PAGE_RE = re.compile(
    rf"\s*See [pP]p?\.\s*{_PAGES_LIST}{_PAGES_TAIL}", re.IGNORECASE
)
_BARE_PAGE_PREFIX_RE = re.compile(rf"^[pP]p?\.\s*{_PAGES_LIST}{_PAGES_TAIL}")


def _strip_page_refs(value: str) -> tuple[str, list[str]]:
    """Split manual page references ("See p. <n>") off a CSV field value.

    Returns ``(cleaned, refs)`` where ``refs`` are the normalized page tokens
    ("p. 17", "pp. 18 and 19", "p. 19-9") in order of appearance. The refs
    surface as ``Command.page_refs``; the cleaned text is what the API/UI
    render (previously the refs were discarded outright).
    """
    found: list[str] = []

    def _capture(match: re.Match) -> str:
        found.append(match.group(0).strip())
        return " "

    cleaned = _SEE_PAGE_RE.sub(_capture, value)
    bare = _BARE_PAGE_PREFIX_RE.match(cleaned)
    if bare:
        found.append(bare.group(0).strip())
        cleaned = _BARE_PAGE_PREFIX_RE.sub("", cleaned, count=1)
    # Tidy a leading separator left by a stripped leading "See p. N. ".
    cleaned = re.sub(r"^\s*\.?\s*", "", cleaned)
    refs = []
    for raw in found:
        token = re.sub(r"(?i)^see\s+", "", raw).strip().rstrip(".").strip()
        if token:
            refs.append(" ".join(token.split()))
    return " ".join(cleaned.split()).strip(), refs


def _data_dir() -> Path:
    """Return the path to the bundled data directory."""
    with resources.as_file(resources.files("civ_api").joinpath("data")) as p:
        return Path(p)


def _load_capabilities_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_command_notes(path: Path) -> dict[tuple[str, str, str], list[CommandNote]]:
    """Load a radio's curated note file: data/civ-command-notes-<id>.json.

    Maps each note's ``matches`` entries (cmd, sub_cmd, data) to the note.
    A missing file simply yields no notes for that radio.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    index: dict[tuple[str, str, str], list[CommandNote]] = {}
    for note in raw.get("notes", []):
        obj = CommandNote(
            title=note.get("title") or "",
            body=note.get("body") or "",
            kind=note.get("kind") or "panel",
            pages=[int(p) for p in (note.get("pages") or [])],
            scope=note.get("scope") or "row",
        )
        for m in note.get("matches", []):
            key = (m["cmd"], m["sub_cmd"], m["data"])
            index.setdefault(key, []).append(obj)
    return index


def _load_command_csv(path: Path, radio_id: str) -> list[Command]:
    """Parse a CI-V command table CSV into :class:`Command` rows.

    The CSV has 4 quoted columns: ``Cmd.``, ``Sub cmd.``, ``Data``,
    ``Description``. Rows where Cmd is empty are skipped (they are
    continuation/formatting artifacts in the source tables).
    """
    notes_index = _load_command_notes(path.with_name(f"civ-command-notes-{radio_id}.json"))
    commands: list[Command] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cmd = (row.get("Cmd.") or "").strip()
            if not cmd:
                continue
            sub = (row.get("Sub cmd.") or "").strip()
            data, data_refs = _strip_page_refs((row.get("Data") or "").strip())
            description, refs = _strip_page_refs((row.get("Description") or "").strip())
            seen = set()
            page_refs = []
            for ref in data_refs + refs:
                if ref not in seen:
                    seen.add(ref)
                    page_refs.append(ref)
            # Rows whose description cited nothing may still cite refs in
            # the raw data cell ("see p. 22" placeholders).
            commands.append(
                Command(
                    radio_id=radio_id,
                    cmd=cmd,
                    sub_cmd=sub,
                    data=data,
                    description=description,
                    page_refs=page_refs,
                    notes=notes_index.get((cmd, sub, data), []),
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
                if c.notes:
                    hay += " " + " ".join(
                        (n.title or "") + " " + (n.body or "") for n in c.notes
                    ).lower()
                return all(tok in hay for tok in tokens)
            filtered = [c for c in pool if matches(c)]
        else:
            filtered = list(pool)

        total = len(filtered)
        return filtered[offset : offset + limit], total