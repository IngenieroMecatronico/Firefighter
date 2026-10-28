import socket
import pygame
import time
# ============================================================
# CONFIGURACION DE RED
# ============================================================
ESP32_IP = "192.168.50.171"
ESP32_PORT = 12345
LOCAL_PORT = 12346
# ============================================================
# MAPEO DUALSHOCK 4
# ============================================================
# ============================================================
# EJES CORRECTOS PARA PYGAME
# ============================================================
# Stick izquierdo
AXIS_LX = 0
AXIS_LY = 1
# Stick derecho
AXIS_RX = 2
AXIS_RY = 3
# Gatillos
AXIS_L2 = 4
AXIS_R2 = 5
# Botones
BTN_X = 0
BTN_CIRCLE = 1
BTN_SQUARE = 2
BTN_TRIANGLE = 3
BTN_SHARE = 4
BTN_PS = 5
BTN_OPTIONS = 6
BTN_L3 = 7
BTN_R3 = 8
BTN_L1 = 9
BTN_R1 = 10
BTN_UP = 11
BTN_DOWN = 12
BTN_LEFT = 13
BTN_RIGHT = 14
BTN_TOUCHPAD = 15
# ============================================================
# MODOS
# ============================================================
MODE_MANUAL = 0
MODE_SEMI = 1
MODE_AUTO = 2
# ============================================================
# PARAMETROS
# ============================================================
# Zona muerta de sticks
DEADZONE = 0.20
# RPM
MIN_RPM = 15
MAX_RPM = 80
# Reenvio de comandos de locomocion
# ESP32 tiene timeout de \~350 ms
MOVEMENT_INTERVAL = 0.10
# Frecuencia de movimiento PAN/TILT
TURRET_INTERVAL = 0.10
# Antirrebote adicional Touchpad
MODE_DEBOUNCE = 0.25

# Mantener PS 2 segundos para solicitar rearme.
PS_RESET_HOLD_S = 2.0
# Evita interpretar como pulsacion un boton ya presionado al arrancar.
OPTIONS_RELEASE_ARM_S = 0.30
# ============================================================
# UDP
# ============================================================
sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)
sock.bind(
    ("", LOCAL_PORT)
)
sock.setblocking(False)
# ============================================================
# FUNCIONES UDP
# ============================================================
def send(command):
    sock.sendto(
        command.encode(),
        (
            ESP32_IP,
            ESP32_PORT
        )
    )
def receive_all():
    while True:
        try:
            data, addr = sock.recvfrom(
                2048
            )
            message = data.decode(
                errors="replace"
            )
            global estop_latched
            if message == "ESTOP_ACTIVE" or message == "OK ESTOP_ACTIVE":
                if not estop_latched:
                    print("\nE-STOP ACTIVO")
                estop_latched = True
            elif message == "OK ESTOP_CLEARED":
                estop_latched = False
                send("mode=manual")
                send("speed=30")
                print("\nE-STOP REARMADO. MODO MANUAL; mandos en reposo.")

            # No repetir mensajes de ESTOP_ACTIVE en cada reintento.
            if message in ("ESTOP_ACTIVE", "OK ESTOP_ACTIVE", "CAMERA=ESTOP_ACTIVE"):
                continue

            # Mensajes provenientes de OpenMV
            if message.startswith("CAMERA="):
                print(
                    "\nOPENMV:",
                    message[7:]
                )
            # No mostrar todos los ACK normales
            elif not message.startswith("OK "):
                print(
                    "\nESP32:",
                    message
                )
        except BlockingIOError:
            break
# ============================================================
# PYGAME
# ============================================================
pygame.init()
pygame.joystick.init()
# ============================================================
# BUSCAR CONTROL
# ============================================================
if pygame.joystick.get_count() == 0:
    print()
    print("ERROR: No se encontro el control PS4.")
    print()
    sock.close()
    pygame.quit()
    raise SystemExit
