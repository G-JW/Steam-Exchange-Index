from __future__ import annotations

import copy
from pathlib import Path

import pytest

from src.config import load_config


@pytest.fixture
def config() -> dict:
    return copy.deepcopy(load_config(Path(__file__).parents[1] / "config.yaml"))

