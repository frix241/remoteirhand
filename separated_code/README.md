# Hand Gesture TV Remote

Control remoto IR mediante gestos de mano usando Python/OpenCV + ESP32.

## 1. Arduino Code (`arduino_remote/`)

### Instalación
1. Abrir `arduino_remote.ino` en **Arduino IDE**
2. Instalar la librería **IRremoteESP8266**:
   - Sketch → Include Library → Manage Libraries
   - Buscar "IRremoteESP8266" por David Conran
   - Instalar
3. Seleccionar Board: **ESP32 Dev Module**
4. Conectar ESP32 y seleccionar el puerto correcto
5. Subir el sketch

### Hardware
- **ESP32** Dev Module
- **LED IR** conectado al GPIO4 (configurable en el código)
- LED integrado en GPIO2 como indicador visual

### Comandos Serial (115200 baud)
| Comando | Acción |
|---------|--------|
| `P` | Power On/Off |
| `M` | Mute |
| `U` | Subir Volumen |
| `D` | Bajar Volumen |
| `N` | Canal Siguiente |
| `L` | Canal Anterior |
| `S` | Cambiar Fuente |

---

## 2. Python Code (`python_detection/`)

### Instalación
```bash
pip install opencv-python mediapipe pyserial
```

### Configuración
Editar `detect_hands.py` si es necesario:
- `SERIAL_PORT`: Puerto del ESP32 (`/dev/ttyUSB0` en Linux, `COM3` en Windows)
- `CAMERA_INDEX`: Índice de la cámara (0 por defecto)

### Ejecución
```bash
python detect_hands.py
```

---

## 3. Códigos IR (IRDB)

Los códigos IR están en el directorio `IRDB/` (repositorio Flipper-IRDB).

### Estructura de archivos .ir
```
protocol: Samsung32
address: 07 00 00 00
command: 02 00 00 00
```

### Categorías disponibles
- `TVs/` - Televisores (Samsung, LG, Sony, etc.)
- `ACs/` - Aires acondicionados
- `SoundBars/` - Barras de sonido
- `Projectors/` - Proyectores
- Y muchas más...

### Fuentes de códigos
- **IRDB incluido**: Ya tienes miles de códigos en `./IRDB/`
- **Repositorio original**: [Flipper-IRDB](https://github.com/Lucaslhm/Flipper-IRDB)
- **Capturar códigos**: Usar receptor IR (VS1838B) con sketch de ejemplo de IRremoteESP8266

---

## Uso

1. Conectar ESP32 al PC
2. Subir el código Arduino
3. Ejecutar el script Python
4. Apuntar la cámara hacia ti
5. Realizar gestos:
   - 🖐️ Mano abierta → Power
   - ✊ Puño → Mute
   - 👍 Pulgar arriba → Vol+
   - 👎 Pulgar abajo → Vol-
   - ☝️ Un dedo → Canal+
   - ✌️ Dos dedos → Canal-
   - 🤟 Tres dedos → Source
