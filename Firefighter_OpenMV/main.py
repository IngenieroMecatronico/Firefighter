# ======================================================
# FIREFIGHTER - OPENMV H7 R2 + WINC1500
# Firmware: OpenMV v5.0.0
#
# MANUAL:
# - Video
# - Vision pasiva
#
# SEMI:
# - SEARCH mediante PAN
# - TRACKING IBVS
# - PAN/TILT
# - Bomba
#
# AUTO:
# - SCAN con PAN mientras el robot esta detenido
# - Si no encuentra fuego -> AUTO_SCAN_90
# - Espera que termine el giro del chasis
# - Escanea el nuevo sector
# - Si encuentra fuego -> TRACKING IBVS
#
# NOTA:
# AUTO_FORWARD todavia NO esta habilitado.
#
# UART3:
# P4 TX -> C3 GPIO7 RX
# P5 RX <- C3 GPIO6 TX
# ======================================================

import time
import network
import socket

import config
import vision
import camera_uart
import pan
import tilt
import pump


# ======================================================
# CONFIGURACION
# ======================================================

WIFI_SSID = "Robotat_2"
WIFI_PASSWORD = "Firefighter_2"
STREAM_PORT = 8080

# Mantener False mientras calibramos locomocion AUTO.
BOMBA_HABILITADA = True

PUMP_ALIGN_MS = 800
SERVO_SETTLE_MS = 1000
REF_EPSILON_DEG = 0.15
TARGET_STABLE_PX = 5

PING_INTERVAL = 2000
PONG_MAX_AGE_MS = 5000

# Tiempo permitido para que PAN explore el sector.
# Ajustaremos este valor despues de medir un barrido real.
AUTO_SCAN_TIME_MS = 5000

# Timeout absoluto esperando el giro del chasis.
AUTO_TURN_TIMEOUT_MS = 8000

# Correccion de chasis: giro de 1100 ms al saturarse PAN.
AUTO_PAN_LIMIT_MARGIN_DEG = 5.0
AUTO_PAN_LIMIT_FRAMES = 3
AUTO_MAX_CORRECTIONS = 5
AUTO_CORRECTION_SETTLE_MS = 350
# Mantener la bomba fisicamente desconectada en primeras pruebas.



# ======================================================
# ESTADOS AUTO
# ======================================================

AUTO_SCAN = 0
AUTO_TRACK = 1
AUTO_WAIT_TURN = 2
AUTO_WAIT_CORRECTION = 3
AUTO_SETTLE_CORRECTION = 4


# ======================================================
# ESTADO GENERAL
# ======================================================

modo = "MANUAL"
estado_vision = config.SEARCH
estado_auto = AUTO_SCAN

client = None

fire_detected = False
estop_activo = True

ultimo_error_x = 0
ultimo_error_y = 0

objetivo_cx = None
objetivo_cy = None
perdidos = 0

alineado_desde = None

ultimo_pan_ref = None
ultimo_tilt_ref = None
ultimo_cambio_ref = time.ticks_ms()

ultimo_objetivo_y = None
ultimo_cambio_objetivo = time.ticks_ms()

ultimo_ping = time.ticks_ms()
ultimo_pong = 0

auto_scan_inicio = time.ticks_ms()
auto_giro_solicitado_en = 0
auto_calibracion_pendiente = False

# Variables exclusivas de correccion AUTO.
auto_saturation_frames = 0
auto_corrections = 0
auto_correction_settle_at = 0
auto_extra_turn_pending = False


# ======================================================
# WIFI
# ======================================================

print()
print("================================")
print("FIREFIGHTER - OPENMV")
print("================================")
print("Inicializando WINC1500...")

wlan = network.WINC()

print("WINC1500 detectado.")
print("Conectando a:", WIFI_SSID)

wlan.connect(
    WIFI_SSID,
    key=WIFI_PASSWORD,
    security=network.WINC.WPA_PSK
)

if not wlan.isconnected():
    raise OSError("No fue posible conectar al WiFi")

wifi_config = wlan.ifconfig()
OPENMV_IP = wifi_config[0]

print()
print("==============================")
print("WIFI CONECTADO")
print("==============================")
print("IP:", OPENMV_IP)
print("Mascara:", wifi_config[1])
print("Gateway:", wifi_config[2])
print()


