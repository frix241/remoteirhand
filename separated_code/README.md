# Hand Gesture TV Remote

This folder contains the separated code for the Hand Gesture TV Remote project.

## 1. Arduino Code (`arduino_remote/`)
This folder contains the code to be uploaded to your ESP32.

**Instructions:**
1. Open the `arduino_remote/arduino_remote.ino` file in the **Arduino IDE**.
2. Make sure you have the **IRremote** library installed (Sketch -> Include Library -> Manage Libraries -> Search for "IRremote" by Armin Joachimsmeyer).
3. Connect your ESP32 and select the correct Board and Port.
4. Upload the sketch.

## 2. Python Code (`python_detection/`)
This folder contains the Python script that runs on your computer, detects hand gestures, and sends commands to the ESP32.

**Instructions:**
1. Ensure you have the required libraries installed:
   ```bash
   pip install opencv-python mediapipe pyserial
   ```
2. Connect your ESP32 to the computer.
3. Check which serial port it is using (e.g., `/dev/ttyUSB0` on Linux, `COM3` on Windows).
4. Edit `detect_hands.py` if necessary to update the `SERIAL_PORT` variable.
5. Run the script:
   ```bash
   python detect_hands.py
   ```

## Usage
- Point your webcam at yourself.
- Perform gestures (Open Palm, Fist, Thumb Up/Down, Pointing Up/Left/Right).
- The Python script will send commands to the ESP32, which will emit IR signals to your TV.
