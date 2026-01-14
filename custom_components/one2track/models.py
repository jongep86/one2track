"""Data models for One2Track integration."""

from __future__ import annotations

from dataclasses import dataclass

from .client import GpsClient
from .coordinator import One2TrackDataUpdateCoordinator


@dataclass
class One2TrackData:
    """Runtime data for One2Track integration."""

    client: GpsClient
    coordinator: One2TrackDataUpdateCoordinator