# ======================================================
# VISION / BOMBA
# ======================================================

print("Inicializando vision...")
vision.init()
print("Vision lista.")

pump.init()


# ======================================================
# SERVIDOR MJPEG
# ======================================================

print("Creando servidor de video...")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", STREAM_PORT))
server.listen(1)
server.settimeout(0.01)

print("STREAM: http://%s:%d" % (OPENMV_IP, STREAM_PORT))
print()


# ======================================================
# REINICIAR VARIABLES DE OBJETIVO
# ======================================================

def reset_objetivo():
    global objetivo_cx, objetivo_cy, perdidos
    global fire_detected, alineado_desde
    global ultimo_pan_ref, ultimo_tilt_ref
    global ultimo_objetivo_y

    objetivo_cx = None
    objetivo_cy = None
    perdidos = 0

    fire_detected = False
    alineado_desde = None

    ultimo_pan_ref = None
    ultimo_tilt_ref = None
    ultimo_objetivo_y = None


# ======================================================
# INICIAR SCAN AUTO
#
# Robot quieto.
# PAN comienza a explorar el sector.
# ======================================================

def iniciar_scan_auto():
    global estado_auto, estado_vision
    global auto_scan_inicio
    global auto_saturation_frames, auto_corrections

    auto_saturation_frames = 0
    pump.off()
    reset_objetivo()

    estado_auto = AUTO_SCAN
    estado_vision = config.SEARCH

    # El scan comienza desde la posicion PAN actual.
    pan.scan_angle = pan.pan_angle

    auto_scan_inicio = time.ticks_ms()

    print("[AUTO] SCAN DE SECTOR INICIADO")


# ======================================================
# CAMBIO DE MODO
# ======================================================

def set_mode(new_mode):
    global modo, estado_vision
    global estado_auto, auto_calibracion_pendiente
    global auto_saturation_frames, auto_corrections
    global ultimo_cambio_ref, ultimo_cambio_objetivo

    if new_mode == modo:
        return

    pump.off()
    reset_objetivo()

    modo = new_mode
    estado_vision = config.SEARCH

    ahora = time.ticks_ms()
    ultimo_cambio_ref = ahora
    ultimo_cambio_objetivo = ahora

    auto_calibracion_pendiente = False
    auto_saturation_frames = 0
    auto_corrections = 0

    # SEMI usa su SEARCH tradicional con PAN.
    if modo == "SEMI":
        pan.cx_filtrado = config.IMG_CX
        pan.scan_angle = pan.pan_angle
        tilt.reset_position()

        print("MODO SEMI - SEARCH PAN")
        return

    # AUTO tiene su propia maquina de estados.
    if modo == "AUTO":
        estado_auto = AUTO_SCAN

        pan.cx_filtrado = config.IMG_CX
        tilt.reset_position()

        iniciar_scan_auto()

        print("MODO AUTO - EXPLORACION POR SECTORES")
        return

    print("MODO MANUAL")


# ======================================================
# E-STOP
# ======================================================

def activar_estop():
    global estop_activo, estado_auto
    global auto_saturation_frames, auto_corrections

    auto_saturation_frames = 0
    auto_corrections = 0
    estop_activo = True
    estado_auto = AUTO_SCAN

    pump.off()
    reset_objetivo()

    print("[SEGURIDAD] ESTOP ACTIVO")


def rearmar_estop():
    global estop_activo

    estop_activo = False
    set_mode("MANUAL")
    pump.off()

    print("[SEGURIDAD] REARME CONFIRMADO; MODO MANUAL")


# ======================================================
# PING / PONG
# ======================================================

def update_uart_test():
    global ultimo_ping

    ahora = time.ticks_ms()

    if time.ticks_diff(ahora, ultimo_ping) < PING_INTERVAL:
        return

    ultimo_ping = ahora

    camera_uart.send("PING")
    print("[UART] OPENMV -> C3: PING")


# ======================================================
# UART RX
# ======================================================

