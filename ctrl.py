#!/usr/bin/env python3
"""Main tool of the RP2350 Laser Fault Injection Project."""
import logging
import random
import time
from typing import Annotated

import typer
from requests import ConnectionError
from rich.logging import RichHandler

from rp2350_lfi import DeltaStage, FpgaController, LaserPulser

app = typer.Typer()

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
)


@app.command()
def set_power(en: bool) -> None:
    """Control the power supply of the target."""
    ctrl = FpgaController()
    ctrl.set_power(en)


@app.command()
def select_flash(index: int) -> None:
    """Select the QSPI flash used by the target."""
    ctrl = FpgaController()
    ctrl.select_flash(index)


@app.command()
def set_run(level: bool) -> None:
    """Set the RUN signal of the target."""
    ctrl = FpgaController()
    ctrl.set_run(level)


@app.command()
def set_bootsel(level: bool) -> None:
    """Set the BOOTSEL signal of the target."""
    ctrl = FpgaController()
    ctrl.set_bootsel(level)


@app.command()
def reset() -> None:
    """Reset the target."""
    ctrl = FpgaController()
    ctrl.set_run(False)
    time.sleep(0.1)
    ctrl.set_run(True)


@app.command()
def run_bootloader() -> None:
    """Run the bootloader of the target."""
    ctrl = FpgaController()

    ctrl.set_power(False)
    ctrl.set_bootsel(False)
    ctrl.set_run(False)

    time.sleep(0.1)

    ctrl.set_power(True)
    ctrl.set_run(True)

    time.sleep(0.1)

    ctrl.set_bootsel(True)


