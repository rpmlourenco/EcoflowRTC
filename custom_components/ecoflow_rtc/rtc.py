"""Bounded access to the Raspberry Pi's native RTC, never the UPS RTC."""

import threading
import time
from pathlib import Path


class RTCError(Exception):
    """The native wake alarm could not be safely prepared."""


class NativeRTC:
    """Use only the fixed native Pi RTC and preserve other owners' alarms."""

    def __init__(self, root: Path = Path("/sys/class/rtc/rtc0")) -> None:
        self.root = root
        self._lock = threading.Lock()

    def _validate(self) -> None:
        if not (self.root / "name").read_text(encoding="ascii").startswith("rpi-rtc "):
            raise RTCError("The Raspberry Pi native RTC driver is required")
        rtc_time = int((self.root / "since_epoch").read_text(encoding="ascii"))
        if abs(rtc_time - time.time()) > 5:
            raise RTCError("Native RTC and system UTC differ by more than five seconds")

    def _read_alarm(self) -> int | None:
        value = (self.root / "wakealarm").read_text(encoding="ascii").strip()
        return int(value) if value else None

    def _write_alarm(self, value: int) -> None:
        (self.root / "wakealarm").write_text(f"{value}\n", encoding="ascii")

    def schedule(self, minutes: int, owned_alarm: int | None) -> int:
        """Arm and read back an absolute alarm; refuse a foreign alarm."""
        if type(minutes) is not int or not 5 <= minutes <= 1440:
            raise RTCError("Retry interval must be an integer from 5 to 1440 minutes")
        with self._lock:
            try:
                self._validate()
                current = self._read_alarm()
                if current is not None and current != owned_alarm:
                    raise RTCError("A native RTC alarm belongs to another application")
                deadline = int(time.time()) + minutes * 60
                if current is not None:
                    self._write_alarm(0)
                self._write_alarm(deadline)
                if self._read_alarm() != deadline:
                    raise RTCError("Native RTC alarm readback did not match")
                return deadline
            except (OSError, ValueError) as err:
                raise RTCError(f"Cannot prepare native RTC wake alarm: {err}") from err

    def cancel(self, owned_alarm: int | None) -> bool:
        """Clear only an alarm previously armed by this integration."""
        if owned_alarm is None:
            return False
        with self._lock:
            try:
                self._validate()
                if self._read_alarm() != owned_alarm:
                    return False
                self._write_alarm(0)
                if self._read_alarm() is not None:
                    raise RTCError("Native RTC alarm could not be cleared")
                return True
            except (OSError, ValueError) as err:
                raise RTCError(f"Cannot cancel native RTC wake alarm: {err}") from err
