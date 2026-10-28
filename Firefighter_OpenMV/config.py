
# ======================================================
# FIREFIGHTER - OPENMV H7 R2
# Archivo: config.py
#
# Configuracion de vision, IBVS, servos y UART.
# ======================================================

# ======================================================
# 1. IMAGEN QVGA (320 x 240)
# ======================================================

IMG_CX = 160
IMG_CY = 120

# ======================================================
# 2. COMPENSACION DE APUNTADO
#
# X_OFFSET:
#   Negativo = objetivo a la izquierda.
#   Positivo = objetivo a la derecha.
#
# La cruceta permanece en el centro (160,120).
# PAN intentara mantener la llama en X = 140.
#
# Y_OFFSET se conserva para calibracion posterior.
# ======================================================

X_OFFSET = -80
Y_OFFSET = 0

# ======================================================
# 3. FILTRO EMA
# ======================================================

ALPHA = 0.40

# ======================================================
# 4. DETECCION BLANCO BRILLANTE - FILTRO IR
#
# Umbral probado en OpenMV IDE.
# Detecta regiones luminosas, no exclusivamente fuego.
# ======================================================

WHITE_THRESHOLD = (90, 100, -15, 25, -15, 35)

PIXELS_THRESHOLD = 200
AREA_THRESHOLD = 200
MERGE = True

# ======================================================
# 5. MAQUINA DE ESTADOS
# ======================================================

SEARCH = 0
TRACKING = 1

# ======================================================
# 6. CONTROLADOR IBVS PAN
# ======================================================

SCAN_MIN = -90
SCAN_MAX = 90

PAN_HOME = 0

KP = 0.05
DEADBAND = 10
MAX_STEP = 1.5

# ======================================================
# 7. CONTROLADOR TILT
#
# La camara permanece fija.
# TILT mueve solamente la manguera.
# ======================================================

KP_TILT = 0.02
DEADBAND_TILT = 10
MAX_STEP_TILT = 0.5

TILT_KH = 0.30
TILT_DIRECTION = 1.0

# ======================================================
# 8. LIMITES FISICOS ESP32-C3
# ======================================================

C3_PAN_MIN = 10
C3_PAN_MAX = 170

C3_TILT_MIN = 50
C3_TILT_MAX = 180

C3_TILT_HOME = 115.0

# ======================================================
# 9. SEGUIMIENTO DEL OBJETIVO
# ======================================================

BLOB_MAX_JUMP_PX = 45
BLOB_LOST_FRAMES = 4
BLOB_LOST_TIMEOUT_MS = 500

# ======================================================
# 10. CONTROL AUTOMATICO DE BOMBA
# ======================================================

TILT_ALIGNED_THRESHOLD = 10

PUMP_ALIGN_MS = 800
SERVO_SETTLE_MS = 1000
PUMP_SETTLE_MS = SERVO_SETTLE_MS

REF_EPSILON_DEG = 0.15
TILT_STABLE_DEG = 0.5
BLOB_STABLE_Y_PX = 5

# ======================================================
# 11. UART OPENMV <-> ESP32-C3
#
# OpenMV P4 TX -> C3 GPIO7 RX
# OpenMV P5 RX <- C3 GPIO6 TX
# ======================================================

UART_ID = 3
UART_BAUD = 115200
