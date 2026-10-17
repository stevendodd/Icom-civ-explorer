"""Tests for the data store / loader."""

import re

import pytest

from civ_api.store import DataStore, RADIOS_ORDER, _strip_page_refs


def test_default_store_loads_all_radios() -> None:
    store = DataStore.default()
    assert set(store.radios) == set(RADIOS_ORDER)
    for radio in store.radios.values():
        assert radio.command_count > 0


def test_radio_commands_match_summary_count() -> None:
    store = DataStore.default()
    for radio_id in RADIOS_ORDER:
        cmds = store.radio_commands(radio_id)
        assert cmds is not None
        assert len(cmds) == store.radios[radio_id].command_count


def test_total_commands_is_sum_of_radios() -> None:
    store = DataStore.default()
    expected = sum(r.command_count for r in store.radios.values())
    assert len(store.commands) == expected


def test_search_commands_radio_filter() -> None:
    store = DataStore.default()
    items, total = store.search_commands(radio_id="7300", limit=500)
    assert all(c.radio_id == "7300" for c in items)
    assert total == store.radios["7300"].command_count


def test_search_commands_query_matches_any_field() -> None:
    store = DataStore.default()
    items, total = store.search_commands(query="frequency", limit=500)
    assert total > 0
    assert any("frequency" in c.description.lower() for c in items)


def test_search_commands_query_cmd_code() -> None:
    store = DataStore.default()
    items, total = store.search_commands(query="05", limit=500)
    assert total > 0
    assert any(c.cmd == "05" for c in items)


def test_search_commands_pagination() -> None:
    store = DataStore.default()
    page1, total = store.search_commands(limit=10, offset=0)
    page2, _ = store.search_commands(limit=10, offset=10)
    assert len(page1) == 10
    assert len(page2) == 10
    last = (page1[-1].radio_id, page1[-1].cmd, page1[-1].sub_cmd)
    first = (page2[0].radio_id, page2[0].cmd, page2[0].sub_cmd)
    assert last != first  # consecutive pages must not share identical rows


def test_capabilities_for_radio_filters_by_membership() -> None:
    store = DataStore.default()
    caps = store.capabilities_for_radio("9700")
    assert len(caps) > 0
    assert all("9700" in cap.radios for cap in caps)
    sat = next(c for c in caps if c.name == "satellite_mode")
    assert sat.radios["9700"] is True


def test_unknown_radio_returns_none() -> None:
    store = DataStore.default()
    assert store.get_radio("nope") is None
    assert store.radio_commands("nope") is None


def test_strip_page_refs_handles_hyphenated_ranges() -> None:
    # Manual refs with chapter-page ranges: "see p. 20-11" (whole field),
    # mid-string, and leading-prefix forms must be stripped in full.
    assert _strip_page_refs("see p. 20-11") == ""
    assert _strip_page_refs("see p. 20-15 Output the DV RX Call signs") == (
        "Output the DV RX Call signs"
    )
    assert _strip_page_refs("See pp. 18 and 19 Read freq") == "Read freq"
    assert _strip_page_refs("Read freq See pp. 14, 15") == "Read freq"
    # Bare "p. NN-N " prefixes (no "See") are stripped at field start only.
    assert _strip_page_refs("p. 19-9 Send/read SSB RX HPF/LPF settings") == (
        "Send/read SSB RX HPF/LPF settings"
    )
    # Mid-string "p. N" wording is prose, not a page-reference artifact.
    assert _strip_page_refs("per manual p. 28: foo") == "per manual p. 28: foo"


def test_loader_strips_hyphenated_page_refs_from_real_data() -> None:
    # 2026-10-17 feedback triage: 7100 data cells like "see p. 20-11" must be
    # stripped in full (previously left "-11" behind), and 7300 descriptions
    # carry bare "p. 19-9 " prefixes.
    store = DataStore.default()
    cmds = store.radio_commands("7100")
    assert cmds is not None
    freq = next((c for c in cmds if c.cmd == "00" and not c.sub_cmd), None)
    assert freq is not None and freq.data == ""
    dv = next((c for c in cmds if c.cmd == "20" and c.sub_cmd == "01"), None)
    assert dv is not None and not dv.description.startswith("-15")
    cmds = store.radio_commands("7300")
    assert cmds is not None
    send_freq = next(c for c in cmds if c.cmd == "00" and not c.sub_cmd)
    assert send_freq.description == "Send frequency data (transceive)"
    assert not any(re.search(r"^p\. \d", c.description) for c in store.commands)