# Shutter Control for Home Assistant

This repository provides a Home Assistant custom integration inspired by the ioBroker shuttercontrol adapter. It automates cover entities based on sunrise/sunset, optional presence, and weather protection.

## Features
- Multi-step config and options wizard that first selects shutter entities, maps them to flexible rooms, collects ioBroker-like defaults, and finally fine-tunes each cover.
- Per-cover sunrise/sunset offsets plus open/close target positions.
- Optional presence guard to keep shutters untouched when someone is home.
- Optional weather integration that raises shutters to a safer position when wind speeds exceed a configured limit.
- Optional window/door sensors prevent shutters from closing on open windows.
- Sensor entities expose the latest movement reason and target position for every configured shutter.
- Services to trigger manual moves or to recalculate scheduled callbacks after changing entities.
- **Bundled Home Assistant blueprint** mirroring the ioBroker shutter control behaviour for users who prefer automation-based setups.

## Installation
1. Copy the `custom_components/shuttercontrol` directory to your Home Assistant `custom_components` folder (or install via HACS by pointing to this repository).
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → Shutter Control**.
4. (Optional) Import the bundled blueprint via **Settings → Automations & Scenes → Blueprints → Import Blueprint** using the raw URL of `blueprints/automation/cover_control_automation.yaml` in this repository to drive shutters with the published automation.

### Testing releases
Tagged builds automatically publish a `shuttercontrol.zip` asset that can be downloaded from the GitHub release page. Extract the `custom_components` folder from the archive into your Home Assistant configuration directory to test a specific version. The release asset also bundles the original adapter logic from the `lib/` directory for reference while the Home Assistant port evolves.

## Configuration
The config flow mirrors the ioBroker wiki by walking through several screens:
1. **Select shutters/Jalousien** that should be automated.
2. **Assign rooms** so living, sleeping, or kids groupings are user-defined instead of fixed.
3. **Defaults** for open/close positions, sunrise/sunset offsets, presence guard, optional wind/weather safety, and manual override behaviour.
4. **Per-cover tuning** where you can override positions/offsets and map window or door sensors that should block closing.

All settings can be revisited via the integration options so you can adjust or extend the setup later.

## Services
- `shuttercontrol.recalculate_targets`: re-registers sunrise/sunset callbacks (helpful after changing entities).
- `shuttercontrol.move_covers`: immediately moves all configured covers. Provide `target: "open"` or `"close"`.

## Notes
The automation logic intentionally mirrors the most common workflows from the ioBroker adapter while staying native to Home Assistant. Further algorithm refinements—such as shading based on elevation or azimuth—can be added on top of this foundation.

## Blueprint

This repository ships the upstream `Cover Control Automation (CCA)` Home Assistant blueprint from [`hvorragend/ha-blueprints`](https://github.com/hvorragend/ha-blueprints/blob/main/blueprints/automation/cover_control_automation.yaml). If you prefer to orchestrate covers via a blueprint instead of the integration’s built-in automations, import it with the blueprint URL below or by pointing Home Assistant to the `blueprints/automation/cover_control_automation.yaml` file contained in tagged release assets.

```
https://raw.githubusercontent.com/simatec/ioBroker.shuttercontrol/main/blueprints/automation/cover_control_automation.yaml
```
