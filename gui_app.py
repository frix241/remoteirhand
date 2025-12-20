import sys
import cv2
import time
import serial
import mediapipe as mp
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
                             QTreeView, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QDir
from PyQt6.QtGui import QImage, QPixmap, QFileSystemModel

# Import the parser
from irdb_parser import parse_ir_file

# --- Configuration ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
CAMERA_INDEX = 0

# --- Gesture Logic (Copied/Adapted from main.py for now to ensure standalone function) ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def count_fingers(landmarks):
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    count = 0
    for tip, pip in zip(tips, pips):
        if landmarks[tip].y < landmarks[pip].y:
            count += 1
    return count

def is_thumb_up(landmarks):
    if (landmarks[4].y < landmarks[3].y and 
        landmarks[4].y < landmarks[5].y and
        count_fingers(landmarks) == 0):
        return True
    return False

def is_thumb_down(landmarks):
    if (landmarks[4].y > landmarks[3].y and 
        landmarks[4].y > landmarks[5].y and
        count_fingers(landmarks) == 0):
        return True
    return False

def get_gesture(landmarks):
    # Count 4 fingers (Index, Middle, Ring, Pinky)
    fingers = count_fingers(landmarks)
    
    # 0 Fingers (Fist-like)
    if fingers == 0:
        if is_thumb_up(landmarks):
            return "SUBIR VOLUMEN", 'U'
        if is_thumb_down(landmarks):
            return "BAJAR VOLUMEN", 'D'
        return "SILENCIAR", 'M' # Fist
        
    # 1 Finger (Index)
    if fingers == 1:
        return "CANAL SIGUIENTE", 'N'
        
    # 2 Fingers (Index + Middle)
    if fingers == 2:
        return "CANAL ANTERIOR", 'L'
        
    # 3 Fingers (Index + Middle + Ring)
    if fingers == 3:
        return "FUENTE", 'S'
        
    # 4 or 5 Fingers (Open Palm)
    if fingers == 4:
        return "ENCENDIDO", 'P'

    return "NINGUNO", None

# --- Video Thread ---
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    gesture_signal = pyqtSignal(str, str) # gesture_name, command_char
    send_serial_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.ser = None
        self.send_serial_signal.connect(self.send_serial)
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Conectado a {SERIAL_PORT}")
        except Exception as e:
            print(f"Advertencia: No se pudo conectar al puerto serie {SERIAL_PORT}. Ejecutando en modo simulación.")
            print(f"Error: {e}")

    @pyqtSlot(str)
    def send_serial(self, command):
        if self.ser:
            try:
                self.ser.write(command.encode())
            except Exception as e:
                print(f"Error enviando serial: {e}")

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        hands = mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
            max_num_hands=1
        )
        
        last_sent_time = 0
        SEND_COOLDOWN = 1.0

        while self._run_flag:
            success, image = cap.read()
            if not success:
                continue

            image = cv2.flip(image, 1)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)

            gesture_name = "NINGUNO"
            command_char = None

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # FIX: Draw on image_rgb so it shows up in the QImage
                    mp_drawing.draw_landmarks(
                        image_rgb,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS)
                    
                    gesture_name, command_char = get_gesture(hand_landmarks.landmark)
                    
                    if command_char and (time.time() - last_sent_time > SEND_COOLDOWN):
                        self.gesture_signal.emit(gesture_name, command_char)
                        if self.ser:
                            self.ser.write(command_char.encode())
                        last_sent_time = time.time()

            # Display gesture name on the image
            cv2.putText(image_rgb, f"Accion: {gesture_name}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            # Convert to Qt Image
            # FIX: Use image_rgb instead of image (which is BGR)
            h, w, ch = image_rgb.shape
            bytes_per_line = ch * w
            convert_to_Qt_format = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            p = convert_to_Qt_format.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
            self.change_pixmap_signal.emit(p)

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
        self.setWindowTitle("Control Remoto por Gestos y Visor IRDB")
        self.resize(1200, 700)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Splitter for resizable areas
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Side: File Browser ---
        file_browser_widget = QWidget()
        file_browser_layout = QVBoxLayout(file_browser_widget)
        
        lbl_browser = QLabel("Archivos IRDB")
        lbl_browser.setStyleSheet("font-weight: bold;")
        file_browser_layout.addWidget(lbl_browser)

        self.file_model = QFileSystemModel()
        root_path = os.path.abspath("./IRDB")
        self.file_model.setRootPath(root_path)
        self.file_model.setNameFilters(["*.ir"])
        self.file_model.setNameFilterDisables(False)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setRootIndex(self.file_model.index(root_path))
        self.tree_view.setColumnHidden(1, True) # Hide Size
        self.tree_view.setColumnHidden(2, True) # Hide Type
        self.tree_view.setColumnHidden(3, True) # Hide Date
        self.tree_view.clicked.connect(self.on_file_selected)
        
        file_browser_layout.addWidget(self.tree_view)
        splitter.addWidget(file_browser_widget)

        # --- Middle: Video Feed ---
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        
        self.image_label = QLabel(self)
        self.image_label.resize(640, 480)
        self.image_label.setText("Iniciando Cámara...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_layout.addWidget(self.image_label)
        
        self.gesture_log = QTextEdit()
        self.gesture_log.setReadOnly(True)
        self.gesture_log.setMaximumHeight(150)
        video_layout.addWidget(self.gesture_log)
        
        splitter.addWidget(video_widget)

        # --- Right Side: IR Commands ---
        commands_widget = QWidget()
        commands_layout = QVBoxLayout(commands_widget)
        
        self.file_label = QLabel("Ningún archivo cargado")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("font-weight: bold; color: blue;")
        commands_layout.addWidget(self.file_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Protocolo", "Comando"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        commands_layout.addWidget(self.table)
        
        splitter.addWidget(commands_widget)

        # Set initial sizes for splitter
        splitter.setSizes([250, 600, 350])

        # Start Video Thread
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.gesture_signal.connect(self.update_gesture_log)
        self.thread.start()

    @pyqtSlot(QImage)
    def update_image(self, qt_img):
        self.image_label.setPixmap(QPixmap.fromImage(qt_img))

    @pyqtSlot(str, str)
    def update_gesture_log(self, gesture_name, command_char):
        self.gesture_log.append(f"Detectado: {gesture_name} -> Enviado: {command_char}")
        # Auto scroll
        sb = self.gesture_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_file_selected(self, index):
        file_path = self.file_model.filePath(index)
        if file_path.endswith(".ir") and not self.file_model.isDir(index):
            self.load_ir_file(file_path)

    def load_ir_file(self, file_path):
        model_name = os.path.basename(file_path).replace(".ir", "")
        self.file_label.setText(f"Cargado: {os.path.basename(file_path)}")
        
        # Send model name to Arduino
        if self.thread.isRunning():
            self.thread.send_serial_signal.emit(f"#{model_name}\n")
            
        commands = parse_ir_file(file_path)
        self.populate_table(commands)

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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
