"""Unit Converter — a general-purpose unit conversion tool for HA Assist.

Uses pint for real unit conversion (length, mass, volume, temperature,
speed, pressure, energy, etc — anything pint knows about), so it isn't
limited to a hand-maintained list like the kitchen/volume converter is.

v1.1: registering a plain `intent.IntentHandler` turned out NOT to be
enough to get this exposed to conversation agents. Confirmed by testing
directly against a live instance: with "Assist" checked as a Tool
Provider on the agent, and debug logging on the component, an obscure
conversion (47.3 nautical miles -> furlongs) produced zero log output
and a hallucinated wrong answer — the intent was registered (no setup
errors) but never actually invoked. Home Assistant's built-in Assist
API tool list does not automatically forward arbitrary custom-registered
intents; it only forwards a fixed built-in set plus entity-control
intents for exposed entities.

The fix is to register this as its own `llm.API` (the same mechanism
third-party tool packs like llm_intents use for their "Search Services"
/ "Basic Utilities" / etc groups) — that's what makes it show up as its
own checkbox under "Tool Providers" in a conversation agent's config,
separate from "Assist".

Install:
  1. Copy this custom_components/unit_converter folder into your HA
     config's custom_components/ directory.
  2. Add `unit_converter:` to configuration.yaml.
  3. Restart Home Assistant — HA will install the `pint` requirement
     automatically from manifest.json.
  4. In your conversation agent's Reconfigure screen, check the new
     "Unit Converter" box under Tool Providers.

Try it once installed by asking your agent something an LLM can't
reliably know off the top of its head, e.g. "convert 47.3 nautical
miles to furlongs" — should come back exact, not a guess.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent, llm
from homeassistant.util.json import JsonObjectType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "unit_converter"
INTENT_CONVERT_UNITS = "ConvertUnits"

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

TOOL_DESCRIPTION = (
    "Convert a numeric value from one unit to another. Supports length, "
    "mass/weight, volume, temperature, speed, time, pressure, energy, "
    "and most other physical units (e.g. mile, kilometer, km, meter, "
    "foot, inch, yard, pound, kilogram, gram, ounce, stone, celsius, "
    "fahrenheit, kelvin, liter, gallon, cup, mph, kph, m/s, psi, bar, "
    "joule, calorie, and many more, including common abbreviations). "
    "Use this for ANY unit conversion or arithmetic-adjacent unit "
    "question rather than computing it yourself — you are not reliable "
    "at arithmetic, this tool is."
)

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


def _convert(value: float, from_unit: str, to_unit: str):
    ureg = _get_registry()
    quantity = value * ureg(from_unit)
    return quantity.to(to_unit)


# --- Plain HA intent (kept for completeness / potential future sentence
#     triggers), though as noted above it is NOT what conversation agents
#     pick up as a tool. ---


class ConvertUnitsIntentHandler(intent.IntentHandler):
    """Handle ConvertUnits intents: {value, from_unit, to_unit} -> result."""

    intent_type = INTENT_CONVERT_UNITS
    description = TOOL_DESCRIPTION
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

        response = intent_obj.create_response()
        try:
            result = await hass.async_add_executor_job(
                _convert, value, from_unit, to_unit
            )
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


# --- LLM API / Tool: this is the part that actually shows up as a
#     "Tool Providers" checkbox for conversation agents. ---


class ConvertUnitsTool(llm.Tool):
    """The tool a conversation agent actually calls."""

    name = "ConvertUnits"
    description = TOOL_DESCRIPTION
    parameters = vol.Schema(
        {
            vol.Required("value"): vol.Coerce(float),
            vol.Required("from_unit"): cv.string,
            vol.Required("to_unit"): cv.string,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        value = tool_input.tool_args["value"]
        from_unit = tool_input.tool_args["from_unit"]
        to_unit = tool_input.tool_args["to_unit"]

        try:
            result = await hass.async_add_executor_job(
                _convert, value, from_unit, to_unit
            )
        except Exception as err:  # pint raises UndefinedUnitError / DimensionalityError / etc
            _LOGGER.debug("Unit conversion failed: %s", err)
            return {"error": str(err)}

        return {
            "value": round(result.magnitude, 6),
            "unit": to_unit,
            "input": f"{value} {from_unit}",
        }


class UnitConverterAPI(llm.API):
    """Registers the 'Unit Converter' entry under Tool Providers."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=DOMAIN, name="Unit Converter")

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        return llm.APIInstance(
            api=self,
            api_prompt=(
                "You have access to a ConvertUnits tool for exact unit "
                "conversion and unit-aware arithmetic. Always use it "
                "instead of computing conversions yourself."
            ),
            llm_context=llm_context,
            tools=[ConvertUnitsTool()],
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    intent.async_register(hass, ConvertUnitsIntentHandler())
    llm.async_register_api(hass, UnitConverterAPI(hass))
    _LOGGER.info(
        "Registered %s intent and Unit Converter LLM API", INTENT_CONVERT_UNITS
    )
    return True