def update_uart():
    global ultimo_pong
    global estado_auto
    global auto_scan_inicio
    global auto_calibracion_pendiente
    global auto_correction_settle_at, auto_saturation_frames
    global auto_extra_turn_pending

    while True:
        message = camera_uart.receive()

        if message is None:
            break

        if message == "PONG":
            ultimo_pong = time.ticks_ms()
            continue

        print("C3 -> OPENMV:", message)

        # E-STOP tiene prioridad absoluta.
        if message in ("ESTOP", "ESTOP_ACTIVE"):
            activar_estop()
            continue

        if message == "MODE=MANUAL":
            if estop_activo:
                rearmar_estop()
            else:
                set_mode("MANUAL")

        elif message == "ESTOP_CLEARED":
            rearmar_estop()

        elif message == "MODE=SEMI":
            if not estop_activo:
                set_mode("SEMI")

        elif message == "MODE=AUTO":
            if not estop_activo:
                set_mode("AUTO")

        elif message == "AUTO_TURN_STARTED":
            if modo != "AUTO" or estado_auto != AUTO_WAIT_TURN:
                continue
            estado_auto = AUTO_WAIT_TURN
            print("[AUTO] GIRO DEL CHASIS INICIADO")

        elif message == "AUTO_TURN_TIME_DONE":
            if modo == "AUTO" and estado_auto == AUTO_WAIT_CORRECTION:
                estado_auto = AUTO_SETTLE_CORRECTION
                auto_correction_settle_at = time.ticks_ms()
                auto_saturation_frames = 0
                reset_objetivo()
                print("[AUTO] CORRECCION TERMINADA; OBSERVANDO")
            elif modo == "AUTO" and estado_auto == AUTO_WAIT_TURN:
                # Tras un giro extra, conservar el contador de intentos.
                # Volver a buscar el blob sin asumir que sigue visible.
                if auto_extra_turn_pending:
                    auto_extra_turn_pending = False
                    estado_auto = AUTO_SETTLE_CORRECTION
                    auto_correction_settle_at = time.ticks_ms()
                    auto_saturation_frames = 0
                    reset_objetivo()
                    print("[AUTO] GIRO EXTRA TERMINADO; REVISANDO OBJETIVO")
                else:
                    iniciar_scan_auto()
                    print("[AUTO] GIRO DE SECTOR TERMINADO")

        elif message in (
            "AUTO_TURN_NEEDS_CALIBRATION",
            "AUTO_SCAN_COMPLETE",
            "AUTO_REJECTED_MODE",
            "AUTO_TRANSLATION_NOT_READY"
        ):
            pump.off()

            auto_calibracion_pendiente = True
            camera_uart.send("AUTO_STOP")

            print("[AUTO] PAUSADO:", message)

        elif message == "AUTO_STOPPED":
            pass


# ======================================================
# VIDEO
# ======================================================

def update_client():
    global client

    if client is not None:
        return

    try:
        new_client, address = server.accept()

        print("Cliente conectado:", address)

        try:
            new_client.settimeout(0.2)
            new_client.recv(1024)
        except:
            pass

        header = (
            "HTTP/1.1 200 OK\r\n"
            "Server: OpenMV\r\n"
            "Cache-Control: no-cache\r\n"
            "Pragma: no-cache\r\n"
            "Connection: close\r\n"
            "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            "\r\n"
        )

        new_client.send(header)
        new_client.settimeout(0.05)

        client = new_client

    except OSError:
        pass


# ======================================================
# HUD
# ======================================================

