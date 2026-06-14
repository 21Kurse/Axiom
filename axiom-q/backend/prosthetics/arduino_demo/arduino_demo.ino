// QVis Prosthetic — Dual Potentiometer Serial Bridge
// =====================================================
// Pot 1 (A0): "Limb-Shift" knob — drives drift magnitude in the backend.
//             Value 0–1023 maps to [0, 1] → pot_value in telemetry.inject_drift().
//             Crossing the backend threshold (default 0.30) fires a full cycle.
//
// Pot 2 (A1): "Comfort-Target" knob — defines what "comfortable" pressure
//             means for the patient. Instead of a hardcoded 8–12 kPa target,
//             this knob dynamically adjusts the pressure baseline.
//             Value 0–1023 maps to [0, 1] → target range in telemetry.py.
//
// Output format: "pot1,pot2\n" at ~30 Hz, 9600 baud, 8N1.
// Each line contains two comma-separated integers (0–1023).
//
// Wiring:
//   Pot 1: 5V → outer lug, GND → outer lug, A0 → wiper
//   Pot 2: 5V → outer lug, GND → outer lug, A1 → wiper
//
// Upload: Arduino IDE → Board "Arduino Uno" → Upload
// Verify: Serial Monitor at 9600 baud → "512,340\n" lines scrolling.

void setup() {
  Serial.begin(9600);
  // Small settling delay so the serial port is ready before the host
  // starts requesting data (especially on Windows COM port open).
  delay(500);
}

void loop() {
  int pot1 = analogRead(A0);  // 0–1023, limb-shift drift
  int pot2 = analogRead(A1);  // 0–1023, comfort-target baseline

  Serial.print(pot1);
  Serial.print(",");
  Serial.println(pot2);

  delay(33);  // ~30 Hz sample rate
}
