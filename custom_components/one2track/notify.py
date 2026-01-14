"""Notification service for One2Track integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .client import One2TrackConfig, get_client
from .client.client_types import AuthenticationError
from .const import DOMAIN, LOGGER

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_get_service(
    hass: HomeAssistant, config: dict[str, Any], discovery_info: dict[str, Any] | None = None
) -> One2TrackNotificationService:
    """Get the One2Track notification service."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    # Try to get shared client from existing config entries
    shared_client = None

    # Look through config entries for runtime_data
    if DOMAIN in hass.data:
        # Try to get the first config entry's client
        for entry_id in hass.data[DOMAIN]:
            entry_data = hass.data[DOMAIN].get(entry_id)
            if hasattr(entry_data, "client"):
                shared_client = entry_data.client
                LOGGER.debug("Using shared client from config entry: %s", entry_id)
                break

    return One2TrackNotificationService(hass, username, password, shared_client)


class One2TrackNotificationService(BaseNotificationService):
    """Implementation of the notification service for One2Track."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        shared_client: Any = None,
    ) -> None:
        """Initialize the service."""
        self.hass = hass
        self.username = username
        self.password = password
        self._owns_client = shared_client is None

        if shared_client:
            self._client = shared_client
            LOGGER.debug("Notification service using shared client")
        else:
            config = One2TrackConfig(username=username, password=password)
            self._client = get_client(config)
            LOGGER.debug("Notification service created its own client")

        self._stop_unsub = None

        # Only register cleanup if we own the client
        if self._owns_client:
            self._stop_unsub = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_close_client
            )

    async def _async_close_client(self, _event: Any) -> None:
        """Close the underlying aiohttp session when hass stops."""
        if self._client and hasattr(self._client, "close"):
            await self._client.close()
            LOGGER.debug("Closed notification service client")

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the One2Track device."""
        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA) or {}

        device_id = data.get("device_id")

        # If no device_id provided, try to find one from device tracker entities
        if not device_id:
            for entity_id in self.hass.states.async_entity_ids("device_tracker"):
                if "one2track" in entity_id:
                    state = self.hass.states.get(entity_id)
                    if state and state.attributes.get("device_id"):
                        device_id = state.attributes.get("device_id")
                        LOGGER.debug(
                            "Auto-detected device_id from %s: %s", entity_id, device_id
                        )
                        break

        if not device_id:
            LOGGER.error(
                "No device_id provided and could not auto-detect from One2Track device trackers. "
                "Please specify device_id in the service data field."
            )
            return

        LOGGER.debug("Sending message to One2Track device %s: %s", device_id, message)

        try:
            await self._client.send_device_message(device_id, message, title)
            LOGGER.info("Message sent successfully to One2Track device %s", device_id)
        except AuthenticationError as err:
            LOGGER.error(
                "Authentication error sending message to device %s: %s", device_id, err
            )
        except Exception as err:
            LOGGER.exception(
                "Unexpected error sending message to One2Track device %s", device_id
            )