def draw_interface(img, blob=None):
    cx = img.width() // 2
    cy = img.height() // 2

    # Reticula.
    img.draw_line((cx - 38, cy, cx - 8, cy),
                  color=(0, 255, 0), thickness=2)
    img.draw_line((cx + 8, cy, cx + 38, cy),
                  color=(0, 255, 0), thickness=2)
    img.draw_line((cx, cy - 38, cx, cy - 8),
                  color=(0, 255, 0), thickness=2)
    img.draw_line((cx, cy + 8, cx, cy + 38),
                  color=(0, 255, 0), thickness=2)

    img.draw_circle((cx, cy, 4),
                    color=(0, 255, 0), thickness=2)
    img.draw_circle((cx, cy, 2),
                    color=(0, 255, 0), fill=True)

    # Modo.
    img.draw_rectangle((6, 6, 100, 28),
                       color=(0, 0, 0), fill=True)
    img.draw_string((12, 10), modo,
                    color=(0, 255, 0), scale=2)

    # SEARCH / TRACK.
    if modo in ("SEMI", "AUTO"):
        estado_texto = (
            "SEARCH"
            if estado_vision == config.SEARCH
            else "TRACK"
        )

        img.draw_rectangle((6, 40, 82, 18),
                           color=(0, 0, 0), fill=True)

        img.draw_string((10, 43), estado_texto,
                        color=(0, 255, 0), scale=1)

    # UART.
    uart_ok = (
        ultimo_pong != 0 and
        time.ticks_diff(time.ticks_ms(), ultimo_pong)
        < PONG_MAX_AGE_MS
    )

    uart_text = "UART OK" if uart_ok else "UART ?"

    img.draw_rectangle((230, 6, 84, 20),
                       color=(0, 0, 0), fill=True)

    img.draw_string((236, 9), uart_text,
                    color=(0, 255, 0), scale=1)

    # Objetivo.
    if blob is not None:
        img.draw_rectangle(
            blob.rect,
            color=(0, 255, 0),
            thickness=2
        )

        img.draw_cross(
            (blob.cx, blob.cy),
            color=(0, 255, 0),
            size=8,
            thickness=2
        )

    # Telemetria.
    if modo in ("SEMI", "AUTO"):
        pan_ref = pan.controller_to_c3(pan.pan_angle)
        tilt_ref = tilt.tilt_angle

        pan_text = "PAN  %.1f" % pan_ref
        tilt_text = "TILT %.1f" % tilt_ref
        bomba_text = "PUMP ON" if pump._enabled else "PUMP OFF"

    else:
        pan_text = "PAN  --"
        tilt_text = "TILT --"
        bomba_text = "PUMP --"

    hud_x = cx + 45
    hud_y = cy + 8
    hud_color = (0, 255, 0)

    # Solo letras verdes.
    img.draw_string((hud_x, hud_y), pan_text,
                    color=hud_color, scale=1)

    img.draw_string((hud_x, hud_y + 14), tilt_text,
                    color=hud_color, scale=1)

    img.draw_string((hud_x, hud_y + 28), bomba_text,
                    color=hud_color, scale=1)


# ======================================================
# STREAM
# ======================================================

def stream_frame(img):
    global client

    if client is None:
        return

    try:
        jpg = img.compress(quality=45)

        client.send(b"--frame\r\n")
        client.send(b"Content-Type: image/jpeg\r\n")

        header = "Content-Length: %d\r\n\r\n" % len(jpg)
        client.send(header.encode())

        client.send(jpg)
        client.send(b"\r\n")

    except OSError:
        try:
            client.close()
        except:
            pass

        client = None


# ======================================================
# SELECCION DE OBJETIVO
# ======================================================

def seleccionar_objetivo(blobs):
    global objetivo_cx, objetivo_cy

    if not blobs:
        return None

    # Primera adquisicion: blob con mas pixeles.
    if objetivo_cx is None:
        elegido = max(blobs, key=lambda b: b.pixels)

    # Tracking: conservar el blob cercano al anterior.
    else:
        candidatos = []

        for b in blobs:
            dx = b.cx - objetivo_cx
            dy = b.cy - objetivo_cy

            if (
                dx * dx + dy * dy
                <= config.BLOB_MAX_JUMP_PX ** 2
            ):
                candidatos.append(b)

        if not candidatos:
            return None

        elegido = min(
            candidatos,
            key=lambda b:
                (b.cx - objetivo_cx) ** 2 +
                (b.cy - objetivo_cy) ** 2
        )

    objetivo_cx = elegido.cx
    objetivo_cy = elegido.cy

    return elegido


# ======================================================
# TRACKING IBVS COMUN
#
# No realiza SEARCH.
# SEMI y AUTO lo reutilizan una vez adquirido el fuego.
#
# Retorno:
# blob  -> objetivo presente
# False -> perdida momentanea
# None  -> perdida confirmada
# ======================================================