controller = pygame.joystick.Joystick(0)
controller.init()
# ============================================================
# INFORMACION
# ============================================================
print()
print("========================================")
print("       OMNIBOT - CONTROL PS4")
print("========================================")
print()
print("Control:", controller.get_name())
print()
print("----------------------------------------")
print("LOCOMOCION")
print("----------------------------------------")
print()
print("Stick izquierdo:")
print("  Arriba     = Adelante")
print("  Abajo      = Atras")
print("  Izquierda  = Lateral izquierda")
print("  Derecha    = Lateral derecha")
print()
print("L2 = Giro antihorario")
print("R2 = Giro horario")
print()
print("----------------------------------------")
print("TORRETA - SOLO MANUAL")
print("----------------------------------------")
print()
print("Stick derecho:")
print("  Izquierda / derecha = PAN")
print("  Arriba / abajo      = TILT")
print()
print("X        = Bomba ON/OFF")
print("Cuadrado = Centrar torreta")
print("Triangulo = Luces de emergencia + sirena ON/OFF")
print()
print("----------------------------------------")
print("MODOS")
print("----------------------------------------")
print()
print("Touchpad:")
print("  MANUAL -> SEMI -> AUTO -> MANUAL...")
print()
print("----------------------------------------")
print("SEGURIDAD")
print("----------------------------------------")
print()
print("Circulo = STOP locomocion")
print("OPTIONS = ESTOP")
print("Ctrl+C  = Salir")
print()
print("========================================")
print()
# ============================================================
# CONECTAR CON ESP32
# ============================================================
print("Buscando ESP32...")
send(
    "ping"
)
connected = False
start_time = time.time()
while time.time() - start_time < 3.0:
    try:
        data, addr = sock.recvfrom(
            2048
        )
        response = data.decode(
            errors="replace"
        )
        if response == "pong":
            connected = True
            break
    except BlockingIOError:
        pass
    time.sleep(
        0.02
    )
if not connected:
    print()
    print("ERROR: ESP32 no responde.")
    print()
    controller.quit()
    pygame.quit()
    sock.close()
    raise SystemExit
print("ESP32 conectado.")
print()
# ============================================================
# ESTADO
# ============================================================
robot_mode = MODE_MANUAL
pump_enabled = False
current_speed = 30
last_movement_time = 0.0
last_turret_time = 0.0
last_mode_change = 0.0
last_movement_command = None

# Seguridad: el C3 arranca bloqueado hasta rearme explicito.
estop_latched = True
ps_hold_start = None
ps_reset_sent = False
options_released_since = None
options_ready = False
# ============================================================
# ESTADO ANTERIOR DE BOTONES
#
# Permite detectar una sola pulsacion.
# ============================================================
previous_buttons = [
    bool(controller.get_button(i))
    for i in range(controller.get_numbuttons())
]
# ============================================================
# DETECTAR FLANCO DE BOTON
# ============================================================
def button_pressed(button):
    if button >= len(previous_buttons):
        return False
    current = bool(
        controller.get_button(
            button
        )
    )
    previous = previous_buttons[
        button
    ]
    previous_buttons[
        button
    ] = current
    return (
        current and
        not previous
    )
# ============================================================
# CONVERTIR STICK A RPM
# ============================================================
def axis_to_speed(value):
    magnitude = abs(
        value
    )
    if magnitude < DEADZONE:
        return 0
    # Quitar zona muerta y reescalar
    magnitude = (
        magnitude - DEADZONE
    ) / (
        1.0 - DEADZONE
    )
    rpm = (
        MIN_RPM +
        magnitude *
        (
            MAX_RPM -
            MIN_RPM
        )
    )
    return int(
        rpm
    )
# ============================================================
# ACTUALIZAR VELOCIDAD
# ============================================================
def set_speed(rpm):
    global current_speed
    rpm = int(
        rpm
    )
    if rpm < MIN_RPM:
        rpm = MIN_RPM
    if rpm > MAX_RPM:
        rpm = MAX_RPM
    # Evitar enviar speed por cambios insignificantes
    if abs(
        rpm -
        current_speed
    ) >= 3:
        current_speed = rpm
        send(
            "speed=" +
            str(
                current_speed
            )
        )
# ============================================================
# GATILLOS
#
# Medimos:
#
# reposo     = -1
# presionado = +1
# ============================================================
def trigger_pressed(value):
    return value > 0.20
# ============================================================
# GATILLO -> RPM
# ============================================================
def trigger_to_speed(value):
    # Convertir -1...+1 a 0...1
    normalized = (
        value + 1.0
    ) / 2.0
    if normalized < 0.0:
        normalized = 0.0
    if normalized > 1.0:
        normalized = 1.0
    rpm = (
        MIN_RPM +
        normalized *
        (
            MAX_RPM -
            MIN_RPM
        )
    )
    return int(
        rpm
    )
# ============================================================
# CAMBIO CICLICO DE MODO
#
# MANUAL -> SEMI -> AUTO -> MANUAL
# ============================================================
def next_mode():
    global robot_mode
    global pump_enabled
    global last_movement_command
    # --------------------------------------------------------
    # MANUAL -> SEMI
    # --------------------------------------------------------
    if robot_mode == MODE_MANUAL:
        send(
            "mode=semi"
        )
        robot_mode = MODE_SEMI
        pump_enabled = False
        last_movement_command = None
        print()
        print("========================================")
        print("MODO: SEMIAUTOMATICO")
        print("========================================")
        return
    # --------------------------------------------------------
    # SEMI -> AUTO
    # --------------------------------------------------------
    if robot_mode == MODE_SEMI:
        send(
            "mode=auto"
        )
        robot_mode = MODE_AUTO
        pump_enabled = False
        last_movement_command = None
        print()
        print("========================================")
        print("MODO: AUTOMATICO")
        print("========================================")
        return
    # --------------------------------------------------------
    # AUTO -> MANUAL
    # --------------------------------------------------------
    if robot_mode == MODE_AUTO:
        send(
            "mode=manual"
        )
        robot_mode = MODE_MANUAL
        pump_enabled = False
        last_movement_command = None
        print()
        print("========================================")
        print("MODO: MANUAL")
        print("========================================")
        return
