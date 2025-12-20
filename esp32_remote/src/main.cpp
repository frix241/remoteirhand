#include <Arduino.h>
#include <IRremote.hpp>

// --- Configuration ---
const int IR_SEND_PIN = 4; // Update this to your IR LED pin
// Note: IRremote library might have specific pins for specific boards. 
// For ESP32, you can often specify the pin in the send function or init.

// --- IR Codes (Samsung TV Example) ---
// Replace these with your TV's codes!
// You can find codes online or use an IR Receiver sketch to read your remote.
const uint32_t CODE_POWER = 0xE0E040BF;
const uint32_t CODE_MUTE = 0xE0E0F00F;
const uint32_t CODE_VOL_UP = 0xE0E0E01F;
const uint32_t CODE_VOL_DOWN = 0xE0E0D02F;
const uint32_t CODE_CH_NEXT = 0xE0E048B7;
const uint32_t CODE_CH_PREV = 0xE0E008F7;
const uint32_t CODE_SOURCE = 0xE0E0807F;

// Using Samsung Protocol by default. Change 'sendSamsung' to your TV's protocol.
// Common: sendNEC, sendSony, sendLG, etc.

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32 IR Remote Ready");
  
  // Initialize IR Sender
  IrSender.begin(IR_SEND_PIN);

  // Initialize Built-in LED
  pinMode(2, OUTPUT); // Pin 2 is usually the built-in LED on ESP32 Dev Boards
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    Serial.print("Received command: ");
    Serial.println(command);

    // Blink LED to indicate command received
    digitalWrite(2, HIGH);

    switch (command) {
      case 'P': // Power
        IrSender.sendSamsung(0xE0E0, 0x40BF, 0); 
        Serial.println("Sent: POWER");
        break;
      case 'M': // Mute
        IrSender.sendSamsung(0xE0E0, 0xF00F, 0);
        Serial.println("Sent: MUTE");
        break;
      case 'U': // Vol Up
        IrSender.sendSamsung(0xE0E0, 0xE01F, 0);
        Serial.println("Sent: VOL UP");
        break;
      case 'D': // Vol Down
        IrSender.sendSamsung(0xE0E0, 0xD02F, 0);
        Serial.println("Sent: VOL DOWN");
        break;
      case 'N': // Ch Next
        IrSender.sendSamsung(0xE0E0, 0x48B7, 0);
        Serial.println("Sent: CH NEXT");
        break;
      case 'L': // Ch Prev
        IrSender.sendSamsung(0xE0E0, 0x08F7, 0);
        Serial.println("Sent: CH PREV");
        break;
      case 'S': // Source
        IrSender.sendSamsung(0xE0E0, 0x807F, 0);
        Serial.println("Sent: SOURCE");
        break;
      default:
        Serial.println("Unknown command");
        break;
    }
    
    // Keep LED on for a moment so it's visible
    delay(100); 
    digitalWrite(2, LOW);
  }
}
