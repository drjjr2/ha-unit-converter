# Unit Converter for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/drjjr2/ha-unit-converter/actions/workflows/validate.yaml/badge.svg)](https://github.com/drjjr2/ha-unit-converter/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A general-purpose `ConvertUnits` intent for Home Assistant Assist, backed by
[pint](https://pint.readthedocs.io/) — the standard Python unit library.

Unlike hand-maintained "kitchen unit converter" style tools that only cover a
fixed list (volume, say), this exposes real conversion across length, mass,
volume, temperature, speed, pressure, energy, time, and most other physical
units pint knows about, including common abbreviations (`km`, `mi`, `kg`,
`lb`, `°C`, `°F`, ...).

It's aimed at LLM-backed conversation agents (local or cloud) that are prone
to getting arithmetic/unit conversion wrong on their own — the model still
decides *what* to convert, but the actual math is delegated to pint instead
of the model's own arithmetic.

## Why

Small (and not-so-small) LLMs are unreliable at arithmetic. Giving a
conversation agent a real conversion tool to call, instead of asking it to
compute the answer itself, turns "close enough" into an exact answer. This
was built after a local Qwen3-8B agent got `840ml → cups` wrong, and then
invented a wrong answer for `1 mile → km` after a kitchen-only conversion
tool rejected units it doesn't cover.

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/drjjr2/ha-unit-converter` as an Integration.
3. Install "Unit Converter", restart Home Assistant.

### Manual

Copy `custom_components/unit_converter` into your Home Assistant
`custom_components/` directory and restart.

## Setup

Add to `configuration.yaml`:

```yaml
unit_converter:
```

Restart Home Assistant. The `pint` dependency is installed automatically from
the integration's manifest.

## Exposing it to a conversation agent

This integration registers a standard Home Assistant intent
(`ConvertUnits`), so it's picked up the same way built-in intents are by any
conversation agent that uses HA's Assist API tool list. Depending on the
agent integration you're using, you may need to explicitly enable "native HA
intents" or "Control Home Assistant" tools in its configuration — check its
options if the tool doesn't show up as available after restart.

## Usage

Once exposed to your agent, ask things like:

- "How many kilometers is 5 miles?"
- "Convert 840 ml to cups"
- "What's 72 fahrenheit in celsius?"
- "How many pounds is 40 kilograms?"

The intent takes three slots — `value` (number), `from_unit`, `to_unit` — and
returns the converted value using pint's real unit registry, so it also
correctly rejects nonsensical conversions (e.g. converting a length to a
weight) instead of guessing.

## Development

```bash
git clone https://github.com/drjjr2/ha-unit-converter
cd ha-unit-converter
python -m venv .venv && source .venv/bin/activate
pip install pint homeassistant
```

CI runs [hassfest](https://developers.home-assistant.io/docs/creating_integration_manifest/#hassfest)
and [HACS validation](https://github.com/hacs/action) on every push/PR.

## License

MIT — see [LICENSE](LICENSE).
