"""Device tracker platform for One2Track integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .entity import One2TrackEntity

if TYPE_CHECKING:
    from .client.client_types import TrackerDevice
    from .models import One2TrackData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track device tracker from a config entry."""
    LOGGER.debug("Setting up One2Track device tracker platform")

    runtime_data: One2TrackData = entry.runtime_data
    coordinator = runtime_data.coordinator

    # Wait for first update to complete
    if not coordinator.data:
        LOGGER.warning("No data available from coordinator yet")
        return

    # Create tracker entities for all devices
    entities = [
        One2TrackDeviceTracker(coordinator, device["uuid"])
        for device in coordinator.data
    ]

    LOGGER.info("Adding %s One2Track device tracker(s)", len(entities))
    async_add_entities(entities, update_before_add=False)


class One2TrackDeviceTracker(One2TrackEntity, TrackerEntity):
    """Representation of a One2Track device tracker."""

    _attr_icon = "mdi:watch-variant"

    def __init__(self, coordinator, device_uuid: str) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, device_uuid)

        # Set entity name from initial device data
        device = self._get_device_data()
        if device:
            self._attr_name = device.get("name", f"Device {device_uuid[:8]}")

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        device = self._get_device_data()
        if device and device.get("last_location", {}).get("location_type") == "WIFI":
            return SourceType.ROUTER
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        device = self._get_device_data()
        if device and "last_location" in device:
            lat = device["last_location"].get("latitude")
            if lat is not None:
                return float(lat)
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        device = self._get_device_data()
        if device and "last_location" in device:
            lon = device["last_location"].get("longitude")
            if lon is not None:
                return float(lon)
        return None

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy in meters."""
        device = self._get_device_data()
        if device and "last_location" in device:
            signal = device["last_location"].get("signal_strength", 0)
            # Better signal = better accuracy
            # Signal strength is typically 0-100, map to accuracy in meters
            if signal > 80:
                return 5
            if signal > 50:
                return 10
            if signal > 20:
                return 20
        return 50  # Default accuracy

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        device = self._get_device_data()
        if device and "last_location" in device:
            return device["last_location"].get("battery_percentage")
        return None

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        device = self._get_device_data()
        if not device:
            return None

        # If connected to WIFI, assume home
        if device.get("last_location", {}).get("location_type") == "WIFI":
            return "home"

        # Check if in a defined zone
        if self.latitude and self.longitude:
            try:
                zone = async_active_zone(
                    self.hass, self.latitude, self.longitude, radius=0
                )
                if zone:
                    return zone.name
            except Exception as err:
                LOGGER.error("Error getting zone for tracker: %s", err)

        # Fallback to address from API
        return device.get("last_location", {}).get("address")

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return device specific attributes."""
        device = self._get_device_data()
        if not device:
            return {}

        last_location = device.get("last_location", {})
        simcard = device.get("simcard", {})

        return {
            "device_id": device.get("id"),
            "serial_number": device.get("serial_number"),
            "uuid": device.get("uuid"),
            "name": device.get("name"),
            "status": device.get("status"),
            "phone_number": device.get("phone_number"),
            "tariff_type": simcard.get("tariff_type"),
            "balance_cents": simcard.get("balance_cents"),
            "last_communication": last_location.get("last_communication"),
            "last_location_update": last_location.get("last_location_update"),
            "altitude": last_location.get("altitude"),
            "location_type": last_location.get("location_type"),
            "address": last_location.get("address"),
            "signal_strength": last_location.get("signal_strength"),
            "satellite_count": last_location.get("satellite_count"),
            "host": last_location.get("host"),
            "port": last_location.get("port"),
            "speed": last_location.get("speed"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get fresh device data
        device = self._get_device_data()

        if device is None:
            LOGGER.warning(
                "Device %s not found in coordinator data", self._device_uuid
            )
            return

        # Update entity name if it changed
        new_name = device.get("name")
        if new_name and new_name != self._attr_name:
            self._attr_name = new_name

        # Write state to Home Assistant
        self.async_write_ha_state()
