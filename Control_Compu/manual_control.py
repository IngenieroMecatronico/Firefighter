import socket
import msvcrt
import time

# ============================================================
# CONFIGURACION
# ============================================================

ESP32_IP = "192.168.50.171"
ESP32_PORT = 12345
LOCAL_PORT = 12346

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

sock.settimeout(0.02)


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


def receive():

    try:

        data, addr = sock.recvfrom(2048)

        return data.decode(
            errors="replace"
        )

    except socket.timeout:

        return None


# ============================================================
# CONECTAR CON ESP32
# ============================================================

print()
print("========================================")
print("          OMNIBOT - CONTROL")
print("========================================")
print()

print("Buscando ESP32...")

send("ping")

connected = False

for _ in range(30):

    response = receive()

    if response == "pong":

        connected = True
        break

    time.sleep(0.05)


if not connected:

    print("ERROR: ESP32 no responde.")

    sock.close()

    raise SystemExit


print("ESP32 conectado.")


# ============================================================
# ARRANQUE EN MANUAL
# ============================================================

speed = 30

# El ESP32 arranca en E-STOP: esperar confirmacion antes de mover.

pump_enabled = False
emergency_enabled = False  # Estado solicitado, no confirmacion del C3
estop_active = True         # El firmware arranca bloqueado
reset_pending = False
last_toggle_time = 0.0
TOGGLE_DEBOUNCE_S = 0.45

# No enviar modo ni velocidad hasta confirmar el rearme.

# ============================================================
# CONTROLES
# ============================================================

print()
print("========================================")
print("MODOS")
print("========================================")
print()
print("1 = MANUAL")
print("2 = SEMIAUTOMATICO")
print("3 = AUTOMATICO")
print()
print("========================================")
print("LOCOMOCION")
print("========================================")
print()
print("W = Adelante")
print("S = Atras")
print("A = Izquierda")
print("D = Derecha")
print("Q = Giro antihorario")
print("E = Giro horario")
print()
print("SPACE = STOP")
print()
print("+ / - = Velocidad")
print()
print("========================================")
print("TORRETA - SOLO MANUAL")
print("========================================")
print()
print("Flecha izquierda  = PAN izquierda")
print("Flecha derecha    = PAN derecha")
print("Flecha arriba     = TILT arriba")
print("Flecha abajo      = TILT abajo")
print()
print("C = Centrar torreta")
print("B = Bomba ON/OFF")
print("T = Luces de emergencia + sirena (triangulo PS4)")
print()
print("========================================")
print("DIAGNOSTICO")
print("========================================")
print()
print("P = Camera PING")
print("X = ESTOP")
print("R = Solicitar rearme E-STOP")
print("Al conectar: pulsa R y espera OK ESTOP_CLEARED")
print("ESC = Salir")
print()
print("Velocidad inicial:", speed, "RPM")
print()
print("========================================")
print()


# ============================================================
# MOVIMIENTOS
# ============================================================

movement_commands = {

    b'w': "forward",
    b's': "backward",
    b'a': "left",
    b'd': "right",
    b'q': "rotate_ccw",
    b'e': "rotate_cw"
}


movement_names = {

    "forward": "ADELANTE",
    "backward": "ATRAS",
    "left": "IZQUIERDA",
    "right": "DERECHA",
    "rotate_ccw": "GIRO CCW",
    "rotate_cw": "GIRO CW"
}


# ============================================================
# LOOP
# ============================================================

