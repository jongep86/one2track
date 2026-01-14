"""Config flow for One2Track integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .client import One2TrackConfig, get_client
from .client.client_types import AuthenticationError
from .const import CONF_ACCOUNT_ID, DEFAULT_PREFIX, DOMAIN, LOGGER


class One2TrackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for One2Track."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._prefix = DEFAULT_PREFIX

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate credentials by attempting to get account ID
                account_id = await self._async_validate_credentials(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                LOGGER.info("One2Track GPS: Found account: %s", account_id)

                # Add account ID to user input
                user_input[CONF_ACCOUNT_ID] = account_id

                # Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()

                # Create config entry
                return self.async_create_entry(
                    title=f"{user_input[CONF_USERNAME]}/{account_id}",
                    data=user_input,
                )

            except AuthenticationError:
                LOGGER.warning("Authentication failed for user: %s", user_input.get(CONF_USERNAME))
                errors["base"] = "invalid_auth"
            except Exception as err:
                LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"

        # Show form (initial or with errors)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )

    async def _async_validate_credentials(
        self, username: str, password: str
    ) -> str:
        """Validate credentials and return account ID."""
        config = One2TrackConfig(username=username, password=password)
        client = get_client(config)

        try:
            account_id = await client.install()
            return account_id
        finally:
            # Clean up client session
            await client.close()
