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

# --- Configuración ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
CAMERA_INDEX = 0

# --- Tema Claro ---
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

# --- Mapeo de Gestos a Comandos ---
GESTURE_TO_IR_NAMES = {
    "ENCENDIDO": ["Power", "power", "POWER", "On", "Off", "On/Off"],
    "SILENCIAR": ["Mute", "mute", "MUTE", "Silence", "A/V_Mute"],
    "SUBIR VOLUMEN": ["Vol_up", "Vol+", "Volume_up", "Volume+", "vol_up", "VOL_UP", "VOL+"],
    "BAJAR VOLUMEN": ["Vol_dn", "Vol-", "Volume_down", "Volume-", "vol_dn", "VOL_DN", "Vol_down", "VOL-"],
    "CANAL SIGUIENTE": ["Ch_next", "Ch+", "Channel_up", "Channel+", "ch_next", "CH_NEXT", "Up"],
    "CANAL ANTERIOR": ["Ch_prev", "Ch-", "Channel_down", "Channel-", "ch_prev", "CH_PREV", "Down"],
    "FUENTE": ["Source", "source", "SOURCE", "Input", "input", "INPUT", "Hdmi_1", "HDMI"]
}

# --- Lógica de Gestos ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def get_euclidean_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_finger_extended(landmarks, finger_tip_idx, finger_pip_idx, wrist_idx=0):
    """
    Comprobación robusta: El dedo está extendido si la punta está más lejos de la muñeca que la articulación PIP.
    Funciona independientemente de la rotación de la mano.
    """
    wrist = landmarks[wrist_idx]
    tip = landmarks[finger_tip_idx]
    pip = landmarks[finger_pip_idx]
    
    return get_euclidean_distance(tip, wrist) > get_euclidean_distance(pip, wrist) * 1.1

def count_fingers_robust(landmarks):
    """Cuenta los dedos extendidos (Índice, Medio, Anular, Meñique) usando lógica de distancia."""
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
    
    # 1. Analizar Dedos
    fingers_up = count_fingers_robust(landmarks)
    
    # 2. Analizar Pulgar
    # El pulgar es complicado. Comprobamos si la punta está 'lejos' de la base del índice (MCP)
    # y si el ángulo sugiere 'Arriba' o 'Abajo' relativo a la mano.
    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    index_mcp = landmarks[5]
    
    # Comprobación de Extensión del Pulgar
    thumb_extended = get_euclidean_distance(thumb_tip, index_mcp) > 0.15
    
    # Total de dedos efectivos
    total_fingers = fingers_up + (1 if thumb_extended else 0)
    
    # --- Árbol de Lógica ---
    # Detecta: Encendido (5), Mute (0), Vol+/- (Pulgar), Canal+/- (Índice), Fuente (3)
    
    # 1. Palma Abierta (Encender)
    if total_fingers == 5:
        return "ENCENDIDO"
        
    # 2. Puño / Gestos con Pulgar (0 dedos arriba)
    if fingers_up == 0:
        # Comprobar Orientación del Pulgar
        # Vector desde Muñeca a Punta del Pulgar
        dy = thumb_tip.y - wrist.y
        dx = thumb_tip.x - wrist.x
        
        # Si el pulgar está extendido significativamente
        if thumb_extended:
            # Comprobación de ángulo: -90 es Arriba, +90 es Abajo (en coords de imagen y aumenta hacia abajo)
            # Pero más simple: comparar Y relativo a otros nudillos
            
            # Pulgar Arriba: La punta está significativamente arriba de IP y MCP del Índice
            if thumb_tip.y < thumb_ip.y and thumb_tip.y < index_mcp.y:
                return "SUBIR VOLUMEN"
            
            # Pulgar Abajo: La punta está significativamente abajo de IP y MCP del Índice
            if thumb_tip.y > thumb_ip.y and thumb_tip.y > index_mcp.y:
                return "BAJAR VOLUMEN"
                
        return "SILENCIAR" # Puño Cerrado
        
    # 3. Apuntando (1 dedo: Índice)
    if fingers_up == 1 and is_finger_extended(landmarks, 8, 6):
        # Comprobar si apunta a Izquierda o Derecha
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        
        # Umbral para apuntar horizontalmente
        if abs(index_tip.x - index_pip.x) > 0.05:
            if index_tip.x < index_pip.x: # Izquierda (en pantalla)
                return "CANAL ANTERIOR"
            else:
                return "CANAL SIGUIENTE"
        
        # If vertical
        # Apuntando verticalmente (por defecto Siguiente)
        return "CANAL SIGUIENTE"
    
    if fingers_up == 2:
        return "CANAL ANTERIOR"
        
    if fingers_up == 3:
        return "FUENTE"
        
    if fingers_up == 4:
        return "ENCENDIDO" # Alternativa para 4 dedos

    return "NINGUNO"

