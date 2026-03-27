#include <Servo.h>

Servo ultrasoundServo;

const int servoPin = 9;

unsigned long lastInputTime = 0;
const unsigned long timeout = 10000; // 3 seconds

int currentAngle = 0;

void setup() {
  ultrasoundServo.attach(servoPin);
  Serial.begin(9600);

  ultrasoundServo.write(0);  // start at 0
  delay(1000);

  Serial.println("Enter angles (0–180). Will return to 0 after inactivity.");
}

void loop() {

  // 🔹 Read input
  if (Serial.available() > 0) {

    int inputAngle = Serial.parseInt();

    if (inputAngle >= 0 && inputAngle <= 180) {
      currentAngle = inputAngle;
      ultrasoundServo.write(currentAngle);

      Serial.print("Moved to: ");
      Serial.println(currentAngle);

      lastInputTime = millis();  // reset timer
    }

    // clear buffer
    while (Serial.available() > 0) {
      Serial.read();
    }
  }

  // 🔹 Check timeout
  if (millis() - lastInputTime > timeout && currentAngle != 0) {
    ultrasoundServo.write(0);
    currentAngle = 0;

    Serial.println("Returning to 0 (timeout)");
  }
}
