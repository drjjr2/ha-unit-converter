"""Unit Converter — a general-purpose ConvertUnits intent for HA Assist.

Uses pint for real unit conversion (length, mass, volume, temperature,
speed, pressure, energy, etc — anything pint knows about), so it isn't
limited to a hand-maintained list like the kitchen/volume converter is.

Install:
  1. Copy this custom_components/unit_converter folder into your HA
     config's custom_components/ directory.
  2. Add `unit_converter:` to configuration.yaml.
  3. Restart Home Assistant — HA will install the `pint` requirement
     automatically from manifest.json.
  4. In your conversation agent's configuration, check whether there's
     a toggle for native HA intents/"Control Home Assistant" tools
     (distinct from the llm_intents "Basic Utilities" group) and make
     sure it's enabled — that's what exposes this intent to the LLM.
     If you don't see this intent show up as a callable tool, that's
     the first thing to check.

Try it once installed with:
  Developer Tools -> Actions -> conversation.process
    text: "how many kilometers in 5 miles"
or directly:
  Developer Tools -> Actions -> intent.  (there's no direct intent-call
    service in core HA; easiest is via conversation.process, or by
    asking your Assist agent once the tool is enabled)
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent

_LOGGER = logging.getLogger(__name__)

DOMAIN = "unit_converter"
INTENT_CONVERT_UNITS = "ConvertUnits"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

_UREG = None


def _get_registry():
    """Lazily create the pint UnitRegistry (import + construction are
    both a little slow, so do this once off the event loop, not at
    import time)."""
    global _UREG
    if _UREG is None:
        import pint

        _UREG = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    return _UREG


class ConvertUnitsIntentHandler(intent.IntentHandler):
    """Handle ConvertUnits intents: {value, from_unit, to_unit} -> result."""

    intent_type = INTENT_CONVERT_UNITS
    description = (
        "Convert a numeric value from one unit to another. Supports length, "
        "mass/weight, volume, temperature, speed, time, pressure, energy, "
        "and most other physical units (e.g. mile, kilometer, km, meter, "
        "foot, inch, yard, pound, kilogram, gram, ounce, stone, celsius, "
        "fahrenheit, kelvin, liter, gallon, cup, mph, kph, m/s, psi, bar, "
        "joule, calorie, and many more, including common abbreviations). "
        "Use this for ANY unit conversion question rather than computing "
        "it yourself."
    )
    slot_schema = {
        vol.Required("value"): vol.Coerce(float),
        vol.Required("from_unit"): cv.string,
        vol.Required("to_unit"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        value = slots["value"]["value"]
        from_unit = slots["from_unit"]["value"]
        to_unit = slots["to_unit"]["value"]

        def _convert():
            ureg = _get_registry()
            quantity = value * ureg(from_unit)
            return quantity.to(to_unit)

        response = intent_obj.create_response()
        try:
            result = await hass.async_add_executor_job(_convert)
        except Exception as err:  # pint raises UndefinedUnitError / DimensionalityError / etc
            _LOGGER.debug("Unit conversion failed: %s", err)
            response.async_set_speech(
                f"I couldn't convert {from_unit} to {to_unit}: {err}"
            )
            response.async_set_speech_slots({"error": str(err)})
            return response

        magnitude = round(result.magnitude, 6)
        response.async_set_speech(f"{value} {from_unit} is {magnitude} {to_unit}")
        response.async_set_speech_slots({"value": magnitude, "unit": to_unit})
        return response


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    intent.async_register(hass, ConvertUnitsIntentHandler())
    _LOGGER.info("Registered %s intent", INTENT_CONVERT_UNITS)
    return True
