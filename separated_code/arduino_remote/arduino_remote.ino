/*
 * ESP32 IR Remote Control - IRremote Library
 * 
 * Recibe comandos por serial y envía códigos IR.
 * Compatible con el proyecto de detección de gestos Python/OpenCV.
 * 
 * Librería: IRremote by Armin Joachimsmeyer
 * Instalar desde: Sketch → Include Library → Manage Libraries → "IRremote"
 * 
 * Soporta comandos extendidos: !PROTOCOLO:ADDRESS:COMMAND
 */

#include <Arduino.h>
#include <IRremote.hpp>

// --- Configuration ---
const uint8_t IR_SEND_PIN = 4;  // Pin del LED IR (GPIO4)
const uint32_t BAUD_RATE = 115200;

// --- Default Samsung IR Codes (fallback) ---
// Samsung TV usa Address 0x07, pero algunos modelos usan 0xE0E0
// Probado con códigos universales de Samsung
const uint16_t SAMSUNG_ADDRESS = 0x07;
const uint8_t CMD_POWER    = 0x02;   // Power On/Off
const uint8_t CMD_MUTE     = 0x0F;   // Mute
const uint8_t CMD_VOL_UP   = 0x07;   // Volume +
const uint8_t CMD_VOL_DOWN = 0x0B;   // Volume -
const uint8_t CMD_CH_NEXT  = 0x12;   // Channel +
const uint8_t CMD_CH_PREV  = 0x10;   // Channel -
const uint8_t CMD_SOURCE   = 0x01;   // Source/Input

// --- LED Indicator ---
const int LED_PIN = 2;
unsigned long ledTimer = 0;
bool ledOn = false;

// --- Helper: Convert hex string to int ---
uint32_t hexStringToUint(String hexStr) {
  hexStr.trim();
  hexStr.toUpperCase();
  return strtoul(hexStr.c_str(), NULL, 16);
}

// --- Send IR based on protocol ---
// Supports all protocols found in IRDB:
// NECext (143816), NEC (8862), RC5 (7589), Samsung32 (2309), Kaseikyo (1543)
// SIRC/SIRC15/SIRC20 (2605), RC6 (894), RCA (279), RC5X (190), Pioneer (154), NEC42 (124)
void sendIRCommand(String protocol, uint32_t address, uint32_t command) {
  protocol.toUpperCase();
  
  Serial.print("IR: ");
  Serial.print(protocol);
  Serial.print(" A:0x");
  Serial.print(address, HEX);
  Serial.print(" C:0x");
  Serial.println(command, HEX);
  
  // === NEC Family (most common) ===
  if (protocol == "NECEXT" || protocol == "NEC2" || protocol == "NECX") {
    // NECext: 16-bit address, 8-bit command (most used in IRDB)
    IrSender.sendNEC(address, command, 0);
  }
  else if (protocol == "NEC" || protocol == "NEC1") {
    IrSender.sendNEC(address, command, 0);
  }
  else if (protocol == "NEC42") {
    // NEC with 42-bit format - use standard NEC
    IrSender.sendNEC(address, command, 0);
  }
  
  // === RC5/RC6 Family ===
  else if (protocol == "RC5") {
    IrSender.sendRC5(address, command, 0);
  }
  else if (protocol == "RC5X") {
    // RC5 extended - use RC5 with toggle bit
    IrSender.sendRC5(address, command, 0);
  }
  else if (protocol == "RC6") {
    IrSender.sendRC6(address, command, 0);
  }
  
  // === Samsung ===
  else if (protocol == "SAMSUNG" || protocol == "SAMSUNG32") {
    IrSender.sendSamsung(address, command, 0);
  }
  
  // === Sony SIRC Family ===
  else if (protocol == "SIRC" || protocol == "SIRC12" || protocol == "SONY12") {
    IrSender.sendSony(address, command, 0, 12);  // 12 bits
  }
  else if (protocol == "SIRC15" || protocol == "SONY15") {
    IrSender.sendSony(address, command, 0, 15);  // 15 bits
  }
  else if (protocol == "SIRC20" || protocol == "SONY20" || protocol == "SONY") {
    IrSender.sendSony(address, command, 0, 20);  // 20 bits
  }
  
  // === Kaseikyo / Panasonic ===
  else if (protocol == "KASEIKYO" || protocol == "PANASONIC" || protocol == "KASEIKYO_DENON") {
    IrSender.sendKaseikyo(address, command, 0, 0);  // vendorID = 0
  }
  
  // === LG ===
  else if (protocol == "LG" || protocol == "LG32") {
    IrSender.sendLG(address, command, 0);
  }
  
  // === RCA ===
  else if (protocol == "RCA") {
    // RCA protocol - use NEC as fallback (similar timing)
    IrSender.sendNEC(address, command, 0);
  }
  
  // === Pioneer ===
  else if (protocol == "PIONEER") {
    // Pioneer uses NEC protocol with specific timing
    IrSender.sendNEC(address, command, 0);
  }
  
  // === JVC ===
  else if (protocol == "JVC") {
    IrSender.sendJVC((uint8_t)address, (uint8_t)command, 0);
  }
  
  // === Sharp ===
  else if (protocol == "SHARP") {
    IrSender.sendSharp(address, command, 0);
  }
  
  // === Denon ===
  else if (protocol == "DENON") {
    IrSender.sendDenon(address, command, 0);
  }
  
  // === Default: NEC (most compatible) ===
  else {
    Serial.print("Protocolo desconocido: ");
    Serial.println(protocol);
    IrSender.sendNEC(address, command, 0);
  }
}

