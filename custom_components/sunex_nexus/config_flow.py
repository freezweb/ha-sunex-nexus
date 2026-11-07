"""Explicit local configuration; never scan a network or write during setup."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import CONF_ALLOW_WRITES, CONF_EXCLUSIVE, CONF_INTERVAL, DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN
from .coordinator import read_snapshot
from .protocol import NexusTransport, ProtocolError


class NexusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip(".").lower()
            port = user_input[CONF_PORT]
            if not user_input[CONF_EXCLUSIVE]:
                errors["base"] = "exclusive_required"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                transport = None
                try:
                    transport = NexusTransport(host, port)
                    await read_snapshot(transport)
                except (ProtocolError, OSError, ValueError):
                    errors["base"] = "cannot_connect"
                finally:
                    if transport:
                        await transport.close()
                if not errors:
                    return self.async_create_entry(title="SUNEX NEXUS", data={CONF_HOST: host, CONF_PORT: port})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(CONF_EXCLUSIVE, default=False): bool,
        }), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NexusOptionsFlow()


class NexusOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_ALLOW_WRITES, default=self.config_entry.options.get(CONF_ALLOW_WRITES, False)): bool,
            vol.Required(CONF_INTERVAL, default=self.config_entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=15, max=60)),
        }))
