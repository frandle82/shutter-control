# Shutter Control Blueprint for Home Assistant

This repository now distributes the upstream **Cover Control Automation (CCA)** blueprint so you can drive shutters and blinds directly via Home Assistant’s automation UI. All configuration happens through the blueprint’s built-in forms—no additional Python integration code is required.

## Features
- Ready-to-import blueprint with a comprehensive shutter/blind automation feature set (time windows, sun/brightness logic, ventilation, lockout protection, resident checks, and much more).
- Native Home Assistant UI for selecting cover entities and all related helpers/sensors the blueprint supports.
- Packaged release asset that bundles the blueprint for offline installation.

## Installation
1. In Home Assistant, navigate to **Settings → Automations & Scenes → Blueprints**.
2. Click **Import Blueprint** and paste the raw URL below:

   ```
   https://raw.githubusercontent.com/simatec/ioBroker.shuttercontrol/main/blueprints/automation/cover_control_automation.yaml
   ```

   Alternatively, download a tagged release asset from this repository and upload the `blueprints/automation/cover_control_automation.yaml` file manually.

3. Create a new automation from the imported blueprint and follow the UI prompts to configure your shutters, sensors, and schedules.

## Releases
When a tag is pushed, GitHub Actions builds a `shuttercontrol.zip` that contains the blueprint file plus this README and the license for easy distribution.

## Attribution
The blueprint is maintained by [hvorragend](https://github.com/hvorragend/ha-blueprints). Please consult the linked community thread and LICENSE inside the blueprint header for usage guidance and support links.