@app.command()
def attack(
    start_delay: Annotated[
        int, typer.Option(help="Minimum trigger delay (clock cycles)")
    ] = 60,
    end_delay: Annotated[
        int, typer.Option(help="Maximum trigger delay (clock cycles)")
    ] = 400,
    delay_step: Annotated[
        int, typer.Option(help="Trigger delay tuning step size (clock cycles)")
    ] = 1,
    n_retries: Annotated[
        int,
        typer.Option(
            help="Number of retries for a fixed set of configuration parameters"
        ),
    ] = 10,
    laser_voltage: Annotated[
        float, typer.Option(help="Voltage of the Pulser Circuit (Volts)")
    ] = 60,
    disable_laser: Annotated[bool, typer.Option(help="Disable the laser")] = False,
    success_timeout: Annotated[
        float,
        typer.Option(help="How long to wait for a possible glitch success (seconds)"),
    ] = 0.004,
    poweroff_duration: Annotated[
        float, typer.Option(help="How long to wait between retries (seconds)")
    ] = 0.001,
    walk_method: Annotated[
        bool, typer.Option(help="Randomly move the delta stage from time to time")
    ] = False,
    randomize_laser_power: Annotated[
        bool, typer.Option(help="Randomly change the power of the laser pulses")
    ] = False,
) -> None:
    """Attack the target."""
    if walk_method:
        try:
            delta_stage = DeltaStage()
        except ConnectionError:
            logging.error("Cannot connect to the delta stage")
            exit(-1)

    ctrl = FpgaController()

    if not disable_laser:
        laser_pulser = LaserPulser()
    else:
        logging.warning("Laser is disabled")

    logging.info("Preparing DUT")

    ctrl.set_power(False)
    ctrl.set_bootsel(True)
    ctrl.set_run(True)
    ctrl.cancel_glitch_engine()

    logging.info("DUT preparation done")

    if not disable_laser:
        logging.info(f"Enabling laser ({laser_voltage} V)")
        laser_pulser.set_supply_voltage(laser_voltage)
        laser_pulser.set_power(True)
        laser_pulser.set_driver_en(True)

    total_retry_count = 0
    n_events = 0
    previous_n_events = 0
    event_update = True

    try:
        while True:
            # Move the delta state in case the "walk" method is used
            # and a given number of successful glitch events have
            # previously been detected.
            if (
                walk_method
                and n_events != 0
                and (n_events - previous_n_events) >= 10
                and event_update
            ):
                position = delta_stage.get_position()
                max_delta = 4
                position = (
                    position[0] + random.randrange(-max_delta, max_delta + 1),
                    position[1] + random.randrange(-max_delta, max_delta + 1),
                    position[2],
                )
                logging.info(f"Moving delta stage to {position}")
                delta_stage.move_to(position)
                event_update = False
                previous_n_events = n_events

            # Note that iterating over various delay is possibly useless because of the
            # random delays inserted by the Boot ROM.
            for delay in range(start_delay, end_delay, delay_step):
                logging.info(f"Setting trigger delay to {delay} cycles")
                ctrl.set_trigger_delay(delay)

                if randomize_laser_power:
                    laser_voltage = random.randrange(
                        20, 51
                    )  # Hardcoded values determined empirically
                    logging.info(f"Setting laser voltage to {laser_voltage} V")
                    laser_pulser.set_supply_voltage(laser_voltage)

                # Multiple retries with the same laser and delay parameters
                for retry in range(n_retries):
                    logging.info(f"Attempt {retry + 1} / {n_retries}")
                    total_retry_count += 1

                    #
                    # ARM glitch engine and start the target
                    #
                    ctrl.arm_glitch_engine()
                    time.sleep(poweroff_duration)
                    ctrl.set_power(True)

                    #
                    # Wait for glitch engine to be done
                    #
                    try:
                        ctrl.wait_glitch_done()
                    except TimeoutError:
                        logging.error("Glitch engine has not triggered")
                        ctrl.cancel_glitch_engine()
                        ctrl.set_power(False)
                        continue

                    #
                    # Check for a possible glitch success.
                    # Here, a success is simply defined as a new QSPI read detected on the bus.
                    # This doesn't mean the attack is a success yet, but shows the laser pulse did
                    # something.
                    #
                    try:
                        ctrl.wait_glitch_success(timeout=success_timeout)
                        logging.info(
                            "Possible glitch success, another flash byte has been read."
                        )
                        n_events += 1
                        event_update = True
                    except TimeoutError:
                        ctrl.cancel_glitch_engine()
                        ctrl.set_power(False)
                        continue

                    #
                    # Next, check if data corresponding to the XIP custom firmware has been read
                    # If yes, it could mean this firmware is being executed.
                    #
                    try:
                        ctrl.wait_xip_success(timeout=1.0)
                        logging.info("XIP data has been read")

                        # Read the highest address accessed on the QSPI bus.
                        # Occasionally, the glitch forces weird unwanted behavior
                        # we can heuristically detect.
                        logging.info("Monitoring QSPI reads")
                        possible_attack_success = True
                        prev_max_address = 0
                        for _ in range(8):
                            max_address = ctrl.get_max_address()
                            logging.info(f"{max_address = :x}")

                            if (
                                max_address == 0xFFFFFE
                            ):  # The SHA-256 was computed over the entire SPI flash
                                logging.warning("Detected SHA-256 mega-loop")
                                possible_attack_success = False
                                break

                            if (
                                max_address == 0x13FE and prev_max_address == 0x13FE
                            ):  # Not sure what that is, but this common behavior isn't a success

                                logging.warning("Detected weird 0x13fe thing")
                                possible_attack_success = False
                                break

                            prev_max_address = max_address

                            time.sleep(5)

                        start_address = ctrl.get_start_address()
                        read_size = max_address - start_address + 1

                        if possible_attack_success:
                            logging.info(
                                "Detected a possible success, please check if a console is available"
                            )
                            input("Press enter to continue")

                    except TimeoutError:
                        logging.warning("XIP data has not been read")
                        start_address = ctrl.get_start_address()
                        max_address = ctrl.get_max_address()
                        logging.info(f"{start_address = :x}")
                        logging.info(f"{max_address = :x}")

                        read_size = max_address - start_address + 1

                    # More heuristics matching for interesting fault behaviors. They could indicate
                    # a "good" laser positioning. Pause the attack, so the situation can be assessed.
                    if (read_size == 0x13D8) or (max_address == 0x27AF):
                        logging.info("Interesting behavior detected, let's wait here")
                        input("...")

                    ctrl.cancel_glitch_engine()
                    ctrl.set_power(False)

            logging.info("Main loop iteration completed")

    except KeyboardInterrupt:
        logging.info(f"Interrupted after {total_retry_count} attempts")
        pass

    ctrl.cancel_glitch_engine()
    ctrl.set_power(False)

    if not disable_laser:
        laser_pulser.set_driver_en(False)
        laser_pulser.set_power(False)


if __name__ == "__main__":
    app()
