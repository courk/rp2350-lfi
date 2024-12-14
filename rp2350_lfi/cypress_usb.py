#!/usr/bin/env python3
"""Wrapper around the compiled cyusbserial library."""

import platform
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from cffi import FFI


class CypressUSBError(Exception):
    """Base CypressUSB exception class."""

    pass


@dataclass
class CypressI2cConfig:
    """Cypress I2C configuration data."""

    frequency: int
    slave_address: int
    is_master: bool
    is_clock_stretch: bool


@dataclass
class CypressI2cDataConfig:
    """Cypress I2C transfer configuration data."""

    slave_address: int
    is_stop_bit: bool
    is_nak_bit: bool


class CypressUSB:
    """Manage the Cypress USB-to-serial converter of the Validation Board."""

    VID = 0x04B4
    PID = 0x0004

    def __init__(self):
        """Create CypressUSB object."""
        self._ffi = FFI()

        if platform.system() == "Linux":
            cdef = "typedef bool BOOL;"
        else:
            cdef = "typedef int BOOL;"

        c_def = Path(__file__).parent.joinpath("./assets/cypress_usb.h")

        with c_def.open("r") as f:
            cdef += "\n" + f.read()

        self._ffi.cdef(cdef)

        self._lib = self._ffi.dlopen("/usr/local/lib/libcyusbserial.so.1")

        if self._lib is None:
            raise CypressUSBError("Cannot load cyusbserial")

        if platform.system() == "Linux":
            ret = self._lib.CyLibraryInit()
            if ret != self._lib.CY_SUCCESS:
                raise CypressUSBError(self._get_error_txt(ret))

        # Find target device
        n_devices_ptr = self._ffi.new("unsigned char *")
        device_info_ptr = self._ffi.new("CY_DEVICE_INFO *")

        ret = self._lib.CyGetListofDevices(n_devices_ptr)
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

        target_index = None
        for n in range(n_devices_ptr[0]):
            ret = self._lib.CyGetDeviceInfo(n, device_info_ptr)
            if ret not in [self._lib.CY_SUCCESS, self._lib.CY_ERROR_ACCESS_DENIED]:
                raise CypressUSBError(self._get_error_txt(ret))

            vid = device_info_ptr[0].vidPid.vid
            pid = device_info_ptr[0].vidPid.pid

            if (vid, pid) == (self.VID, self.PID):
                target_index = n
                break

        if target_index is None:
            raise CypressUSBError("Device not found")

        # Open target device
        handle_ptr = self._ffi.new("CY_HANDLE *")
        for _ in range(
            3
        ):  # Retry more than one time is sometimes needed (kernel detach bug ?)
            ret = self._lib.CyOpen(target_index, 0, handle_ptr)
            if ret == self._lib.CY_SUCCESS:
                break
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))
        self._handle = handle_ptr[0]

        self._lock = Lock()

        # Reset I2C
        self.i2c_reset()

    def gpio_set(self, gpio: int, value: bool) -> None:
        """Set the level of a give GPIO.

        Args:
            gpio (int): The index of the GPIO to control.
            value (bool): True to set the GPIO high, False to set it low.
        """
        with self._lock:
            ret = self._lib.CySetGpioValue(self._handle, gpio, int(value))
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

    def i2c_get_config(self) -> CypressI2cConfig:
        cfg = self._ffi.new("CY_I2C_CONFIG *")
        with self._lock:
            ret = self._lib.CyGetI2cConfig(self._handle, cfg)
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

        return CypressI2cConfig(
            frequency=cfg.frequency,
            slave_address=cfg.slaveAddress,
            is_master=cfg.isMaster,
            is_clock_stretch=cfg.isClockStretch,
        )

    def i2c_set_config(self, config: CypressI2cConfig) -> None:
        cfg = self._ffi.new("CY_I2C_CONFIG *")

        cfg.frequency = config.frequency
        cfg.slaveAddress = config.slave_address
        cfg.isMaster = config.is_master
        cfg.isClockStretch = config.is_clock_stretch

        with self._lock:
            ret = self._lib.CySetI2cConfig(self._handle, cfg)
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

    def i2c_write(
        self, config: CypressI2cDataConfig, data: bytes, timeout: float = 1.0
    ) -> None:
        cfg = self._ffi.new(
            "CY_I2C_DATA_CONFIG *",
            (config.slave_address, config.is_stop_bit, config.is_nak_bit),
        )

        wlen = len(data)
        wbuf = self._ffi.new("UCHAR[%d]" % wlen, bytes(data))
        wcdb = self._ffi.new("CY_DATA_BUFFER *", (wbuf, wlen, 0))

        with self._lock:
            ret = self._lib.CyI2cWrite(self._handle, cfg, wcdb, int(timeout * 1000))
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

    def i2c_read(
        self, config: CypressI2cDataConfig, size: int, timeout: float = 1.0
    ) -> bytes:
        cfg = self._ffi.new(
            "CY_I2C_DATA_CONFIG *",
            (config.slave_address, config.is_stop_bit, config.is_nak_bit),
        )

        rlen = size
        rbuf = self._ffi.new("UCHAR[%d]" % rlen)
        rcdb = self._ffi.new("CY_DATA_BUFFER *", (rbuf, rlen, 0))

        with self._lock:
            ret = self._lib.CyI2cRead(self._handle, cfg, rcdb, int(timeout * 1000))
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

        buf = self._ffi.buffer(rbuf, rlen)
        return bytes(buf)

    def i2c_reset(self) -> None:
        with self._lock:
            for n in (0, 1):
                ret = self._lib.CyI2cReset(self._handle, n)
                if ret != self._lib.CY_SUCCESS:
                    raise CypressUSBError(self._get_error_txt(ret))

    def reset(self) -> None:
        """Reset the Cypress device."""
        with self._lock:
            ret = self._lib.CyResetDevice(self._handle)
        if ret != self._lib.CY_SUCCESS:
            raise CypressUSBError(self._get_error_txt(ret))

    def _get_error_txt(self, code: int) -> str:
        """Get human readable error string."""
        errors = self._ffi.typeof("CY_RETURN_STATUS").relements
        for txt in errors:
            if code == errors[txt]:
                return txt
        return "Unknown"

    def close(self) -> None:
        """Close the cypress device (and return control to the kernel driver)."""
        if hasattr(self, "_handle"):
            self._lib.CyClose(self._handle)
            delattr(self, "_handle")
        if platform.system() == "Linux":
            self._lib.CyLibraryExit()

    def __del__(self):
        """Close the handle and exit the cyusbserial library cleanly."""
        self.close()
