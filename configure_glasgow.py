#!/home/courk/.local/share/pipx/venvs/glasgow/bin/python

import argparse
import asyncio
import logging

from glasgow.access.direct import (
    DirectArguments,
    DirectDemultiplexer,
    DirectMultiplexer,
)
from glasgow.applet import GlasgowApplet, GlasgowAppletError
from glasgow.applet.interface.rp2350_lfi import Rp2350LfiApplet
from glasgow.device.hardware import GlasgowHardwareDevice
from glasgow.target.hardware import GlasgowHardwareTarget

logger = logging.getLogger(__loader__.name)
logger.setLevel(logging.INFO)


def pinargs(x):
    r = []
    for k in x.keys():
        r.append(f"--pin-{k}")
        r.append(str(x[k]))
    return r


async def _main():
    device = GlasgowHardwareDevice()

    io_level = 3.3  # V

    rp2350_pins = {
        "run": 2,
        "power-en": 3,
        "qspi-ss": 4,  # also bootsel
        "qspi-clk": 8,  # B0
        "qspi-d0": 9,  # B1
        "qspi-d1": 10,  # B2
        "qspi-d2": 11,  # B3
        "qspi-d3": 12,  # B4
        "flash-ss1": 5,
        "flash-ss2": 6,
        "laser": 13,  # B5
    }

    ctrl_endpoint = "tcp::3334"

    logger.info(f"{ctrl_endpoint = }")

    await device.reset_alert("AB")
    await device.poll_alert()
    await device.set_voltage("AB", io_level)

    target = GlasgowHardwareTarget(
        revision=device.revision, multiplexer_cls=DirectMultiplexer, with_analyzer=False
    )

    access_args = DirectArguments(applet_name="rp2350", default_port="AB", pin_count=16)

    rp2350_parser = argparse.ArgumentParser("rp2350-backside-rev2")

    Rp2350LfiApplet.add_build_arguments(rp2350_parser, access_args)

    Rp2350LfiApplet.add_run_arguments(rp2350_parser, access_args)

    Rp2350LfiApplet.add_interact_arguments(rp2350_parser)

    voltsarg = ["-V", str(io_level)]

    rp2350_args = rp2350_parser.parse_args(
        voltsarg + pinargs(rp2350_pins) + [ctrl_endpoint]
    )

    rp2350 = Rp2350LfiApplet()

    rp2350.build(target, rp2350_args)

    plan = target.build_plan()

    await device.download_target(plan)

    device.demultiplexer = DirectDemultiplexer(device, target.multiplexer.pipe_count)

    async def run_applet(applet: GlasgowApplet, args):
        try:
            iface = await applet.run(device, args)
            return await applet.interact(device, args, iface)
        except GlasgowAppletError as e:
            applet.logger.error(str(e))
            return 1
        except asyncio.CancelledError:
            return 130  # 128 + SIGINT
        finally:
            await device.demultiplexer.flush()
            device.demultiplexer.statistics()

    tasks = [
        asyncio.ensure_future(run_applet(rp2350, rp2350_args)),
    ]

    logger.info("Running")

    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()

    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)


def main():
    root_logger = logging.getLogger()
    term_handler = logging.StreamHandler()
    root_logger.addHandler(term_handler)
    exit(asyncio.new_event_loop().run_until_complete(_main()))


if __name__ == "__main__":
    main()
