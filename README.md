# RP2350 Laser Fault Injection

## Overview

This repository contains software written in the context of the [RP2350 Hacking Challenge](https://github.com/raspberrypi/rp2350_hacking_challenge).

Refer to [Laser Fault Injection on a Budget: RP2350 Edition](https://courk.cc/rp2350-challenge-laser) for more context and technical details.

## Prerequisites

The following tools and dependencies are expected to be installed:

- A valid _ARM_ toolchain
- [`libcyusbserial`](https://github.com/cyrozap/libcyusbserial)
- [Poetry](https://python-poetry.org/)
- [pipx](https://pipx.pypa.io/latest/)

## Installation

My fork of [Glasgow](https://github.com/GlasgowEmbedded/Glasgow) can be installed with the following command:

```bash
pipx install -e "glasgow/software[builtin-toolchain]"
```

Other tools can be installed with `poetry`.

```bash
poetry install
```

## Usage

### Glasgow Configuration

Running `./configure_glasgow.py` will configure the _Glasgow Interface Explorer_.

### Flash Images Generation

The content of both _QSPI_ flash components located in the _I/O Board_ can be generated using the `binary-patcher` tool. Refer to the [section detailing this work](https://courk.cc/rp2350-challenge-laser#flash-memory-organization) for details regarding how this content is generated.

In the following sequence of commands, the `vanilla.bin` file represents the image of an authentic signed firmware. In the context of this challenge, such an image can be obtained by dumping it from the target _Pico 2_ board.

```bash
# Generate both QSPI flash images
poetry run binary-patcher --vanilla-binary vanilla.bin \
                          --flash-0 flash0.bin \
                          --flash-1 flash1.bin \
                          --signature-block-address $((0x13D8)) # Offset obtained by studying the vanilla.bin image

# Configure the electronic to use the first flash, and run the bootloader
poetry run ctrl set-power false
poetry run ctrl select-flash 0
poetry run ctrl run-bootloader

# Flash the first flash
picotool load -v flash0.bin -o 0x10000000

# Configure the electronic to use the second flash, and run the bootloader
poetry run ctrl set-power false
poetry run ctrl select-flash 1
poetry run ctrl run-bootloader

# Flash the first flash
picotool load -v flash1.bin -o 0x10000000

# Write the arbitrary firmware, assumed to have been built already
picotool load -v arbitrary_firmware/build/firmware.bin -o 0x10010000

poetry run ctrl set-power false
```

### Attack Loop

Running `poetry run ctrl attack` starts the process detailed in the [relevant section of the article detailing this project](https://courk.cc/rp2350-challenge-laser#attack-loop).

```
poetry run ctrl attack --help

 Usage: ctrl attack [OPTIONS]

 Attack the target.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --start-delay                                            INTEGER  Minimum trigger delay (clock cycles) [default: 60]    │
│ --end-delay                                              INTEGER  Maximum trigger delay (clock cycles) [default: 400]   │
│ --delay-step                                             INTEGER  Trigger delay tuning step size (clock cycles)         │
│                                                                   [default: 1]                                          │
│ --n-retries                                              INTEGER  Number of retries for a fixed set of configuration    │
│                                                                   parameters                                            │
│                                                                   [default: 10]                                         │
│ --laser-voltage                                          FLOAT    Voltage of the Pulser Circuit (Volts) [default: 60]   │
│ --disable-laser            --no-disable-laser                     Disable the laser [default: no-disable-laser]         │
│ --success-timeout                                        FLOAT    How long to wait for a possible glitch success        │
│                                                                   (seconds)                                             │
│                                                                   [default: 0.004]                                      │
│ --poweroff-duration                                      FLOAT    How long to wait between retries (seconds)            │
│                                                                   [default: 0.001]                                      │
│ --walk-method              --no-walk-method                       Randomly move the delta stage from time to time       │
│                                                                   [default: no-walk-method]                             │
│ --randomize-laser-power    --no-randomize-laser-power             Randomly change the power of the laser pulses         │
│                                                                   [default: no-randomize-laser-power]                   │
│ --help                                                            Show this message and exit.                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```