"""The One2Track integration."""

from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import GpsClient, get_client
from .client.client_types import AuthenticationError, One2TrackConfig
from .const import CONF_ACCOUNT_ID, CONF_PASSWORD, CONF_USERNAME, DEFAULT_UPDATE_RATE_MIN, DOMAIN, LOGGER
from .coordinator import One2TrackDataUpdateCoordinator
from .exceptions import One2TrackAuthenticationError
from .models import One2TrackData

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up One2Track from a config entry."""
    LOGGER.debug("Setting up One2Track integration for entry: %s", entry.entry_id)

    # Create API client configuration
    config = One2TrackConfig(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        id=entry.data[CONF_ACCOUNT_ID],
    )

    # Get shared aiohttp session
    session = async_get_clientsession(hass)

    # Create API client with session
    client = GpsClient(config, session)

    try:
        # Verify credentials and get account ID
        account_id = await client.install()

        # Verify account ID matches configuration
        if account_id != entry.data[CONF_ACCOUNT_ID]:
            LOGGER.error(
                "Account ID mismatch: expected %s, got %s",
                entry.data[CONF_ACCOUNT_ID],
                account_id,
            )
            raise ConfigEntryNotReady("Account ID verification failed")

    except AuthenticationError as err:
        LOGGER.error("Authentication failed during setup: %s", err)
        raise ConfigEntryAuthFailed("Invalid credentials") from err
    except One2TrackAuthenticationError as err:
        LOGGER.error("One2Track authentication error: %s", err)
        raise ConfigEntryAuthFailed from err
    except ClientError as err:
        LOGGER.error("Network error during setup: %s", err)
        raise ConfigEntryNotReady("Unable to connect to One2Track API") from err
    except Exception as err:
        LOGGER.exception("Unexpected error during setup")
        raise ConfigEntryNotReady(f"Unexpected error: {err}") from err

    # Create coordinator
    coordinator = One2TrackDataUpdateCoordinator(
        hass=hass,
        client=client,
        update_interval=timedelta(minutes=DEFAULT_UPDATE_RATE_MIN),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = One2TrackData(
        client=client,
        coordinator=coordinator,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register reload listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    LOGGER.info("One2Track integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading One2Track integration for entry: %s", entry.entry_id)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Shutdown coordinator and close client session
        runtime_data: One2TrackData = entry.runtime_data
        await runtime_data.coordinator.async_shutdown()
        LOGGER.info("One2Track integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    LOGGER.debug("Reloading One2Track integration for entry: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
