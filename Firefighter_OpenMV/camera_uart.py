# ======================================================
# Proyecto : Robot Extinguidor de Incendios IBVS
# Plataforma: OpenMV H7 R2
# Archivo   : camera_uart.py
#
# OPENMV <-> ESP32-C3
#
# UART3:
# P4 = TX
# P5 = RX
# ======================================================

from machine import UART

import config


_uart = UART(
    config.UART_ID,
    baudrate=config.UART_BAUD
)

_rx_buffer = ""


# ======================================================
# ENVIAR
# ======================================================

def send(message):

    _uart.write(
        message + "\n"
    )


# ======================================================
# RECIBIR
# ======================================================

def receive():

    global _rx_buffer


    if _uart.any():

        data = _uart.read()


        if data:

            try:

                _rx_buffer += \
                    data.decode()

            except:

                return None


    if "\n" not in _rx_buffer:

        return None


    line, _rx_buffer = \
        _rx_buffer.split(
            "\n",
            1
        )


    return line.strip()
