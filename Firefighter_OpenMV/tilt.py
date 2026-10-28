# ======================================================
# FIREFIGHTER - OPENMV H7 R2
# ARCHIVO: tilt.py
#
# TILT: MAPEO DIRECTO DE PIXELES A GRADOS
# CAMARA FIJA / MANGUERA MOVIL
# ======================================================

import config
import camera_uart

TILT_MIN = 50.0
TILT_MAX = 180.0
TILT_HOME = 115.0

# Factor de conversion grados/pixel
KH = 0.30

# Cambiar a -1.0 si el sentido fisico es inverso
DIRECCION = 1.0

cy_filtrado = config.IMG_CY
tilt_angle = TILT_HOME


def send_target():
    camera_uart.send(
        "TILT_TARGET={:.1f}".format(tilt_angle)
    )


def reset_position():
    global cy_filtrado, tilt_angle

    cy_filtrado = config.IMG_CY
    tilt_angle = TILT_HOME

    send_target()


def track(cy_raw):
    global cy_filtrado, tilt_angle

    # Filtro EMA
    cy_filtrado = (
        config.ALPHA * cy_filtrado
        + (1.0 - config.ALPHA) * cy_raw
    )

    # Error vertical en pixeles
    H = cy_filtrado - config.IMG_CY

    # Mapeo directo a grados
    objetivo = TILT_HOME + DIRECCION * KH * H

    # Limites del servo
    tilt_angle = max(
        TILT_MIN,
        min(TILT_MAX, objetivo)
    )

    send_target()

    return (
        cy_filtrado,
        H,
        tilt_angle,
        tilt_angle
    )
