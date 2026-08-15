LMC Process Control Application
==============================

## General description
This repository contains a Python application for LMC (Liquid Metal Cooling) process control, designed to manage and monitor various processes efficiently. The application is structured to provide a user-friendly interface for controlling processes, with a focus on reliability and performance.

## Features
- Real-time process monitoring
- Process control and management
- Configurable settings for transport layer and application behavior
- Logging capabilities for tracking application activity and debugging

## PLC Control Button MQTT API
The app listens for button commands from UI/Node-RED and executes PLC logic using a state-driven controller.

### Command topics (UI -> app)
- `buttons/connect_to_plc`
	- Payload: optional JSON object, e.g. `{}`
	- Effect: Connect to PLC and move state to `connected_idle`.

- `buttons/start_process`
	- Payload: optional JSON object with speed control
	- Supported field: `speed_mm_per_sec` (float, clamped to `[5.0, 30.0]`)
	- Example: `{ "speed_mm_per_sec": 12.5 }`
	- Effect: Send process start command, run nominal checks, monitor gradient.

- `buttons/emergency_stop`
	- Payload: optional JSON object, e.g. `{}`
	- Effect: Immediate stop command and state transition to `emergency_stopped`.

### Feedback topics (app -> UI)
- `buttons/events`
	- Rich per-command/event response with result, message, state and optional details.

- `buttons/state`
	- Current controller state snapshot:
	- `state`: `disconnected|connected_idle|process_running|emergency_stopped`
	- `process_running`: boolean
	- `emergency_active`: boolean

### Process finish condition
While process is running, the app calculates thermal gradient from thermal couples.
When gradient reaches `60..80 K/cm`, the app sends finish command to PLC and returns to `connected_idle`.

## Modbus TCP Runbook (Short)
Use this order to run the PLC simulator and the LMC app with Modbus TCP.

1. Open terminal in project root:
	- `cd /home/volodymyr/Desktop/lmc_process_control_app`
2. Activate virtual environment:
	- `source lmc_venv/bin/activate`
3. Start PLC simulator first (Terminal A):
	- `python plc_simulator/simulations/plc_simulator.py`
4. Start LMC process control app second (Terminal B):
	- `python lmc_process_control.py`

### Notes
- The default Modbus TCP endpoint is `127.0.0.1:5020` (configured in `configs/tl_config.json`).
- If startup fails with "address already in use", check the port:
  - `ss -ltnp '( sport = :5020 )'`

### Stop Order
1. Stop the LMC app first (`Ctrl+C` in Terminal B).
2. Stop PLC simulator second (`Ctrl+C` in Terminal A).

