import cv2
import mediapipe as mp
import serial
import time
import math

# --- Configuration ---
SERIAL_PORT = '/dev/ttyUSB0'  # Update this to your ESP32 port
BAUD_RATE = 115200
CAMERA_INDEX = 0

# --- Serial Communication ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to {SERIAL_PORT}")
except Exception as e:
    print(f"Warning: Could not connect to serial port {SERIAL_PORT}. Running in simulation mode.")
    print(f"Error: {e}")
    ser = None

# --- MediaPipe Setup ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5,
    max_num_hands=1
)

# --- Gesture Logic ---
def count_fingers(landmarks):
    """Counts the number of fingers extended (excluding thumb for simplicity in some checks)."""
    # Tips IDs: Index=8, Middle=12, Ring=16, Pinky=20
    tips = [8, 12, 16, 20]
    # PIP IDs (lower joint): 6, 10, 14, 18
    pips = [6, 10, 14, 18]
    
    count = 0
    for tip, pip in zip(tips, pips):
        # In MediaPipe, y decreases as you go up
        if landmarks[tip].y < landmarks[pip].y:
            count += 1
    return count

def is_thumb_up(landmarks):
    # Thumb tip (4) above Thumb IP (3) and Index MCP (5)
    # And other fingers folded
    if (landmarks[4].y < landmarks[3].y and 
        landmarks[4].y < landmarks[5].y and
        count_fingers(landmarks) == 0):
        return True
    return False

def is_thumb_down(landmarks):
    # Thumb tip (4) below Thumb IP (3)
    # And other fingers folded
    if (landmarks[4].y > landmarks[3].y and 
        landmarks[4].y > landmarks[5].y and
        count_fingers(landmarks) == 0):
        return True
    return False

def is_pointing_up(landmarks):
    # Index extended, others folded
    if (landmarks[8].y < landmarks[6].y and 
        count_fingers(landmarks) == 1): # Only index is up (technically count_fingers checks 4 fingers)
        # Double check it's the index
        if landmarks[8].y < landmarks[6].y and landmarks[12].y > landmarks[10].y:
            return True
    return False

def is_pointing_right(landmarks):
    # Index tip x > Index MCP x (assuming right hand facing camera, right is larger x)
    # Note: Mirror effect might flip this. Let's assume non-mirrored for logic first, or handle both.
    # Actually, let's just check x difference.
    if (abs(landmarks[8].x - landmarks[5].x) > 0.1 and # Significant horizontal extension
        count_fingers(landmarks) <= 1): # Mostly folded
        if landmarks[8].x < landmarks[5].x: # Tip is to the left of knuckle (on screen) -> Pointing Left
             return "LEFT"
        else:
             return "RIGHT"
    return None

def get_gesture(landmarks):
    # 1. Power: Open Palm (5 fingers)
    # Thumb is tricky, let's check if thumb tip is to the side of the palm
    thumb_extended = False
    if abs(landmarks[4].x - landmarks[9].x) > 0.1: # Thumb tip far from middle finger mcp
        thumb_extended = True
    
    finger_count = count_fingers(landmarks)
    if thumb_extended:
        finger_count += 1
        
    if finger_count == 5:
        return "POWER", 'P'
    
    if finger_count == 0:
        # Check for Thumb Up/Down specifically
        if is_thumb_up(landmarks):
            return "VOL_UP", 'U'
        if is_thumb_down(landmarks):
            return "VOL_DOWN", 'D'
        return "MUTE", 'M' # Fist
        
    if is_pointing_up(landmarks):
        return "SOURCE", 'S'
        
    direction = is_pointing_right(landmarks)
    if direction == "RIGHT":
        return "CH_NEXT", 'N'
    elif direction == "LEFT":
        return "CH_PREV", 'L'

    return "NONE", None

# --- Main Loop ---
cap = cv2.VideoCapture(CAMERA_INDEX)
last_sent_time = 0
SEND_COOLDOWN = 1.0 # Seconds between commands

while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Flip the image horizontally for a later selfie-view display
    image = cv2.flip(image, 1)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)

    gesture_name = "NONE"
    
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS)
            
            gesture_name, command_char = get_gesture(hand_landmarks.landmark)
            
            if command_char and (time.time() - last_sent_time > SEND_COOLDOWN):
                print(f"Detected: {gesture_name} -> Sending: {command_char}")
                if ser:
                    ser.write(command_char.encode())
                last_sent_time = time.time()
                
            # Display gesture name
            cv2.putText(image, f"Gesture: {gesture_name}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

    cv2.imshow('Hand Gesture Remote', image)
    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