try:

    while True:

        # ====================================================
        # MENSAJES ESP32 / OPENMV
        # ====================================================

        response = receive()

        if response:

            # El rearme se confirma desde el ESP32 principal.
            if response == "OK ESTOP_CLEARED":
                estop_active = False
                reset_pending = False
                pump_enabled = False
                emergency_enabled = False
                send("mode=manual")
                send(f"speed={speed}")
                print("\nE-STOP REARMADO: modo MANUAL habilitado")
            elif response == "OK ESTOP_ALREADY_CLEARED":
                estop_active = False
                reset_pending = False
                send("mode=manual")
                send(f"speed={speed}")
                print("\nE-STOP ya estaba liberado: modo MANUAL habilitado")
            elif response in ("ESTOP_ACTIVE", "OK ESTOP_ACTIVE") or response.endswith("ESTOP_ACTIVE"):
                estop_active = True
                reset_pending = False
                pump_enabled = False
                emergency_enabled = False

            # Mostrar especialmente mensajes de camara
            if response.startswith("CAMERA="):

                print()
                print(
                    "OPENMV:",
                    response[7:]
                )

            elif not response.startswith("OK "):

                print()
                print(
                    "ESP32:",
                    response
                )


        # ====================================================
        # TECLADO
        # ====================================================

        if not msvcrt.kbhit():

            continue


        key = msvcrt.getch()

        # Bloqueo local: nunca enviar movimiento, modo ni bomba
        # antes de que el principal confirme el rearme.
        if estop_active and key.lower() not in (b'r', b'x', b'p', b'\x1b'):
            print("\nBLOQUEADO: pulsa R y espera confirmacion E-STOP")
            continue

        # ====================================================
        # TECLAS ESPECIALES
        #
        # msvcrt devuelve:
        #
        # 0x00 o 0xE0
        # seguido del codigo de la flecha.
        # ====================================================

        if key in (b'\x00', b'\xe0'):

            special = msvcrt.getch()

            # -----------------------------------------------
            # ARRIBA
            # -----------------------------------------------

            if special == b'H':

                send(
                    "tilt_up"
                )

                print(
                    "\rTILT ARRIBA              ",
                    end="",
                    flush=True
                )

            # -----------------------------------------------
            # ABAJO
            # -----------------------------------------------

            elif special == b'P':

                send(
                    "tilt_down"
                )

                print(
                    "\rTILT ABAJO               ",
                    end="",
                    flush=True
                )

            # -----------------------------------------------
            # IZQUIERDA
            # -----------------------------------------------

            elif special == b'K':

                send(
                    "pan_left"
                )

                print(
                    "\rPAN IZQUIERDA             ",
                    end="",
                    flush=True
                )

            # -----------------------------------------------
            # DERECHA
            # -----------------------------------------------

            elif special == b'M':

                send(
                    "pan_right"
                )

                print(
                    "\rPAN DERECHA               ",
                    end="",
                    flush=True
                )

            continue


        # ====================================================
        # ESC
        # ====================================================

        if key == b'\x1b':

            send("stop")
            send("pump_off")

            print()
            print("Saliendo...")

            break


        # ====================================================
        # SPACE
        # ====================================================

        if key == b' ':

            send(
                "stop"
            )

            print(
                "\rSTOP                       ",
                end="",
                flush=True
            )

            continue


        key = key.lower()


        # ====================================================
        # MODOS
        # ====================================================

        if key == b'1':

            send(
                "mode=manual"
            )

            pump_enabled = False

            print()
            print(
                "MODO: MANUAL"
            )

            continue


        if key == b'2':

            send(
                "mode=semi"
            )

            pump_enabled = False

            print()
            print(
                "MODO: SEMIAUTOMATICO"
            )

            continue


        if key == b'3':

            send(
                "mode=auto"
            )

            pump_enabled = False

            print()
            print(
                "MODO: AUTOMATICO"
            )

            continue


        # ====================================================
        # MOVIMIENTO
        # ====================================================

        if key in movement_commands:

            command = \
                movement_commands[key]

            send(
                command
            )

            print(
                "\r" +
                movement_names[command] +
                "                       ",
                end="",
                flush=True
            )

            continue


        # ====================================================
        # VELOCIDAD +
        # ====================================================

        if key in (b'+', b'='):

            speed += 5

            if speed > 80:
                speed = 80

            send(
                f"speed={speed}"
            )

            print(
                f"\rVELOCIDAD = {speed} RPM       ",
                end="",
                flush=True
            )

            continue


        # ====================================================
        # VELOCIDAD -
        # ====================================================

        if key == b'-':

            speed -= 5

            if speed < 5:
                speed = 5

            send(
                f"speed={speed}"
            )

            print(
                f"\rVELOCIDAD = {speed} RPM       ",
                end="",
                flush=True
            )

            continue


        # ====================================================
        # CENTRAR TORRETA
        # ====================================================

        if key == b'c':

            send(
                "turret_center"
            )

            print(
                "\rCENTRANDO TORRETA          ",
                end="",
                flush=True
            )

            continue


        # ====================================================
        # BOMBA
        # ====================================================

        if key == b'b':

            pump_enabled = \
                not pump_enabled

            if pump_enabled:

                send(
                    "pump_on"
                )

                print(
                    "\rBOMBA ON                  ",
                    end="",
                    flush=True
                )

            else:

                send(
                    "pump_off"
                )

                print(
                    "\rBOMBA OFF                 ",
                    end="",
                    flush=True
                )

            continue


        # ====================================================
        # LUCES DE EMERGENCIA Y BUZZER (TRIANGULO PS4)
        #
        # Misma orden UDP que el control PS4:
        #   emergency_toggle -> ESP32 principal
        #   EMERGENCY_TOGGLE -> ESP32-C3
        #
        # No es E-STOP. El estado local es estimado:
        # el C3 debe confirmar el estado real.
        # ====================================================

        if key == b't':

            now = time.monotonic()
            if now - last_toggle_time < TOGGLE_DEBOUNCE_S:
                continue
            last_toggle_time = now
            send("emergency_toggle")
            emergency_enabled = not emergency_enabled

            print()
            print("LUCES + SIRENA: comando TOGGLE enviado")
            print("Estado solicitado:",
                  "ON" if emergency_enabled else "OFF")

            continue

        # ====================================================
        # SOLICITAR REARME DEL E-STOP
        # El ESP32 y C3 validan el rearme.
        # ====================================================

        if key == b'r':
            if reset_pending:
                print("\nRearme solicitado; esperando confirmacion del C3")
                continue
            reset_pending = True
            send("estop_reset")
            print()
            print("Solicitando ESTOP_RESET; esperando confirmacion")
            continue

        # ====================================================
        # CAMERA PING
        # ====================================================

        if key == b'p':

            print()
            print(
                "Enviando PING a OpenMV..."
            )

            send(
                "camera_ping"
            )

            continue


        # ====================================================
        # ESTOP
        # ====================================================

        if key == b'x':

            send(
                "estop"
            )

            pump_enabled = False
            emergency_enabled = False
            estop_active = True
            reset_pending = False

            print()
            print(
                "!!! ESTOP !!!"
            )

            continue


except KeyboardInterrupt:

    send("stop")
    send("pump_off")


finally:

    send("stop")
    send("pump_off")

    sock.close()