# ============================================================
# ARRANQUE
# ============================================================
# El C3 inicia en bloqueo de seguridad. No mandar ordenes
# de modo o velocidad hasta recibir confirmacion de rearme.

print("MODO INICIAL: MANUAL")
print()
# ============================================================
# LOOP PRINCIPAL
# ============================================================
try:
    while True:
        # ====================================================
        # ACTUALIZAR PYGAME
        # ====================================================
        pygame.event.pump()
        # ====================================================
        # RESPUESTAS ESP32 / OPENMV
        # ====================================================
        receive_all()
        now = time.time()
        # ====================================================
        # TOUCHPAD
        #
        # CAMBIO DE MODO
        #
        # MANUAL -> SEMI -> AUTO -> MANUAL
        # ====================================================
        if button_pressed(
            BTN_TOUCHPAD
        ):
            if (
                now -
                last_mode_change
                >=
                MODE_DEBOUNCE
            ):
                last_mode_change = now
                next_mode()
        # ====================================================
        # CIRCULO
        #
        # STOP DE LOCOMOCION
        # ====================================================
        if button_pressed(
            BTN_CIRCLE
        ):
            send(
                "stop"
            )
            last_movement_command = None
            print()
            print("STOP")
        # ====================================================
        # OPTIONS
        #
        # ESTOP GENERAL
        # ====================================================
        # Solo aceptar un flanco nuevo despues de haber observado
        # OPTIONS liberado durante 300 ms. Esto evita pulsaciones
        # fantasma al conectar el mando.
        options_down = bool(controller.get_button(BTN_OPTIONS))
        if not options_down:
            if options_released_since is None:
                options_released_since = now
            if now - options_released_since >= OPTIONS_RELEASE_ARM_S:
                options_ready = True
        else:
            options_released_since = None

        options_edge = button_pressed(BTN_OPTIONS)
        if options_edge and options_ready:
            options_ready = False
            send("estop")
            estop_latched = True
            pump_enabled = False
            last_movement_command = None
            print("\n!!! ESTOP ACTIVADO - OPTIONS !!!")

        # ====================================================
        # PS - REARME SOLICITADO TRAS 2 SEGUNDOS
        # Se envia una sola vez por pulsacion sostenida.
        # ====================================================
        ps_down = bool(controller.get_button(BTN_PS))
        if ps_down:
            if ps_hold_start is None:
                ps_hold_start = now
                ps_reset_sent = False
            elif (estop_latched and not ps_reset_sent and
                  now - ps_hold_start >= PS_RESET_HOLD_S):
                send("estop_reset")
                ps_reset_sent = True
                print("\nSolicitando ESTOP_RESET; esperando confirmacion del C3")
        else:
            ps_hold_start = None
            ps_reset_sent = False

        # Bloqueo local: no procesar movimiento ni actuadores
        # mientras E-STOP permanezca activo.
        if estop_latched:
            time.sleep(0.01)
            continue

        # ====================================================
        # X
        #
        # BOMBA ON / OFF
        #
        # SOLO MANUAL
        # ====================================================
        if button_pressed(
            BTN_X
        ):
            if robot_mode == MODE_MANUAL:
                pump_enabled = (
                    not pump_enabled
                )
                if pump_enabled:
                    send(
                        "pump_on"
                    )
                    print()
                    print("BOMBA: ON")
                else:
                    send(
                        "pump_off"
                    )
                    print()
                    print("BOMBA: OFF")
            else:
                print()
                print(
                    "BOMBA: control manual "
                    "no disponible en este modo"
                )
        # ====================================================
        # CUADRADO
        #
        # CENTRAR TORRETA
        #
        # SOLO MANUAL
        # ====================================================
        if button_pressed(
            BTN_SQUARE
        ):
            if robot_mode == MODE_MANUAL:
                send(
                    "turret_center"
                )
                print()
                print("TORRETA: CENTRANDO")
            else:
                print()
                print(
                    "TORRETA: control manual "
                    "no disponible en este modo"
                )
        # ====================================================
        # TRIANGULO
        #
        # LUCES DE EMERGENCIA + SIRENA
        #
        # DISPONIBLE EN TODOS LOS MODOS
        # ====================================================
        if button_pressed(
            BTN_TRIANGLE
        ):
            send(
                "emergency_toggle"
            )
            print()
            print(
                "EMERGENCIA: TOGGLE"
            )
        # ====================================================
        # LOCOMOCION
        #
        # MANUAL -> PS4
        # SEMI   -> PS4
        # AUTO   -> bloqueado
        # ====================================================
        if robot_mode in (
            MODE_MANUAL,
            MODE_SEMI
        ):
            # ------------------------------------------------
            # LEER STICK + GATILLOS
            # ------------------------------------------------
            lx = controller.get_axis(
                AXIS_LX
            )
            ly = controller.get_axis(
                AXIS_LY
            )
            l2 = controller.get_axis(
                AXIS_L2
            )
            r2 = controller.get_axis(
                AXIS_R2
            )
            command = None
            speed = 0
            # =================================================
            # L2
            #
            # GIRO ANTIHORARIO
            # =================================================
            if trigger_pressed(
                l2
            ):
                command = \
                    "rotate_ccw"
                speed = \
                    trigger_to_speed(
                        l2
                    )
            # =================================================
            # R2
            #
            # GIRO HORARIO
            # =================================================
            elif trigger_pressed(
                r2
            ):
                command = \
                    "rotate_cw"
                speed = \
                    trigger_to_speed(
                        r2
                    )
            # =================================================
            # STICK IZQUIERDO
            # =================================================
            elif (
                abs(lx) > DEADZONE or
                abs(ly) > DEADZONE
            ):
                # --------------------------------------------
                # Elegir eje dominante
                # --------------------------------------------
                if abs(ly) >= abs(lx):
                    speed = axis_to_speed(
                        ly
                    )
                    # Arriba normalmente es negativo
                    if ly < 0:
                        command = \
                            "forward"
                    else:
                        command = \
                            "backward"
                else:
                    speed = axis_to_speed(
                        lx
                    )
                    if lx < 0:
                        command = \
                            "left"
                    else:
                        command = \
                            "right"
            # =================================================
            # ENVIAR MOVIMIENTO
            # =================================================
            if command is not None:
                # Velocidad proporcional
                set_speed(
                    speed
                )
                # --------------------------------------------
                # Reenviar cada 100 ms
                #
                # El ESP32 se detiene si pasan \~350 ms
                # sin recibir movimiento.
                # --------------------------------------------
                if (
                    command !=
                    last_movement_command
                    or
                    now -
                    last_movement_time
                    >=
                    MOVEMENT_INTERVAL
                ):
                    send(
                        command
                    )
                    last_movement_command = \
                        command
                    last_movement_time = \
                        now
            else:
                # Stick/gatillos en reposo.
                #
                # Dejamos actuar al failsafe del ESP32.
                last_movement_command = None
        # ====================================================
        # AUTO
        #
        # No permitir locomocion desde PS4.
        # ====================================================
        else:
            last_movement_command = None
        # ====================================================
        # TORRETA MANUAL
        #
        # STICK DERECHO
        #
        # SOLO MANUAL
        # ====================================================
        if robot_mode == MODE_MANUAL:
            rx = controller.get_axis(
                AXIS_RX
            )
            ry = controller.get_axis(
                AXIS_RY
            )
            # ------------------------------------------------
            # Limitar frecuencia PAN/TILT
            # ------------------------------------------------
            if (
                now -
                last_turret_time
                >=
                TURRET_INTERVAL
            ):
                turret_command = None
                # --------------------------------------------
                # Stick fuera de zona muerta
                # --------------------------------------------
                if (
                    abs(rx) > DEADZONE or
                    abs(ry) > DEADZONE
                ):
                    # ========================================
                    # PAN
                    # ========================================
                    if abs(rx) >= abs(ry):
                        if rx < 0:
                            turret_command = \
                                "pan_left"
                        else:
                            turret_command = \
                                "pan_right"
                    # ========================================
                    # TILT
                    # ========================================
                    else:
                        # Arriba normalmente es negativo
                        if ry < 0:
                            turret_command = \
                                "tilt_up"
                        else:
                            turret_command = \
                                "tilt_down"
                # --------------------------------------------
                # ENVIAR
                # --------------------------------------------
                if turret_command is not None:
                    send(
                        turret_command
                    )
                    last_turret_time = now
        # ====================================================
        # EVITAR USO EXCESIVO DE CPU
        # ====================================================
        time.sleep(
            0.01
        )
# ============================================================
# CTRL+C
# ============================================================
except KeyboardInterrupt:
    print()
    print("Interrupcion por teclado.")
# ============================================================
# SALIDA SEGURA
# ============================================================
finally:
    print()
    print("Deteniendo robot...")
    try:
        send(
            "stop"
        )
        send(
            "pump_off"
        )
    except:
        pass
    controller.quit()
    pygame.quit()
    sock.close()
    print(
        "Control PS4 finalizado."
    )