from collections import deque
import math

# --- Hilo de Video ---
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
        
        self.gesture_buffer = deque(maxlen=7)

    def try_connect(self):
        """Intenta auto-descubrir y conectar al puerto serial"""
        if self.ser is not None:
            return True
            
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        candidate_ports = [p.device for p in ports if 'USB' in p.description or 'ACM' in p.description or 'USB' in p.device or 'ACM' in p.device]
        
        if not candidate_ports:
            candidate_ports = [p.device for p in ports]
            
        print(f"Buscando ESP32 en: {candidate_ports}")
        
        for port in candidate_ports:
            try:
                print(f"Intentando conectar a {port}...")
                self.ser = serial.Serial(port, BAUD_RATE, timeout=1)
                time.sleep(2) 
                
                
                print(f"¡Conectado exitosamente a {port}!")
                self.connection_status_signal.emit(True)
                return True
            except Exception as e:
                print(f"Falló conexión a {port}: {e}")
                if self.ser:
                    self.ser.close()
                self.ser = None
        
        self.connection_status_signal.emit(False)
        return False

    @pyqtSlot(str)
    def send_serial(self, command):
        if self.ser:
            try:
                self.ser.write(command.encode())
                self.ser.flush() # Asegurar que se envía inmediatamente
            except Exception as e:
                print(f"Error enviando serial: {e}")

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        
        hands = mp_hands.Hands(
            model_complexity=1, 
            min_detection_confidence=0.8,
            min_tracking_confidence=0.5,
            max_num_hands=1
        )
        
        last_sent_time = 0
        SEND_COOLDOWN = 0.8 # Respuesta ligeramente más rápida

        # Intento de conexión inicial (en hilo, para no bloquear UI)
        self.try_connect()

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
                    
                    # Obtener gesto crudo de la geometría
                    current_gesture = get_gesture_robust(hand_landmarks.landmark)
            
            # --- Suavizado / Debouncing ---
            self.gesture_buffer.append(current_gesture)
            
            # Encontrar gesto más común en buffer
            from collections import Counter
            if len(self.gesture_buffer) == self.gesture_buffer.maxlen:
                most_common, count = Counter(self.gesture_buffer).most_common(1)[0]
                
                # Umbral de confianza: 5 de 7 frames deben coincidir
                if count >= 5:
                    display_gesture = most_common
                    
                    # Solo enviar si es un comando válido y pasó el enfriamiento
                    if display_gesture != "NINGUNO" and (time.time() - last_sent_time > SEND_COOLDOWN):
                        self.gesture_signal.emit(display_gesture)
                        last_sent_time = time.time()
                        # Limpiar buffer para evitar doble disparo
                        self.gesture_buffer.clear()

            # Superposición UI
            cv2.putText(image_rgb, f"Gesto: {display_gesture}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            h, w, ch = image_rgb.shape
            bytes_per_line = ch * w
            convert_to_Qt_format = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            p = convert_to_Qt_format.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
            self.change_pixmap_signal.emit(p)
            
            # Leer respuestas ESP32
            if self.ser and self.ser.in_waiting > 0:
                try:
                    response = self.ser.readline().decode('utf-8').strip()
                    if response:
                        self.serial_response_signal.emit(response)
                except Exception:
                    self.ser = None
                    self.connection_status_signal.emit(False)
            
            # Auto-reconectar
            if self.ser is None and (time.time() - self.last_reconnect_attempt > self.RECONNECT_INTERVAL):
                self.last_reconnect_attempt = time.time()
                self.try_connect()

        cap.release()
        if self.ser:
            self.ser.close()

    def stop(self):
        self._run_flag = False
        self.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control IR por Gestos")
        self.resize(1300, 750)
        
        # Guardar comandos IR cargados
        self.ir_commands = {}
        
        # Todos los archivos IR para búsqueda
        self.all_ir_files = []

        # Widget Central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Separadores para áreas redimensionables
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Lado Izquierdo: Búsqueda y Lista de Archivos ---
        file_browser_widget = QWidget()
        file_browser_layout = QVBoxLayout(file_browser_widget)
        file_browser_layout.setContentsMargins(0, 0, 0, 0)
        file_browser_layout.setSpacing(10)
        
        lbl_browser = QLabel("Dispositivos IRDB")
        lbl_browser.setObjectName("title")
        file_browser_layout.addWidget(lbl_browser)
        
        # Caja de búsqueda
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar dispositivo (ej: Samsung, Epson...)")
        self.search_box.textChanged.connect(self.filter_files)
        file_browser_layout.addWidget(self.search_box)

        # --- Vista de Árbol con Búsqueda ---
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.path.abspath("./IRDB"))
        self.file_model.setNameFilters(["*.ir"])
        self.file_model.setNameFilterDisables(False)
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(self.file_model.index(os.path.abspath("./IRDB"))))
        
        # Ocultar columnas excepto Nombre
        self.tree_view.setHeaderHidden(True)
        for i in range(1, 4):
            self.tree_view.setColumnHidden(i, True)
            
        self.tree_view.clicked.connect(self.on_tree_clicked)
        file_browser_layout.addWidget(self.tree_view)
        
        splitter.addWidget(file_browser_widget)

        # --- Medio: Feed de Video ---
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(10)
        
        # Estado de conexión
        self.status_label = QLabel("Conectando...")
        self.status_label.setObjectName("title")
        video_layout.addWidget(self.status_label)
        
        self.image_label = QLabel(self)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setText("Iniciando Cámara...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #16213e; border-radius: 12px;")
        video_layout.addWidget(self.image_label)
        
        self.gesture_log = QTextEdit()
        self.gesture_log.setReadOnly(True)
        self.gesture_log.setMaximumHeight(150)
        self.gesture_log.setPlaceholderText("Los mensajes aparecerán aquí...")
        video_layout.addWidget(self.gesture_log)
        
        splitter.addWidget(video_widget)

        # --- Lado Derecho: Tabla de Comandos IR ---
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

        # Establecer tamaños iniciales del separador
        splitter.setSizes([300, 600, 350])

        # Iniciar Hilo de Video
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.gesture_signal.connect(self.on_gesture_detected)
        self.thread.serial_response_signal.connect(self.on_serial_response)
        self.thread.connection_status_signal.connect(self.on_connection_status)
        self.thread.start()

    def filter_files(self, text):
        """Filtrar vista de árbol"""
        self.proxy_model.setFilterFixedString(text)
        # Expandir todo si se busca
        if text:
            self.tree_view.expandAll()
        else:
            self.tree_view.collapseAll()

    def on_tree_clicked(self, index):
        """Manejar clic en nodo del árbol"""
        source_index = self.proxy_model.mapToSource(index)
        file_path = self.file_model.filePath(source_index)
        
        if os.path.isfile(file_path) and file_path.endswith('.ir'):
            self.load_ir_file(file_path)

    @pyqtSlot(bool)
    def on_connection_status(self, connected):
        if connected and self.thread.ser:
            self.status_label.setText(f"ESP32 Conectado ({self.thread.ser.port})")
            self.status_label.setStyleSheet("color: #00ff88;")
        else:
            self.status_label.setText("ESP32 No Conectado (Modo Simulación)")
            self.status_label.setStyleSheet("color: #ff6b6b;")

    @pyqtSlot(QImage)
    def update_image(self, qt_img):
        self.image_label.setPixmap(QPixmap.fromImage(qt_img))

    @pyqtSlot(str)
    def on_serial_response(self, response):
        """Mostrar respuesta ESP32 en log"""
        self.gesture_log.append(f"<span style='color:#00d9ff;'>ESP32:</span> {response}")
        sb = self.gesture_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str)
    def on_gesture_detected(self, gesture_name):
        """Manejar detección de gesto y enviar comando IR"""
        if not self.ir_commands:
            self.gesture_log.append(f"<span style='color:#ffaa00;'>{gesture_name}</span> - No hay archivo IR cargado")
            return
            
        ir_cmd = self.find_ir_command_for_gesture(gesture_name)
        
        if ir_cmd:
            # Ayudante para analizar cadena hex Little Endian de IRDB
            def parse_ir_hex(hex_str):
                # "34 12 00 00" -> ["34", "12", "00", "00"]
                parts = hex_str.strip().split()
                # Eliminar "00"s finales (pero mantener al menos un byte si todo es 00)
                while len(parts) > 1 and parts[-1] == "00":
                    parts.pop()
                # Invertir para Big Endian (así "34 12" pasa a ser "1234" -> 0x1234)
                parts.reverse()
                return "".join(parts)

            # Construir comando extendido: !PROTOCOLO:DIRECCION:COMANDO
            protocol = ir_cmd.get('protocol', 'NEC')
            
            raw_address = ir_cmd.get('address', '00 00 00 00')
            raw_command = ir_cmd.get('command', '00 00 00 00')
            
            address = parse_ir_hex(raw_address)
            command = parse_ir_hex(raw_command)
            
            serial_cmd = f"!{protocol}:{address}:{command}\n"
            self.thread.send_serial_signal.emit(serial_cmd)
            
            self.gesture_log.append(f"<span style='color:#00ff88;'>{gesture_name}</span> → {ir_cmd['name']}")
        else:
            self.gesture_log.append(f"<span style='color:#ff6b6b;'>{gesture_name}</span> - No hay comando asociado")
        
        sb = self.gesture_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def find_ir_command_for_gesture(self, gesture_name):
        """Encontrar comando IR que coincida con el gesto"""
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
