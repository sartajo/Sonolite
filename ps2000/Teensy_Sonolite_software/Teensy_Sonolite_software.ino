
// This program is designed to run on a TEENSY 4.0
// Uses Miuzei 9g micro servo
// Power via 5v, PWM is driven by pin 9
// Must upload this code to teensy prior to using Sonolite software
// This software is responsible for driving the servo full 180 degrees and offerening smooth control options.
// Authored by Omar Sartaj

#include <Servo.h>

Servo scanServo;

const int SERVO_PIN = 9;

int currentAngle = 0;
const int minAngle = 0;
const int maxAngle = 180;

void setup()
{
  Serial.begin(115200);
  delay(2000);

  scanServo.attach(SERVO_PIN);
  scanServo.write(currentAngle);
  delay(500);

  Serial.println("READY");
  Serial.print("ANGLE ");
  Serial.println(currentAngle);
}

void loop()
{
  if (Serial.available())
  {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("STEP "))
    {
      int step = cmd.substring(5).toInt();

      int nextAngle = currentAngle + step;

      // 🔁 wrap-around logic
      if (nextAngle > maxAngle)
      {
        Serial.println("AT MAX - returning to 0 after delay...");
        delay(1000);  // ✅ 1 second pause before reset

        // smooth return (optional but nicer)
        for (int a = currentAngle; a >= minAngle; a -= 2)
        {
          scanServo.write(a);
          delay(10);
        }

        currentAngle = minAngle;
      }
      else
      {
        currentAngle = nextAngle;
        scanServo.write(currentAngle);
        delay(300);
      }

      Serial.print("DONE ");
      Serial.println(currentAngle);
    }
    else if (cmd == "HOME")
    {
      currentAngle = minAngle;
      scanServo.write(currentAngle);
      delay(300);

      Serial.print("DONE ");
      Serial.println(currentAngle);
    }
    else if (cmd == "GET")
    {
      Serial.print("ANGLE ");
      Serial.println(currentAngle);
    }
    else
    {
      Serial.println("ERR");
    }
  }
}
