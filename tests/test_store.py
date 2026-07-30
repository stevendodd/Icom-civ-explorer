"""Tests for the data store / loader."""

from civ_api.store import DataStore, RADIOS_ORDER


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