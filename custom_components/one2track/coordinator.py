"""DataUpdateCoordinator for One2Track integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import GpsClient
from .client.client_types import AuthenticationError, TrackerDevice
from .const import DOMAIN, LOGGER
from .exceptions import One2TrackApiError, One2TrackAuthenticationError

if TYPE_CHECKING:
    from .client.client_types import TrackerDevice


class One2TrackDataUpdateCoordinator(DataUpdateCoordinator[list[TrackerDevice]]):
    """Class to manage fetching One2Track data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: GpsClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> list[TrackerDevice]:
        """Fetch data from One2Track API."""
        try:
            devices = await self.client.update()

            if devices is None:
                raise UpdateFailed("No data received from One2Track API")

            LOGGER.debug("Successfully updated %s devices", len(devices))
            return devices

        except AuthenticationError as err:
            # Authentication errors require user intervention (re-login)
            LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed(
                "Invalid credentials or session expired. Please reconfigure the integration."
            ) from err
        except One2TrackAuthenticationError as err:
            LOGGER.error("One2Track authentication error: %s", err)
            raise ConfigEntryAuthFailed from err
        except One2TrackApiError as err:
            LOGGER.error("One2Track API error: %s", err)
            raise UpdateFailed(f"Error communicating with One2Track API: {err}") from err
        except Exception as err:
            LOGGER.exception("Unexpected error fetching One2Track data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and close client session."""
        await self.client.close()
