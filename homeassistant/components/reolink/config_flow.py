"""Config flow for the Reolink camera component."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from reolink_aio.exceptions import ApiError, CredentialsInvalidError, ReolinkError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DEFAULT_PROTOCOL, DOMAIN
from .exceptions import ReolinkException, UserNotAdmin
from .host import ReolinkHost

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {CONF_PROTOCOL: DEFAULT_PROTOCOL}


class ReolinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry):
        """Initialize ReolinkOptionsFlowHandler."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Reolink options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL,
                        default=self.config_entry.options[CONF_PROTOCOL],
                    ): vol.In(["rtsp", "rtmp", "flv"]),
                }
            ),
        )


class ReolinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._username: str = "admin"
        self._password: str | None = None
        self._reauth: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ReolinkOptionsFlowHandler:
        """Options callback for Reolink."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an authentication error or no admin privileges."""
        self._host = entry_data[CONF_HOST]
        self._username = entry_data[CONF_USERNAME]
        self._password = entry_data[CONF_PASSWORD]
        self._reauth = True
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        placeholders = {"error": ""}

        if user_input is not None:
            host = ReolinkHost(self.hass, user_input, DEFAULT_OPTIONS)
            try:
                await host.async_init()
            except UserNotAdmin:
                errors[CONF_USERNAME] = "not_admin"
                placeholders["username"] = host.api.username
                placeholders["userlevel"] = host.api.user_level
            except CredentialsInvalidError:
                errors[CONF_HOST] = "invalid_auth"
            except ApiError as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "api_error"
            except (ReolinkError, ReolinkException) as err:
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                placeholders["error"] = str(err)
                errors[CONF_HOST] = "unknown"
            finally:
                await host.stop()

            if not errors:
                user_input[CONF_PORT] = host.api.port
                user_input[CONF_USE_HTTPS] = host.api.use_https

                existing_entry = await self.async_set_unique_id(
                    host.unique_id, raise_on_progress=False
                )
                if existing_entry and self._reauth:
                    if self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    ):
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured(updates=user_input)

                return self.async_create_entry(
                    title=str(host.api.nvr_name),
                    data=user_input,
                    options=DEFAULT_OPTIONS,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self._username): str,
                vol.Required(CONF_PASSWORD, default=self._password): str,
                vol.Required(CONF_HOST, default=self._host): str,
            }
        )
        if errors:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_PORT): cv.positive_int,
                    vol.Optional(CONF_USE_HTTPS): bool,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=placeholders,
        )
