# BioMonitor Dashboard

BioMonitor Dashboard is a PySide6 desktop application for an educational Arduino Uno physiological monitoring system. It reads serial messages from the Arduino, parses temperature, heart-rate, and GSR data, calculates baseline-relative deltas, and visualizes everything in real time.

## Features

- Modern dark medical dashboard UI
- Serial connection controls for Arduino Uno
- Commands: `TEMP`, `GSR`, `BPM`, `ALL`, `STOP`
- MAX30102 heart-rate, SpO2, pulse-validity, and GSR parsing
- Robust parser for single and combined serial messages
- Real-time pyqtgraph charts with timestamp axes
- Last 5 minutes of live chart history by default
- Baseline calibration workflow
- Physiological status mapping based on baseline-relative sensor deviations
- Persistent SQLite session storage
- CSV export with `timestamp`, `temperature`, `heart_rate`, `spo2`, `pulse_valid`, `pulse_temperature`, `gsr`, `status`
- HTML session report export
- Settings page for COM port, baud rate, sampling interval, theme, chart history, and data folder

## Arduino Message Format

Serial speed: `115200` baud.

Supported single-value messages:

```text
TEMP:36.2
GSR:542
BPM:74,SPO2:97,PULSE_VALID:1,PULSE_TEMP:31.50
```

Supported combined message:

```text
BPM:74,SPO2:97,PULSE_VALID:1,TEMP:35.82,GSR:542,PULSE_TEMP:31.50
```

Malformed fields are ignored. A line is accepted when at least one supported field is valid.
When `PULSE_VALID:0`, the dashboard ignores the BPM value but still accepts other fields, such as `GSR`.
See `PROTOCOL.md` for the full protocol.

## Setup

Use Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

## Project Structure

```text
app/
  main.py
  models.py
  bioscore/
  charts/
  serial/
  settings/
  storage/
  ui/
    widgets/
```

The application separates serial communication, parsing, scoring, persistence, charting, and GUI code so new sensors or Arduino commands can be added without coupling them to the main window.
Samples are saved in `biomonitor.sqlite3` inside the configured data folder, so history remains available after closing and reopening the app.
