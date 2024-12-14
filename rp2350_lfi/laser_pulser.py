#!/usr/bin/env python3
"""Driver for the laser pulser board."""

from enum import IntEnum

from .cypress_usb import CypressI2cDataConfig, CypressUSB


class _LaserPulserGpio(IntEnum):
    """Laser pulser board GPIOs."""

    POWER_EN = 1
    DRIVER_EN = 2
    PULSE = 5


class LaserPulser:
    """Driver for the laser pulser board."""

    def __init__(self) -> None:
        """Create a drive instance."""
        self._usb = CypressUSB()

    def set_power(self, en: bool) -> None:
        """Set the value of the POWER_EN signal."""
        self._usb.gpio_set(_LaserPulserGpio.POWER_EN, en)

    def set_driver_en(self, en: bool) -> None:
        """Enable or disable the switch driver."""
        self._usb.gpio_set(_LaserPulserGpio.DRIVER_EN, not en)

    def pulse(self) -> None:
        """Send a laser pulse."""
        self._usb.gpio_set(_LaserPulserGpio.PULSE, True)
        self._usb.gpio_set(_LaserPulserGpio.PULSE, False)

    def _set_potentiometer_step(self, step: int) -> None:
        config = CypressI2cDataConfig(
            slave_address=0b0101110, is_stop_bit=True, is_nak_bit=False
        )
        self._usb.i2c_write(config, bytes([0, step]))

    def set_supply_voltage(self, voltage: float) -> None:
        """Set the capacitor bank voltage value.

        Args:
            voltage (float): The voltage, expressed in V.
        """
        vref = 1.2  # V
        rhigh = 619  # kOhms
        rlow = 10  # kOhms
        rpot = 100  # kOhms

        step = int(127 * (rhigh / (voltage / vref - 1) - rlow) / rpot)

        step = max(0, min(127, step))

        self._set_potentiometer_step(step)
