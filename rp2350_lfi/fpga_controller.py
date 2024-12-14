#!/usr/bin/env python3
"""Interface to the Gateware running in the the Glasgow board."""

import socket
import struct


class FpgaController:
    """Interface to the gateware running in the Glasgow board."""

    def __init__(self) -> None:
        """Create an interface to the Gateware."""
        self._s = socket.socket()
        self._s.connect(("127.0.0.1", 3334))

    def set_power(self, en: bool) -> None:
        if en:
            self._s.send(b"P")
        else:
            self._s.send(b"p")
        self._wait_ack()

    def set_bootsel(self, level: bool) -> None:
        if level:
            self._s.send(b"X")
        else:
            self._s.send(b"x")
        self._wait_ack()

    def set_run(self, level: bool) -> None:
        if level:
            self._s.send(b"u")
        else:
            self._s.send(b"r")
        self._wait_ack()

    def select_flash(self, index: int) -> None:
        if index == 0:
            self._s.send(b"f")
        else:
            self._s.send(b"F")
        self._wait_ack()

    def set_trigger_delay(self, delay: int) -> None:
        payload = b"D" + struct.pack("<H", delay)
        self._s.send(payload)
        self._wait_ack()

    def arm_glitch_engine(self) -> None:
        self._s.send(b"A")
        self._wait_ack()

    def cancel_glitch_engine(self) -> None:
        self._s.send(b"C")
        self._wait_ack()

    def wait_glitch_done(self, timeout: float = 1.0) -> None:
        self._s.settimeout(timeout)
        r = self._s.recv(1)
        if r != b"D":
            raise ValueError(f"Invalid value: 0x{r[0]:02x}")

    def wait_glitch_success(self, timeout: float = 0.5) -> None:
        self._s.settimeout(timeout)
        r = self._s.recv(1)
        if r != b"S":
            raise ValueError(f"Invalid value: 0x{r[0]:02x}")

    def wait_xip_success(self, timeout: float = 0.5) -> None:
        self._s.settimeout(timeout)
        r = self._s.recv(1)
        if r != b"X":
            raise ValueError(f"Invalid value: 0x{r[0]:02x}")

    def get_start_address(self) -> int:
        self._s.send(b"G")
        value = self._s.recv(1)[0]
        self._s.send(b"H")
        value |= self._s.recv(1)[0] << 8
        self._s.send(b"J")
        value |= self._s.recv(1)[0] << 16

        return value

    def get_max_address(self) -> int:
        self._s.send(b"v")
        value = self._s.recv(1)[0]
        self._s.send(b"V")
        value |= self._s.recv(1)[0] << 8
        self._s.send(b"W")
        value |= self._s.recv(1)[0] << 16

        return value

    def _wait_ack(self, timeout: float = 0.5) -> None:
        self._s.settimeout(timeout)
        r = self._s.recv(1)
        if r != b"A":
            raise ValueError(f"Invalid value: 0x{r[0]:02x}")
