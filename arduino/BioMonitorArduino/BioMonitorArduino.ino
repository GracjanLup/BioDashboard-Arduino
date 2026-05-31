/*
  BioMonitor Dashboard - Arduino Uno firmware

  Hardware:
    DS18B20 temperature sensor -> D2
    GSR sensor                 -> A0
    DFRobot SEN0344 MAX30102   -> I2C, SDA A4, SCL A5

  Supported serial commands:
    TEMP  - stream temperature only
    GSR   - stream galvanic skin response only
    BPM   - stream heart rate / SpO2 only
    ALL   - stream all enabled sensors
    STOP  - stop streaming

  Required libraries:
    OneWire
    DallasTemperature
    DFRobot_BloodOxygen_S
    DFRobot_RTU
*/

#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "DFRobot_BloodOxygen_S.h"

enum Mode {
  MODE_STOP,
  MODE_TEMP,
  MODE_GSR,
  MODE_BPM,
  MODE_ALL
};

const unsigned long BAUD_RATE = 115200;

const unsigned long TEMP_GSR_INTERVAL_MS = 1000;
const unsigned long PULSE_UPDATE_INTERVAL_MS = 4000;

// Pins
const int DS18B20_PIN = 2;
const int GSR_PIN = A0;

const uint8_t MAX30102_I2C_ADDRESS = 0x57;

const bool DEMO_MODE = false;

OneWire oneWire(DS18B20_PIN);
DallasTemperature tempSensor(&oneWire);

DFRobot_BloodOxygen_S_I2C pulseSensor(&Wire, MAX30102_I2C_ADDRESS);

bool pulseSensorReady = false;

int lastBpm = -1;
int lastSpo2 = -1;
float lastPulseBoardTemp = -127.0;
bool pulseValid = false;

unsigned long lastPulseUpdateAt = 0;


Mode currentMode = MODE_STOP;
unsigned long lastStreamAt = 0;
String inputBuffer = "";


void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(GSR_PIN, INPUT);

  Wire.begin();
  tempSensor.begin();

  setupPulseSensor();

  Serial.println("BioMonitor ready");
  Serial.println("Commands: TEMP, GSR, BPM, ALL, STOP");
}


void loop() {
  readSerialCommand();

  updatePulseSensorIfNeeded();

  if (currentMode == MODE_STOP) {
    return;
  }

  unsigned long now = millis();

  if (now - lastStreamAt < TEMP_GSR_INTERVAL_MS) {
    return;
  }

  lastStreamAt = now;
  streamCurrentMode();
}

void setupPulseSensor() {
  if (DEMO_MODE) {
    pulseSensorReady = true;
    return;
  }

  if (pulseSensor.begin()) {
    pulseSensorReady = true;
    pulseSensor.sensorStartCollect();
    Serial.println("MAX30102:READY");
  } else {
    pulseSensorReady = false;
    Serial.println("ERROR:MAX30102_INIT_FAIL");
  }
}

void readSerialCommand() {
  while (Serial.available() > 0) {
    char character = (char)Serial.read();

    if (character == '\n' || character == '\r') {
      inputBuffer.trim();

      if (inputBuffer.length() > 0) {
        setMode(inputBuffer);
      }

      inputBuffer = "";
      continue;
    }

    inputBuffer += character;

    if (inputBuffer.length() > 24) {
      inputBuffer = "";
    }
  }
}

void setMode(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "TEMP") {
    currentMode = MODE_TEMP;
    Serial.println("MODE:TEMP");
  }
  else if (command == "GSR") {
    currentMode = MODE_GSR;
    Serial.println("MODE:GSR");
  }
  else if (command == "BPM") {
    currentMode = MODE_BPM;
    Serial.println("MODE:BPM");
  }
  else if (command == "ALL") {
    currentMode = MODE_ALL;
    Serial.println("MODE:ALL");
  }
  else if (command == "STOP") {
    currentMode = MODE_STOP;
    Serial.println("MODE:STOP");
  }
  else {
    Serial.print("ERROR:UNKNOWN_COMMAND:");
    Serial.println(command);
  }

  lastStreamAt = 0;
}

void streamCurrentMode() {
  if (currentMode == MODE_TEMP) {
    streamTemperatureOnly();
    return;
  }

  if (currentMode == MODE_GSR) {
    streamGsrOnly();
    return;
  }

  if (currentMode == MODE_BPM) {
    streamPulseOnly();
    return;
  }

  if (currentMode == MODE_ALL) {
    streamAllSensors();
    return;
  }
}

void streamTemperatureOnly() {
  Serial.print("TEMP:");
  Serial.println(readTemperatureC(), 2);
}

void streamGsrOnly() {
  Serial.print("GSR:");
  Serial.println(readGsrRaw());
}

void streamPulseOnly() {
  if (!pulseSensorReady && !DEMO_MODE) {
    Serial.println("ERROR:MAX30102_NOT_READY");
    return;
  }

  Serial.print("BPM:");
  Serial.print(pulseValid ? lastBpm : 0);

  Serial.print(",SPO2:");
  Serial.print(lastSpo2);

  Serial.print(",PULSE_VALID:");
  Serial.print(pulseValid ? 1 : 0);

  Serial.print(",PULSE_TEMP:");
  Serial.println(lastPulseBoardTemp, 2);
}

void streamAllSensors() {
  Serial.print("BPM:");
  Serial.print(pulseValid ? lastBpm : 0);

  Serial.print(",SPO2:");
  Serial.print(lastSpo2);

  Serial.print(",PULSE_VALID:");
  Serial.print(pulseValid ? 1 : 0);

  Serial.print(",TEMP:");
  Serial.print(readTemperatureC(), 2);

  Serial.print(",GSR:");
  Serial.print(readGsrRaw());

  Serial.print(",PULSE_TEMP:");
  Serial.println(lastPulseBoardTemp, 2);
}

float readTemperatureC() {
  if (DEMO_MODE) {
    return 36.2 + 0.4 * sin(millis() / 8000.0);
  }

  tempSensor.requestTemperatures();

  float tempC = tempSensor.getTempCByIndex(0);

  if (tempC == DEVICE_DISCONNECTED_C) {
    return -127.0;
  }

  return tempC;
}

int readGsrRaw() {
  if (DEMO_MODE) {
    return 520 + (int)(60.0 * sin(millis() / 5000.0));
  }

  return analogRead(GSR_PIN);
}

void updatePulseSensorIfNeeded() {
  if (!pulseSensorReady && !DEMO_MODE) {
    return;
  }

  unsigned long now = millis();

  if (now - lastPulseUpdateAt < PULSE_UPDATE_INTERVAL_MS) {
    return;
  }

  lastPulseUpdateAt = now;

  if (DEMO_MODE) {
    lastBpm = 74 + (int)(4.0 * sin(millis() / 6000.0));
    lastSpo2 = 97;
    lastPulseBoardTemp = 31.5;
    pulseValid = true;
    return;
  }

  pulseSensor.getHeartbeatSPO2();

  int bpm = pulseSensor._sHeartbeatSPO2.Heartbeat;
  int spo2 = pulseSensor._sHeartbeatSPO2.SPO2;

  lastPulseBoardTemp = pulseSensor.getTemperature_C();

  if (bpm > 30 && bpm < 220) {
    lastBpm = bpm;
  }

  if (spo2 >= 70 && spo2 <= 100) {
    lastSpo2 = spo2;
  } else {
    lastSpo2 = -1;
  }

  pulseValid = (bpm > 30 && bpm < 220);
}