#!/usr/bin/env python3
"""Delta Stage controller."""
import time
from typing import Tuple

import requests


class DeltaStage:
    """Delta stage controller."""

    def __init__(self, host: str = "10.1.10.131") -> None:
        """Create an interface to the Delta Stage API.

        Args:
            host (str, optional): The hostname of the Delta Stage. Defaults to "10.1.10.131".
        """
        self._host = host

    def get_position(self) -> Tuple[int, int, int]:
        r = requests.get(
            f"http://{self._host}:5000/api/v2/instrument/state/stage/position"
        )
        r.raise_for_status()
        ret = r.json()

        return (ret["x"], ret["y"], ret["z"])

    def move_to(self, xyz: Tuple[int, int, int]) -> None:
        payload = {"absolute": True, "z": xyz[2], "x": xyz[0], "y": xyz[1]}

        url = f"http://{self._host}:5000/api/v2/actions/stage/move/"

        r = requests.post(url, json=payload)
        r.raise_for_status()

        # Wait for completion
        time.sleep(0.8)
        self.get_position()

    def take_picture(self, filename: str) -> None:
        payload = {
            "use_video_port": False,
            "temporary": False,
            "filename": filename,
            "bayer": False,
            "tags": ["scan"],
            "annotations": {"Client": "SwaggerUI"},
        }

        url = f"http://{self._host}:5000/api/v2/actions/camera/capture/"

        r = requests.post(url, json=payload)
        r.raise_for_status()
