import sys
import cv2
import time
import serial
import mediapipe as mp
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
                             QTreeView, QSplitter, QLineEdit, QFrame, QListWidget,
                             QListWidgetItem, QStackedWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QDir, QSortFilterProxyModel, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFileSystemModel, QFont, QPalette, QColor

# Import the parser
from irdb_parser import parse_ir_file

# --- Configuration ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
CAMERA_INDEX = 0

# --- Modern Light Theme ---
LIGHT_STYLE = """
QMainWindow {
    background-color: #f5f7fa;
}
QWidget {
    background-color: #f5f7fa;
    color: #2d3436;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    color: #2d3436;
}
QLabel#title {
    font-size: 14px;
    font-weight: bold;
    color: #6c5ce7;
    padding: 8px;
}
QLineEdit {
    background-color: #ffffff;
    border: 2px solid #dfe6e9;
    border-radius: 8px;
    padding: 10px;
    color: #2d3436;
    font-size: 13px;
}
QLineEdit:focus {
    border: 2px solid #6c5ce7;
}
QListWidget {
    background-color: #ffffff;
    border: 1px solid #dfe6e9;
    border-radius: 8px;
    padding: 5px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 6px;
    margin: 2px;
}
QListWidget::item:hover {
    background-color: #e8f4fd;
}
QListWidget::item:selected {
    background-color: #6c5ce7;
    color: white;
}
QTreeView {
    background-color: #ffffff;
    border: 1px solid #dfe6e9;
    border-radius: 8px;
}
QTreeView::item {
    padding: 6px;
}
QTreeView::item:hover {
    background-color: #e8f4fd;
}
QTreeView::item:selected {
    background-color: #6c5ce7;
    color: white;
}
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #dfe6e9;
    border-radius: 8px;
    padding: 10px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #dfe6e9;
    border-radius: 8px;
    gridline-color: #dfe6e9;
}
QTableWidget::item {
    padding: 8px;
}
QTableWidget::item:alternate {
    background-color: #f8f9fa;
}
QHeaderView::section {
    background-color: #6c5ce7;
    color: white;
    padding: 10px;
    border: none;
    font-weight: bold;
}
QSplitter::handle {
    background-color: #dfe6e9;
    width: 3px;
}
QPushButton {
    background-color: #6c5ce7;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #a29bfe;
}
QPushButton:pressed {
    background-color: #5b4cdb;
}
QScrollBar:vertical {
    background-color: #f5f7fa;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #dfe6e9;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #6c5ce7;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# --- Gesture to Command Name Mapping ---
GESTURE_TO_IR_NAMES = {
    "ENCENDIDO": ["Power", "power", "POWER", "On", "Off", "On/Off"],
    "SILENCIAR": ["Mute", "mute", "MUTE", "Silence", "A/V_Mute"],
    "SUBIR VOLUMEN": ["Vol_up", "Vol+", "Volume_up", "Volume+", "vol_up", "VOL_UP", "VOL+"],
    "BAJAR VOLUMEN": ["Vol_dn", "Vol-", "Volume_down", "Volume-", "vol_dn", "VOL_DN", "Vol_down", "VOL-"],
    "CANAL SIGUIENTE": ["Ch_next", "Ch+", "Channel_up", "Channel+", "ch_next", "CH_NEXT", "Up"],
    "CANAL ANTERIOR": ["Ch_prev", "Ch-", "Channel_down", "Channel-", "ch_prev", "CH_PREV", "Down"],
    "FUENTE": ["Source", "source", "SOURCE", "Input", "input", "INPUT", "Hdmi_1", "HDMI"]
}

# --- Gesture Logic ---
# --- Advanced Gesture Logic ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def get_euclidean_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_finger_extended(landmarks, finger_tip_idx, finger_pip_idx, wrist_idx=0):
    """
    Robust check: Finger is extended if Tip is further from Wrist than PIP is.
    Works regardless of hand rotation.
    """
    wrist = landmarks[wrist_idx]
    tip = landmarks[finger_tip_idx]
    pip = landmarks[finger_pip_idx]
    
    return get_euclidean_distance(tip, wrist) > get_euclidean_distance(pip, wrist) * 1.1

def count_fingers_robust(landmarks):
    """Counts extended fingers (Index, Middle, Ring, Pinky) using distance logic."""
    # Tips: 8, 12, 16, 20. PIPs: 6, 10, 14, 18
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    count = 0
    for tip, pip in zip(tips, pips):
        if is_finger_extended(landmarks, tip, pip):
            count += 1
    return count

def get_gesture_robust(landmarks):
    import math
    
    # 1. Analyze Fingers
    fingers_up = count_fingers_robust(landmarks)
    
    # 2. Analyze Thumb
    # Thumb is tricky. We check if Tip is 'far' from the Index MCP (base of index finger)
    # and if the angle suggests 'Up' or 'Down' relative to the hand.
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    index_mcp = landmarks[5]
    
    # Thumb Extension Check
    thumb_extended = get_euclidean_distance(thumb_tip, index_mcp) > 0.15
    
    # Total effective fingers
    total_fingers = fingers_up + (1 if thumb_extended else 0)
    
    # --- Logic Tree ---
    
    # 1. Open Palm (Power)
    if total_fingers == 5:
        return "ENCENDIDO"
        
    # 2. Fist / Thumb Gestures (0 fingers up)
    if fingers_up == 0:
        # Check Thumb Orientation
        # Vector from Wrist to Thumb Tip
        dy = thumb_tip.y - wrist.y
        dx = thumb_tip.x - wrist.x
        
        # If thumb is extended significantly
        if thumb_extended:
            # Angle check: -90 is Up, +90 is Down (in image coords y increases downwards)
            # But simpler: compare Y relative to other knuckles
            
            # Thumb Up: Tip is significantly above IP and Index MCP
            if thumb_tip.y < thumb_ip.y and thumb_tip.y < index_mcp.y:
                return "SUBIR VOLUMEN"
            
            # Thumb Down: Tip is significantly below IP and Index MCP
            if thumb_tip.y > thumb_ip.y and thumb_tip.y > index_mcp.y:
                return "BAJAR VOLUMEN"
                
        return "SILENCIAR" # Closed Fist
        
    # 3. Pointing (1 finger: Index)
    if fingers_up == 1 and is_finger_extended(landmarks, 8, 6):
        # Check if it's pointing Left or Right
        # We use X position of Tip vs PIP
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        
        # Threshold for horizontal pointing
        if abs(index_tip.x - index_pip.x) > 0.05:
            if index_tip.x < index_pip.x: # Left (on screen)
                return "CANAL ANTERIOR"
            else:
                return "CANAL SIGUIENTE"
        
        # If vertical
        return "CANAL SIGUIENTE" # Default to Next if just pointing up? Or maybe Source?
        
    # 4. Two Fingers (Peace Sign) -> Source?
    # Original logic had 3 fingers for Source, let's stick to that or adapt.
    # User asked for "better detection", let's map:
    # 1 Finger -> Channel Next
    # 2 Fingers -> Channel Prev
    # 3 Fingers -> Source
    
    if fingers_up == 2:
        return "CANAL ANTERIOR"
        
    if fingers_up == 3:
        return "FUENTE"
        
    if fingers_up == 4:
        return "ENCENDIDO" # Alternative for 4 fingers

    return "NINGUNO"

from collections import deque
import math

# --- Video Thread ---
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    gesture_signal = pyqtSignal(str)
    send_serial_signal = pyqtSignal(str)
    serial_response_signal = pyqtSignal(str)
    connection_status_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.ser = None
        self.last_reconnect_attempt = 0
        self.RECONNECT_INTERVAL = 5.0
        self.send_serial_signal.connect(self.send_serial)
        
        # Smoothing Buffer
        self.gesture_buffer = deque(maxlen=7) # Store last 7 frames
        self.try_connect()

    def try_connect(self):
        """Try to connect to serial port"""
        if self.ser is not None:
            return True
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"Conectado a {SERIAL_PORT}")
            self.connection_status_signal.emit(True)
            return True
        except Exception as e:
            self.ser = None
            self.connection_status_signal.emit(False)
            return False

    @pyqtSlot(str)
    def send_serial(self, command):
        if self.ser:
            try:
                self.ser.write(command.encode())
            except Exception as e:
                print(f"Error enviando serial: {e}")

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        
        # UPGRADED MODEL: Complexity 1 (Better accuracy)
        hands = mp_hands.Hands(
            model_complexity=1, 
            min_detection_confidence=0.8,
            min_tracking_confidence=0.5,
            max_num_hands=1
        )
        
        last_sent_time = 0
        SEND_COOLDOWN = 0.8 # Slightly faster response

        while self._run_flag:
            success, image = cap.read()
            if not success:
                continue

            image = cv2.flip(image, 1)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)

            current_gesture = "NINGUNO"
            display_gesture = "..."

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        image_rgb,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS)
                    
                    # Get raw gesture from geometry
                    current_gesture = get_gesture_robust(hand_landmarks.landmark)
            
            # --- Smoothing / Debouncing ---
            self.gesture_buffer.append(current_gesture)
            
            # Find most common gesture in buffer
            from collections import Counter
            if len(self.gesture_buffer) == self.gesture_buffer.maxlen:
                most_common, count = Counter(self.gesture_buffer).most_common(1)[0]
                
                # Confidence threshold: 5 out of 7 frames must match
                if count >= 5:
                    display_gesture = most_common
                    
                    # Only send if it's a valid command and cooldown passed
                    if display_gesture != "NINGUNO" and (time.time() - last_sent_time > SEND_COOLDOWN):
                        self.gesture_signal.emit(display_gesture)
                        last_sent_time = time.time()
                        # Clear buffer to prevent double triggering
                        self.gesture_buffer.clear()

            # UI Overlay
            cv2.putText(image_rgb, f"Gesto: {display_gesture}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            h, w, ch = image_rgb.shape
            bytes_per_line = ch * w
            convert_to_Qt_format = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            p = convert_to_Qt_format.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
            self.change_pixmap_signal.emit(p)
            
            # Read ESP32 responses
            if self.ser and self.ser.in_waiting > 0:
                try:
                    response = self.ser.readline().decode('utf-8').strip()
                    if response:
                        self.serial_response_signal.emit(response)
                except Exception:
                    self.ser = None
                    self.connection_status_signal.emit(False)
            
            # Auto-reconnect
            if self.ser is None and (time.time() - self.last_reconnect_attempt > self.RECONNECT_INTERVAL):
                self.last_reconnect_attempt = time.time()
                self.try_connect()

        cap.release()
        if self.ser:
            self.ser.close()

    def stop(self):
        self._run_flag = False
        self.wait()

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control IR por Gestos")
        self.resize(1300, 750)
        
        # Store loaded IR commands
        self.ir_commands = {}
        
        # All IR files for search
        self.all_ir_files = []
        self.scan_ir_files()

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Splitter for resizable areas
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Side: Search and File List ---
        file_browser_widget = QWidget()
        file_browser_layout = QVBoxLayout(file_browser_widget)
        file_browser_layout.setContentsMargins(0, 0, 0, 0)
        file_browser_layout.setSpacing(10)
        
        lbl_browser = QLabel("Dispositivos IRDB")
        lbl_browser.setObjectName("title")
        file_browser_layout.addWidget(lbl_browser)
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Buscar dispositivo (ej: Samsung, Epson...)")
        self.search_box.textChanged.connect(self.filter_files)
        file_browser_layout.addWidget(self.search_box)
        
        # Results list (custom search results)
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_search_result_clicked)
        file_browser_layout.addWidget(self.results_list)
        
        # Show initial files
        self.filter_files("")
        
        splitter.addWidget(file_browser_widget)

        # --- Middle: Video Feed ---
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(10)
        
        # Connection status
        self.status_label = QLabel("Conectando...")
        self.status_label.setObjectName("title")
        video_layout.addWidget(self.status_label)
        
        self.image_label = QLabel(self)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setText("📷 Iniciando Cámara...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #16213e; border-radius: 12px;")
        video_layout.addWidget(self.image_label)
        
        self.gesture_log = QTextEdit()
        self.gesture_log.setReadOnly(True)
        self.gesture_log.setMaximumHeight(150)
        self.gesture_log.setPlaceholderText("Los mensajes aparecerán aquí...")
        video_layout.addWidget(self.gesture_log)
        
        splitter.addWidget(video_widget)

        # --- Right Side: IR Commands Table ---
        commands_widget = QWidget()
        commands_layout = QVBoxLayout(commands_widget)
        commands_layout.setContentsMargins(0, 0, 0, 0)
        commands_layout.setSpacing(10)
        
        self.file_label = QLabel("Ningún archivo cargado")
        self.file_label.setObjectName("title")
        self.file_label.setWordWrap(True)
        commands_layout.addWidget(self.file_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Protocolo", "Comando"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        commands_layout.addWidget(self.table)
        
        splitter.addWidget(commands_widget)

        # Set initial sizes for splitter
        splitter.setSizes([300, 600, 350])

        # Start Video Thread
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.gesture_signal.connect(self.on_gesture_detected)
        self.thread.serial_response_signal.connect(self.on_serial_response)
        self.thread.connection_status_signal.connect(self.on_connection_status)
        self.thread.start()

    def scan_ir_files(self):
        """Scan all .ir files recursively in IRDB"""
        irdb_path = os.path.abspath("./IRDB")
        self.all_ir_files = []
        
        for root, dirs, files in os.walk(irdb_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.endswith('.ir'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, irdb_path)
                    # Store as (display_name, full_path, relative_path)
                    display = rel_path.replace('/', ' → ').replace('.ir', '')
                    self.all_ir_files.append((display, full_path, rel_path))

    def filter_files(self, text):
        """Filter and show matching IR files"""
        self.results_list.clear()
        text_lower = text.lower()
        
        matches = []
        for display, full_path, rel_path in self.all_ir_files:
            if text_lower in rel_path.lower():
                matches.append((display, full_path))
        
        # Limit to 100 results to keep UI responsive
        for display, full_path in matches[:100]:
            item = QListWidgetItem(f" {display}")
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            self.results_list.addItem(item)
        
        if len(matches) > 100:
            info_item = QListWidgetItem(f"... y {len(matches) - 100} más")
            info_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results_list.addItem(info_item)

    def on_search_result_clicked(self, item):
        """Handle click on search result"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.load_ir_file(file_path)

    @pyqtSlot(bool)
    def on_connection_status(self, connected):
        if connected:
            self.status_label.setText("ESP32 Conectado")
            self.status_label.setStyleSheet("color: #00ff88;")
        else:
            self.status_label.setText("ESP32 No Conectado (Modo Simulación)")
            self.status_label.setStyleSheet("color: #ff6b6b;")

    @pyqtSlot(QImage)
    def update_image(self, qt_img):
        self.image_label.setPixmap(QPixmap.fromImage(qt_img))

    @pyqtSlot(str)
    def on_serial_response(self, response):
        """Show ESP32 response in log"""
        self.gesture_log.append(f"📡 <span style='color:#00d9ff;'>ESP32:</span> {response}")
        sb = self.gesture_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str)
    def on_gesture_detected(self, gesture_name):
        """Handle gesture detection and send IR command"""
        if not self.ir_commands:
            self.gesture_log.append(f"⚠️ <span style='color:#ffaa00;'>{gesture_name}</span> - No hay archivo IR cargado")
            return
            
        ir_cmd = self.find_ir_command_for_gesture(gesture_name)
        
        if ir_cmd:
            # Helper to parse Little Endian hex string from IRDB
            def parse_ir_hex(hex_str):
                # "34 12 00 00" -> ["34", "12", "00", "00"]
                parts = hex_str.strip().split()
                # Remove trailing "00"s (but keep at least one byte if all are 00)
                while len(parts) > 1 and parts[-1] == "00":
                    parts.pop()
                # Reverse for Big Endian (so "34 12" becomes "1234" -> 0x1234)
                parts.reverse()
                return "".join(parts)

            # Build extended command: !PROTOCOLO:ADDRESS:COMMAND
            protocol = ir_cmd.get('protocol', 'NEC')
            
            raw_address = ir_cmd.get('address', '00 00 00 00')
            raw_command = ir_cmd.get('command', '00 00 00 00')
            
            address = parse_ir_hex(raw_address)
            command = parse_ir_hex(raw_command)
            
            serial_cmd = f"!{protocol}:{address}:{command}\n"
            self.thread.send_serial_signal.emit(serial_cmd)
            
            self.gesture_log.append(f"✅ <span style='color:#00ff88;'>{gesture_name}</span> → {ir_cmd['name']}")
        else:
            self.gesture_log.append(f"❌ <span style='color:#ff6b6b;'>{gesture_name}</span> - No hay comando asociado")
        
        sb = self.gesture_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def find_ir_command_for_gesture(self, gesture_name):
        """Find IR command that matches the gesture"""
        possible_names = GESTURE_TO_IR_NAMES.get(gesture_name, [])
        
        for name in possible_names:
            if name in self.ir_commands:
                return self.ir_commands[name]
        
        return None

    def load_ir_file(self, file_path):
        model_name = os.path.basename(file_path).replace(".ir", "")
        self.file_label.setText(f"{model_name}")
        
        if self.thread.isRunning():
            self.thread.send_serial_signal.emit(f"#{model_name}\n")
            
        commands = parse_ir_file(file_path)
        
        self.ir_commands = {}
        for cmd in commands:
            name = cmd.get('name', '')
            if name:
                self.ir_commands[name] = cmd
        
        self.populate_table(commands)
        self.gesture_log.append(f"📂 <span style='color:#00d9ff;'>Cargado:</span> {model_name} ({len(commands)} comandos)")

    def populate_table(self, commands):
        self.table.setRowCount(0)
        for cmd in commands:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(cmd.get('name', '')))
            self.table.setItem(row, 1, QTableWidgetItem(cmd.get('protocol', '')))
            self.table.setItem(row, 2, QTableWidgetItem(cmd.get('command', '')))

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