def tracking_ibvs(blobs):
    global estado_vision, fire_detected
    global ultimo_error_x, ultimo_error_y
    global objetivo_cx, objetivo_cy, perdidos
    global alineado_desde
    global ultimo_cambio_ref
    global ultimo_pan_ref, ultimo_tilt_ref
    global ultimo_objetivo_y, ultimo_cambio_objetivo

    ahora = time.ticks_ms()
    elegido = seleccionar_objetivo(blobs)

    # Objetivo no visible.
    if elegido is None:
        pump.off()
        alineado_desde = None
        ultimo_objetivo_y = None

        perdidos += 1

        if perdidos >= config.BLOB_LOST_FRAMES:
            objetivo_cx = None
            objetivo_cy = None
            perdidos = 0
            fire_detected = False

            return None

        return False

    # Objetivo presente.
    perdidos = 0
    estado_vision = config.TRACKING
    fire_detected = True

    estado_vision, pan_data = pan.tracking(
        [elegido],
        config.TRACKING,
        config.IMG_CX,
        config.ALPHA,
        config.KP,
        config.DEADBAND,
        config.MAX_STEP
    )

    if pan_data is None:
        pump.off()
        alineado_desde = None
        return elegido

    ultimo_error_x = pan_data["error"]

    # TILT calcula el angulo de la manguera.
    _, ultimo_error_y, _, tilt_target = tilt.track(elegido.cy)

    # Estabilidad vertical.
    if (
        ultimo_objetivo_y is None or
        abs(elegido.cy - ultimo_objetivo_y) > TARGET_STABLE_PX
    ):
        ultimo_cambio_objetivo = ahora

    ultimo_objetivo_y = elegido.cy

    # Estabilidad de referencias.
    ref_pan = pan.controller_to_c3(pan.pan_angle)
    ref_tilt = tilt_target

    if (
        ultimo_pan_ref is None or
        ultimo_tilt_ref is None or
        abs(ref_pan - ultimo_pan_ref) > REF_EPSILON_DEG or
        abs(ref_tilt - ultimo_tilt_ref) > 3.0
    ):
        ultimo_cambio_ref = ahora

    ultimo_pan_ref = ref_pan
    ultimo_tilt_ref = ref_tilt

    pan_aligned = abs(ultimo_error_x) <= config.DEADBAND

    uart_ok = (
        ultimo_pong != 0 and
        time.ticks_diff(ahora, ultimo_pong) < PONG_MAX_AGE_MS
    )

    if not pan_aligned or not uart_ok:
        alineado_desde = None
        pump.off()
        return elegido

    if alineado_desde is None:
        alineado_desde = ahora

    alineacion_ms = time.ticks_diff(ahora, alineado_desde)
    refs_estables_ms = time.ticks_diff(ahora, ultimo_cambio_ref)

    if (
        BOMBA_HABILITADA and
        (modo == "SEMI" or (modo == "AUTO" and estado_auto == AUTO_TRACK)) and
        alineacion_ms >= PUMP_ALIGN_MS and
        refs_estables_ms >= SERVO_SETTLE_MS and
        not estop_activo
    ):
        pump.on()
    else:
        pump.off()

    return elegido


# ======================================================
# SEMI
#
# SEARCH: PAN barre continuamente.
# TRACK : IBVS.
# ======================================================

def update_semi(blobs):
    global estado_vision, fire_detected
    global objetivo_cx, objetivo_cy, perdidos
    global ultimo_cambio_ref, ultimo_cambio_objetivo
    global ultimo_pan_ref, ultimo_tilt_ref
    global alineado_desde, ultimo_objetivo_y

    # SEARCH SEMI.
    if estado_vision == config.SEARCH:
        pump.off()
        alineado_desde = None
        ultimo_objetivo_y = None

        elegido = seleccionar_objetivo(blobs)

        if elegido is None:
            pan.search([], config.SEARCH)
            return None

        estado_vision = config.TRACKING

        pan.cx_filtrado = elegido.cx
        tilt.cy_filtrado = elegido.cy

        ahora = time.ticks_ms()

        ultimo_cambio_ref = ahora
        ultimo_cambio_objetivo = ahora

        ultimo_pan_ref = None
        ultimo_tilt_ref = None

        perdidos = 0
        fire_detected = True

        print("OBJETIVO ADQUIRIDO")

        return elegido

    # TRACKING SEMI.
    resultado = tracking_ibvs(blobs)

    if resultado is None:
        print("OBJETIVO PERDIDO - SEARCH")

        estado_vision = config.SEARCH
        pan.scan_angle = pan.pan_angle

        return None

    if resultado is False:
        return None

    return resultado