// --- Parse and handle extended command ---
void handleExtendedCommand(String input) {
  // Format: !PROTOCOLO:ADDRESS:COMMAND
  // Example: !SAMSUNG:07:02
  
  input = input.substring(1);  // Remove '!'
  
  int firstColon = input.indexOf(':');
  int secondColon = input.indexOf(':', firstColon + 1);
  
  if (firstColon == -1 || secondColon == -1) {
    Serial.println("Error: Formato invalido. Usar !PROTOCOLO:ADDR:CMD");
    return;
  }
  
  String protocol = input.substring(0, firstColon);
  String addrStr = input.substring(firstColon + 1, secondColon);
  String cmdStr = input.substring(secondColon + 1);
  
  uint16_t address = (uint16_t)hexStringToUint(addrStr);
  uint8_t command = (uint8_t)hexStringToUint(cmdStr);
  
  sendIRCommand(protocol, address, command);
}

// --- Setup ---
void setup() {
  Serial.begin(BAUD_RATE);
  Serial.println("ESP32 IR Remote - Multi Protocol");
  Serial.println("Comandos simples: P, M, U, D, N, L, S");
  Serial.println("Comandos extendidos: !PROTOCOLO:ADDR:CMD");
  
  IrSender.begin(IR_SEND_PIN);
  
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
}

// --- Main Loop ---
void loop() {
  // Turn off LED after 100ms
  if (ledOn && (millis() - ledTimer > 100)) {
    digitalWrite(LED_PIN, LOW);
    ledOn = false;
  }

  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      // Turn on LED indicator
      digitalWrite(LED_PIN, HIGH);
      ledTimer = millis();
      ledOn = true;

      // Model name command: #NOMBRE_MODELO
      if (input.startsWith("#")) {
        String modelName = input.substring(1);
        Serial.print("Modelo Cargado: ");
        Serial.println(modelName);
        return;
      }

      // Extended command: !PROTOCOLO:ADDRESS:COMMAND
      if (input.startsWith("!")) {
        handleExtendedCommand(input);
        return;
      }

      // Simple command: single character (fallback to Samsung)
      char command = input.charAt(0);
      
      switch (command) {
        case 'P':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_POWER, 0);
          Serial.println("Accion: ENCENDIDO");
          break;
        case 'M':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_MUTE, 0);
          Serial.println("Accion: SILENCIAR");
          break;
        case 'U':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_VOL_UP, 0);
          Serial.println("Accion: SUBIR VOLUMEN");
          break;
        case 'D':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_VOL_DOWN, 0);
          Serial.println("Accion: BAJAR VOLUMEN");
          break;
        case 'N':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_CH_NEXT, 0);
          Serial.println("Accion: CANAL SIGUIENTE");
          break;
        case 'L':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_CH_PREV, 0);
          Serial.println("Accion: CANAL ANTERIOR");
          break;
        case 'S':
          IrSender.sendSamsung(SAMSUNG_ADDRESS, CMD_SOURCE, 0);
          Serial.println("Accion: FUENTE");
          break;
        default:
          break;
      }
    }
  }
}
