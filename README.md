# Shutter Control for Home Assistant

This repository provides a Home Assistant custom integration inspired by the ioBroker shuttercontrol adapter. It automates cover entities based on sunrise/sunset, optional presence, and weather protection.

## Features
- Config flow UI for global defaults and per-cover tuning.
- Per-cover sunrise/sunset offsets plus open/close target positions.
- Optional presence guard to keep shutters untouched when someone is home.
- Optional weather integration that raises shutters to a safer position when wind speeds exceed a configured limit.
- Services to trigger manual moves or to recalculate scheduled callbacks after changing entities.

## Installation
1. Copy the `custom_components/shuttercontrol` directory to your Home Assistant `custom_components` folder (or install via HACS by pointing to this repository).
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → Shutter Control**.

### Testing releases
Tagged builds automatically publish a `shuttercontrol.zip` asset that can be downloaded from the GitHub release page. Extract the `custom_components` folder from the archive into your Home Assistant configuration directory to test a specific version. The release asset also bundles the original adapter logic from the `lib/` directory for reference while the Home Assistant port evolves.

## Configuration
The config flow collects:
- **Default open/close positions** used when no per-cover override is provided.
- **Sunrise/Sunset offsets (minutes)** to adjust when shutters move.
- Optional **presence sensor**, **weather entity**, and **wind speed limit** to pause or adapt movements.
- At least one **cover entity** with optional custom positions and offsets.

After setup, revisit the integration options to add more covers or update automation guards.

## Services
- `shuttercontrol.recalculate_targets`: re-registers sunrise/sunset callbacks (helpful after changing entities).
- `shuttercontrol.move_covers`: immediately moves all configured covers. Provide `target: "open"` or `"close"`.

## Notes
The automation logic intentionally mirrors the most common workflows from the ioBroker adapter while staying native to Home Assistant. Further algorithm refinements—such as shading based on elevation or azimuth—can be added on top of this foundation.