# ======================================================
# AUTO
#
# AUTO_SCAN:
#   Robot quieto.
#   PAN barre el sector.
#
# AUTO_TRACK:
#   Fuego detectado.
#   Robot permanece quieto.
#   PAN/TILT ejecutan IBVS.
#
# AUTO_WAIT_TURN:
#   Chasis realiza el giro de sector.
#   La vision no toma decisiones hasta que termine.
# ======================================================

def update_auto(blobs):
    global estado_auto, estado_vision
    global auto_scan_inicio, auto_giro_solicitado_en
    global auto_calibracion_pendiente
    global fire_detected, perdidos
    global ultimo_cambio_ref, ultimo_cambio_objetivo
    global ultimo_pan_ref, ultimo_tilt_ref
    global auto_saturation_frames, auto_corrections
    global auto_correction_settle_at, alineado_desde
    global auto_extra_turn_pending

    ahora = time.ticks_ms()

    if auto_calibracion_pendiente:
        pump.off()
        return None

    # ==================================================
    # ESPERANDO GIRO DEL CHASIS
    # ==================================================

    if estado_auto == AUTO_WAIT_TURN:
        pump.off()

        if (
            time.ticks_diff(ahora, auto_giro_solicitado_en)
            > AUTO_TURN_TIMEOUT_MS
        ):
            camera_uart.send("AUTO_STOP")
            auto_calibracion_pendiente = True

            print("[AUTO] TIMEOUT DE GIRO; PAUSADO")

        return None

    # ==================================================
    # ESPERANDO GIRO CORRECTIVO DEL CHASIS
    # ==================================================
    if estado_auto == AUTO_WAIT_CORRECTION:
        pump.off()
        if time.ticks_diff(ahora, auto_giro_solicitado_en) > AUTO_TURN_TIMEOUT_MS:
            camera_uart.send("AUTO_STOP")
            auto_calibracion_pendiente = True
            print("[AUTO] TIMEOUT CORRECCION; PAUSADO")
        return None

    # Esperar que termine la vibracion del chasis.
    if estado_auto == AUTO_SETTLE_CORRECTION:
        pump.off()
        if time.ticks_diff(ahora, auto_correction_settle_at) < AUTO_CORRECTION_SETTLE_MS:
            return None
        # Reacquirir el objetivo con el mismo detector de SEMI.
        # Si no hay blob, volver al barrido en lugar de seguir un blanco viejo.
        elegido_nuevo = seleccionar_objetivo(blobs)
        if elegido_nuevo is None:
            iniciar_scan_auto()
            return None
        pan.cx_filtrado = elegido_nuevo.cx
        tilt.cy_filtrado = elegido_nuevo.cy
        estado_auto = AUTO_TRACK
        alineado_desde = None

    # ==================================================
    # TRACKING AUTO
    # ==================================================

    if estado_auto == AUTO_TRACK:
        resultado = tracking_ibvs(blobs)

        # Objetivo perdido definitivamente.
        if resultado is None:
            print("[AUTO] OBJETIVO PERDIDO - NUEVO SCAN")

            iniciar_scan_auto()
            return None

        if resultado is False:
            auto_saturation_frames = 0
            return None

        # ==================================================
        # CORRECCION CON GIRO COMPLETO DE BUSQUEDA (1100 ms)
        #
        # No usar giros cortos. El ESP32 principal ejecuta
        # AUTO_SCAN_90 con su temporizador de 1100 ms.
        # Solo pedirlo cuando PAN este saturado Y el error
        # intente seguir moviendolo fuera de su recorrido.
        # El offset se mantiene en -80 px respecto al centro.
        # Para imagen QVGA, la referencia absoluta es X=80.
        # ==================================================
        pan_left_limit = (pan.pan_angle <=
                          config.SCAN_MIN + AUTO_PAN_LIMIT_MARGIN_DEG)
        pan_right_limit = (pan.pan_angle >=
                           config.SCAN_MAX - AUTO_PAN_LIMIT_MARGIN_DEG)

        requiere_otro_giro = (
            (pan_left_limit and ultimo_error_x < -config.DEADBAND) or
            (pan_right_limit and ultimo_error_x > config.DEADBAND)
        )

        if requiere_otro_giro:
            auto_saturation_frames += 1
        else:
            auto_saturation_frames = 0

        if auto_saturation_frames >= AUTO_PAN_LIMIT_FRAMES:
            pump.off()
            alineado_desde = None

            # Limite de seguridad ante objetivo inalcanzable.
            if auto_corrections >= AUTO_MAX_CORRECTIONS:
                camera_uart.send("AUTO_STOP")
                auto_calibracion_pendiente = True
                print("[AUTO] MAXIMO DE GIROS EXTRA; PAUSADO")
                return resultado

            auto_corrections += 1
            auto_saturation_frames = 0
            estado_auto = AUTO_WAIT_TURN
            auto_extra_turn_pending = True
            auto_giro_solicitado_en = ahora
            camera_uart.send("AUTO_SCAN_90")
            print("[AUTO] GIRO EXTRA CW 1100 ms", auto_corrections)

        return resultado

    # ==================================================
    # SCAN AUTO
    # ==================================================

    pump.off()
    estado_vision = config.SEARCH

    elegido = seleccionar_objetivo(blobs)

    # --------------------------------------------------
    # FUEGO ENCONTRADO DURANTE EL BARRIDO
    # --------------------------------------------------

    if elegido is not None:
        estado_auto = AUTO_TRACK
        estado_vision = config.TRACKING

        fire_detected = True
        perdidos = 0

        pan.cx_filtrado = elegido.cx
        tilt.cy_filtrado = elegido.cy

        ultimo_cambio_ref = ahora
        ultimo_cambio_objetivo = ahora

        ultimo_pan_ref = None
        ultimo_tilt_ref = None

        # El robot ya esta quieto durante SCAN.
        # AUTO_FIRE_FOUND refuerza STOP en el principal.
        camera_uart.send("AUTO_FIRE_FOUND")

        print("[AUTO] FUEGO DETECTADO - TRACKING")

        return elegido

    # --------------------------------------------------
    # SIN FUEGO: CONTINUAR BARRIDO PAN
    # --------------------------------------------------

    pan.search([], config.SEARCH)

    # Todavia no termino la ventana de exploracion.
    if (
        time.ticks_diff(ahora, auto_scan_inicio)
        < AUTO_SCAN_TIME_MS
    ):
        return None

    # --------------------------------------------------
    # SCAN TERMINADO SIN FUEGO
    # -> GIRAR CHASIS AL SIGUIENTE SECTOR
    # --------------------------------------------------

    pump.off()

    camera_uart.send("AUTO_SCAN_90")

    estado_auto = AUTO_WAIT_TURN
    auto_giro_solicitado_en = ahora

    print("[AUTO] SCAN SIN FUEGO - SOLICITADO GIRO 90")

    return None


