"""Native wake safety using a simulated RTC; never access the host RTC."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "rtc", Path(__file__).resolve().parents[1] / "custom_components/ecoflow_rtc/rtc.py"
)
rtc_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rtc_driver)
NativeRTC = rtc_driver.NativeRTC
RTCError = rtc_driver.RTCError

NOW = 1_795_000_000


class SimulatedRTC(NativeRTC):
    def __init__(self, root):
        super().__init__(root)
        self.alarm = None
        self.writes = []

    def _read_alarm(self):
        return self.alarm

    def _write_alarm(self, value):
        self.writes.append(value)
        self.alarm = value or None


@pytest.fixture
def rtc(tmp_path):
    (tmp_path / "name").write_text("rpi-rtc soc:rpi_rtc\n", encoding="ascii")
    (tmp_path / "since_epoch").write_text(str(NOW), encoding="ascii")
    with patch.object(rtc_driver.time, "time", return_value=NOW):
        yield SimulatedRTC(tmp_path)


def test_alarm_uses_configurable_minutes_and_is_read_back(rtc):
    assert rtc.schedule(15, None) == NOW + 900
    assert rtc.writes == [NOW + 900]
    assert rtc.schedule(30, NOW + 900) == NOW + 1800
    assert rtc.writes[-2:] == [0, NOW + 1800]


def test_foreign_alarm_is_neither_overwritten_nor_cancelled(rtc):
    rtc.alarm = NOW + 7200
    with pytest.raises(RTCError, match="another application"):
        rtc.schedule(15, NOW + 900)
    assert rtc.cancel(NOW + 900) is False
    assert rtc.writes == []
    assert rtc.alarm == NOW + 7200


def test_cancel_only_owned_alarm(rtc):
    assert rtc.cancel(None) is False
    deadline = rtc.schedule(15, None)
    assert rtc.cancel(deadline) is True
    assert rtc.alarm is None


@pytest.mark.parametrize("minutes", [True, 0, 4, 1441, 15.5, "15"])
def test_invalid_intervals_do_not_write(rtc, minutes):
    with pytest.raises(RTCError):
        rtc.schedule(minutes, None)
    assert rtc.writes == []


def test_wrong_driver_and_clock_drift_do_not_write(rtc):
    (rtc.root / "name").write_text("another-rtc\n", encoding="ascii")
    with pytest.raises(RTCError, match="native RTC driver"):
        rtc.schedule(15, None)
    (rtc.root / "name").write_text("rpi-rtc soc:rpi_rtc\n", encoding="ascii")
    (rtc.root / "since_epoch").write_text(str(NOW - 60), encoding="ascii")
    with pytest.raises(RTCError, match="differ"):
        rtc.schedule(15, None)
    assert rtc.writes == []


def test_failed_write_and_mismatched_readback_are_not_success(rtc):
    with patch.object(rtc, "_write_alarm", side_effect=PermissionError("read only")):
        with pytest.raises(RTCError, match="Cannot prepare"):
            rtc.schedule(15, None)
    with patch.object(rtc, "_write_alarm"):
        with pytest.raises(RTCError, match="readback"):
            rtc.schedule(15, None)
