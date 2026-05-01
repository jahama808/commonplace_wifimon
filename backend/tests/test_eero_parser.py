"""Unit tests for the eero parser (SPEC §5.2 + §11 checklist).

Each branch of the online/offline determination ladder is covered with a
sample payload. Both bare and `{data: {...}}`-wrapped envelopes are exercised.
"""
from __future__ import annotations

import pytest

from app.eero.parser import (
    bucket_connected_by_ssid,
    determine_online,
    device_eero_serial,
    extract_device_list,
    extract_network_metadata,
    unwrap,
)


class TestUnwrap:
    def test_returns_inner_dict_when_wrapped(self):
        assert unwrap({"data": {"x": 1}}) == {"x": 1}

    def test_returns_self_when_bare(self):
        assert unwrap({"x": 1}) == {"x": 1}

    def test_non_dict_returns_empty(self):
        assert unwrap(None) == {}
        assert unwrap("x") == {}
        assert unwrap([1, 2]) == {}

    def test_data_is_a_list_falls_through(self):
        # device-list shape — `data` is a list, NOT the network record
        assert unwrap({"data": [1, 2, 3]}) == {"data": [1, 2, 3]}


class TestDetermineOnlineLadder:
    # Step 1 — health.internet.status
    @pytest.mark.parametrize("status", ["connected", "online", "up", "ok", "green", "GREEN"])
    def test_step1_internet_status_strings(self, status):
        assert determine_online({"health": {"internet": {"status": status}}}) is True

    def test_step1_unknown_string_falls_through(self):
        # Unknown internet.status alone shouldn't return True; should fall through
        # and ultimately return False if nothing else matches.
        assert determine_online({"health": {"internet": {"status": "weird"}}}) is False

    # Step 2 — health.internet.isp_up boolean
    def test_step2_isp_up_true(self):
        assert determine_online({"health": {"internet": {"isp_up": True}}}) is True

    def test_step2_isp_up_false(self):
        assert determine_online({"health": {"internet": {"isp_up": False}}}) is False

    # Step 3 — health.status
    @pytest.mark.parametrize("status", ["green", "yellow", "healthy", "ok"])
    def test_step3_health_status(self, status):
        assert determine_online({"health": {"status": status}}) is True

    # Step 4 — top-level status
    @pytest.mark.parametrize("status,expected", [("green", True), ("yellow", True), ("red", False)])
    def test_step4_top_level_status(self, status, expected):
        assert determine_online({"status": status}) is expected

    def test_step4_top_level_unknown_string(self):
        # Unknown top-level status falls through; nothing else matches → False
        assert determine_online({"status": "lemon"}) is False

    # Step 5 — boolean fields
    @pytest.mark.parametrize("field", ["online", "is_online", "connected"])
    def test_step5_boolean_true(self, field):
        assert determine_online({field: True}) is True

    @pytest.mark.parametrize("field", ["online", "is_online", "connected"])
    def test_step5_boolean_false(self, field):
        assert determine_online({field: False}) is False

    # Step 6 — presence of `url`
    def test_step6_url_presence(self):
        assert determine_online({"url": "https://eero.example/x"}) is True

    def test_step6_empty_url_does_not_count(self):
        assert determine_online({"url": ""}) is False

    # Step 7 — fallthrough
    def test_step7_empty_dict_offline(self):
        assert determine_online({}) is False

    def test_step7_irrelevant_keys_offline(self):
        assert determine_online({"foo": "bar"}) is False

    # Envelope handling
    def test_works_through_data_envelope(self):
        assert determine_online({"data": {"status": "green"}}) is True
        assert determine_online({"data": {"status": "red"}}) is False

    # Robustness
    def test_non_dict_input(self):
        assert determine_online(None) is False
        assert determine_online("oops") is False
        assert determine_online(42) is False

    # Step ordering — internet.status overrides anything below it
    def test_step1_overrides_red_top_level(self):
        # internet says green, top-level says red → step 1 wins → True
        d = {"health": {"internet": {"status": "green"}}, "status": "red"}
        assert determine_online(d) is True

    # Step 2 takes precedence over later steps
    def test_step2_overrides_step5(self):
        d = {"health": {"internet": {"isp_up": False}}, "online": True}
        assert determine_online(d) is False


class TestExtractNetworkMetadata:
    def test_pulls_top_level_fields(self):
        meta = extract_network_metadata(
            {"name": "Lobby", "ssid": "Guest", "wan_ip": "1.2.3.4"}
        )
        assert meta == {"network_name": "Lobby", "ssid": "Guest", "wan_ip": "1.2.3.4"}

    def test_pulls_through_data_envelope(self):
        meta = extract_network_metadata({"data": {"name": "Lobby", "ssid": "Guest"}})
        assert meta["network_name"] == "Lobby"
        assert meta["ssid"] == "Guest"

    def test_wan_ip_from_ip_settings(self):
        meta = extract_network_metadata({"ip_settings": {"wan_ip": "10.0.0.1"}})
        assert meta == {"wan_ip": "10.0.0.1"}

    def test_wan_ip_from_dns(self):
        meta = extract_network_metadata({"dns": {"wan_ip": "10.0.0.2"}})
        assert meta == {"wan_ip": "10.0.0.2"}

    def test_top_level_wan_ip_wins_over_nested(self):
        meta = extract_network_metadata(
            {"wan_ip": "1.1.1.1", "ip_settings": {"wan_ip": "2.2.2.2"}}
        )
        assert meta["wan_ip"] == "1.1.1.1"

    def test_empty_input_empty_output(self):
        assert extract_network_metadata({}) == {}
        assert extract_network_metadata(None) == {}


class TestExtractDeviceList:
    def test_bare_array(self):
        out = extract_device_list([{"a": 1}, {"b": 2}])
        assert out == [{"a": 1}, {"b": 2}]

    def test_data_wrapped_array(self):
        out = extract_device_list({"data": [{"a": 1}]})
        assert out == [{"a": 1}]

    def test_filters_non_dicts(self):
        out = extract_device_list([{"a": 1}, "junk", None, [1, 2]])
        assert out == [{"a": 1}]

    def test_unrecognized_shape(self):
        assert extract_device_list({"foo": "bar"}) == []
        assert extract_device_list(None) == []


class TestBucketConnectedBySsid:
    def test_filters_to_connected_only(self):
        devices = [
            {"connected": True, "ssid": "A"},
            {"connected": False, "ssid": "A"},
            {"connected": True, "ssid": "B"},
        ]
        total, counts = bucket_connected_by_ssid(devices)
        assert total == 2
        assert counts == {"A": 1, "B": 1}

    def test_empty_ssid_bucketed_as_unknown(self):
        devices = [
            {"connected": True, "ssid": ""},
            {"connected": True},  # missing entirely
            {"connected": True, "ssid": None},
            {"connected": True, "ssid": "X"},
        ]
        total, counts = bucket_connected_by_ssid(devices)
        assert total == 4
        assert counts == {"Unknown SSID": 3, "X": 1}

    def test_no_connected_returns_zeros(self):
        devices = [{"connected": False, "ssid": "A"}, {"ssid": "B"}]
        total, counts = bucket_connected_by_ssid(devices)
        assert total == 0
        assert counts == {}


class TestDeviceEeroSerial:
    def test_extracts_from_source(self):
        assert device_eero_serial({"source": {"serial_number": "ABC-123"}}) == "ABC-123"

    def test_missing_source(self):
        assert device_eero_serial({}) is None

    def test_source_present_but_no_serial(self):
        assert device_eero_serial({"source": {"name": "x"}}) is None
