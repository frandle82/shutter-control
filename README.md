# Shutter Control for Home Assistant

This custom integration packages the inputs and algorithms from the **Cover Control Automation (CCA)** blueprint as a dedicated Home Assistant integration. Configure your shutters with a guided setup flow, then let the integration handle time-based opening/closing, brightness and sun elevation guards, ventilation lockout, wind protection, and shading thresholds inspired by the blueprint.

## Features
- Multi-step config/options flow that mirrors the blueprint inputs (cover selection, timers, brightness & sun thresholds, shading and safety sensors).
- Per-cover runtime controller that evaluates CCA-style conditions every minute and on sensor changes.
- Datapoint sensors that expose the latest commanded target position, reason, and manual override window.
- Service to pause automation for a cover for a configurable number of minutes (manual override).

## Installation
1. Copy the `custom_components/shuttercontrol` folder into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for **Shutter Control**, and follow the step-by-step wizard to select covers, define time windows, and supply optional sensors for brightness, sun, ventilation, wind, and temperature.
4. Adjust any values later via the integration's **Configure** options dialog. The same fields stay editable after setup.

## Services
- `shuttercontrol.set_manual_override`: pause automatic control for a selected cover for the configured duration.

## Releases
Tagged releases ship a zip containing this integration source so you can install without Git. The underlying blueprint remains in `blueprints/automation/cover_control_automation.yaml` for reference to the original logic.

## Attribution
Algorithms and inputs are based on the [Cover Control Automation (CCA) blueprint](https://github.com/hvorragend/ha-blueprints/blob/main/blueprints/automation/cover_control_automation.yaml). Many thanks to the original author for the comprehensive feature set.
