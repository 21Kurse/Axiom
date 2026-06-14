#include <Servo.h>
#include <ArduinoJson.h>

Servo socketServo;
const int servoPin = 9;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    // Wait for serial port to connect
  }
  
  // Attach servo to Digital Pin D9
  socketServo.attach(servoPin);
  
  // Initialize to 0 degrees
  socketServo.write(0);
  
  Serial.println("Axiom Prosthetics Socket - Vertical Slice Demo Ready");
}

void loop() {
  if (Serial.available()) {
    String jsonLine = Serial.readStringUntil('\n');
    
    // Allocate a JSON document
    // 200 bytes is plenty for {"cell_id": "03", "target_kpa": 8.0}
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, jsonLine);

    if (error) {
      Serial.print("JSON Parse Failed: ");
      Serial.println(error.c_str());
      return;
    }

    const char* cell_id = doc["cell_id"];
    float target_kpa = doc["target_kpa"];

    // Constrain kPa between 0 and 15
    if (target_kpa < 0.0) target_kpa = 0.0;
    if (target_kpa > 15.0) target_kpa = 15.0;
    
    // Map 0-15 kPa to 0-180 degrees
    int target_angle = map(target_kpa * 10, 0, 150, 0, 180);

    Serial.print("Adjusting cell ");
    Serial.print(cell_id);
    Serial.print(" to ");
    Serial.print(target_kpa);
    Serial.print(" kPa -> Angle ");
    Serial.println(target_angle);
    
    // Physically simulate tightening the socket
    socketServo.write(target_angle);
    
    // Provide a 200ms delay between commands
    delay(200);
  }
}
