# BioMonitor Dashboard

BioMonitor Dashboard is a PySide6 desktop application for an educational Arduino Uno physiological monitoring system. It runs separate temperature, heart-rate/SpO2, and GSR tests, validates serial data, stores final results locally, and presents the complete measurement history.

## Features

- Modern dark medical dashboard UI
- Serial connection controls for Arduino Uno
- Commands: `TEMP`, `GSR`, `BPM`, `STOP`
- Separate timed tests with instructions and progress
- MAX30102 heart-rate, SpO2, and pulse-validity parsing
- Actionable Event Log messages for invalid measurements
- Locked pyqtgraph charts that show the complete stored history
- Fixed-size sample markers independent of chart zoom
- Persistent SQLite session storage
- CSV export including `bioscore` and status
- Medical Dark and High Contrast Dark themes
- Settings page for COM port, theme, and data folder

## Arduino Message Format

Serial speed: `115200` baud.

Supported single-value messages:

```text
TEMP:36.2
GSR:542
BPM:74,SPO2:97,PULSE_VALID:1,PULSE_TEMP:31.50
```

Malformed fields are rejected with a reason in the Event Log. When `PULSE_VALID:0`, the sample is not included in the final heart-rate result.

## Setup

Use Python 3.12 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

Run the automated checks:

```powershell
python -m pip install -e .[dev]
python -m unittest discover -s tests -v
python -m ruff check app tests run.py
python -m ruff format --check app tests run.py
```

## Project Structure

```text
app/
  main.py
  measurements.py
  models.py
  bioscore/
  charts/
  serial/
  settings/
  storage/
  ui/
    widgets/
```

The application separates measurement rules, serial communication, parsing, scoring, persistence, charting, and GUI code. One final result is stored for each completed test in `biomonitor.sqlite3`, so history remains available after restarting the app.