# ======================================================
# SISTEMA LISTO
# ======================================================

print()
print("==============================")
print("SISTEMA LISTO")
print("==============================")
print("IP:", OPENMV_IP)
print("STREAM: http://%s:%d" % (OPENMV_IP, STREAM_PORT))
print("UART3 P4/P5")
print("PING/PONG habilitado")
print()


# ======================================================
# LOOP
# ======================================================

while True:

    # Comunicacion.
    update_uart_test()
    update_uart()

    # Video.
    update_client()

    # Captura y deteccion.
    img = vision.snapshot()

    blobs = vision.find_blobs(
        img,
        config.WHITE_THRESHOLD,
        config.PIXELS_THRESHOLD,
        config.AREA_THRESHOLD,
        config.MERGE
    )

    display_blob = None

    # MANUAL: vision pasiva.
    if blobs and modo == "MANUAL":
        display_blob = max(blobs, key=lambda b: b.pixels)

    # E-STOP: ninguna actuacion.
    if estop_activo:
        pump.off()

    elif modo == "MANUAL":
        pump.off()

    elif modo == "SEMI":
        tracking_blob = update_semi(blobs)

        if tracking_blob is not None:
            display_blob = tracking_blob

    elif modo == "AUTO":
        tracking_blob = update_auto(blobs)

        if tracking_blob is not None:
            display_blob = tracking_blob

    # HUD + stream.
    draw_interface(img, display_blob)
    stream_frame(img)

    time.sleep_ms(5)
