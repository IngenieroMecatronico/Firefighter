# ======================================================
# Proyecto : Robot Extinguidor de Incendios IBVS
# Plataforma: OpenMV H7 R2
# Firmware  : OpenMV v5.0.0
# Archivo   : pump.py
# ======================================================

import time
import camera_uart


# ======================================================
# INTERVALOS
# ======================================================

# Renovacion mientras la bomba esta ON.
# C3 tiene watchdog de 1200 ms.
RENEW_INTERVAL_MS = 400

# Repeticion preventiva de PUMP_OFF.
# No saturar UART.
OFF_REPEAT_MS = 1000


# ======================================================
# ESTADO
# ======================================================

_enabled = False

_last_renew = 0

_last_off = 0


# ======================================================
# INICIALIZAR
# ======================================================

def init():

    global _enabled
    global _last_renew
    global _last_off

    _enabled = False
    _last_renew = 0

    ahora = time.ticks_ms()
    _last_off = ahora

    camera_uart.send(
        "PUMP_OFF"
    )


# ======================================================
# ENCENDER / RENOVAR
# ======================================================

def on():

    global _enabled
    global _last_renew

    ahora = time.ticks_ms()

    # Primer encendido
    if not _enabled:

        _enabled = True
        _last_renew = ahora

        camera_uart.send(
            "PUMP_ON"
        )

        return

    # Renovacion del watchdog del C3
    if time.ticks_diff(
        ahora,
        _last_renew
    ) >= RENEW_INTERVAL_MS:

        _last_renew = ahora

        camera_uart.send(
            "PUMP_ON"
        )


# ======================================================
# APAGAR
# ======================================================

def off():

    global _enabled
    global _last_renew
    global _last_off

    ahora = time.ticks_ms()

    # Si estaba encendida, apagar INMEDIATAMENTE.
    if _enabled:

        _enabled = False
        _last_renew = 0
        _last_off = ahora

        camera_uart.send(
            "PUMP_OFF"
        )

        return

    # Si ya estaba apagada, repetir PUMP_OFF
    # solo una vez por segundo como seguridad.
    if time.ticks_diff(
        ahora,
        _last_off
    ) >= OFF_REPEAT_MS:

        _last_off = ahora

        camera_uart.send(
            "PUMP_OFF"
        )
