"""Base entity for One2Track integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import One2TrackDataUpdateCoordinator


class One2TrackEntity(CoordinatorEntity[One2TrackDataUpdateCoordinator]):
    """Base One2Track entity with common device_info and attributes."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: One2TrackDataUpdateCoordinator,
        device_uuid: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_uuid = device_uuid
        self._attr_unique_id = device_uuid

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this One2Track device."""
        device = self._get_device_data()

        if device is None:
            # Fallback device info if device not found
            return DeviceInfo(
                identifiers={(DOMAIN, self._device_uuid)},
                name=f"One2Track Device {self._device_uuid[:8]}",
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_uuid)},
            name=device.get("name", "Unknown"),
            manufacturer="One2Track",
            model="GPS Watch",
            serial_number=device.get("serial_number"),
            sw_version=None,  # API doesn't provide firmware version
        )

    def _get_device_data(self) -> dict | None:
        """Get device data from coordinator by UUID."""
        if not self.coordinator.data:
            return None

        for device in self.coordinator.data:
            if device.get("uuid") == self._device_uuid:
                return device

        return None
