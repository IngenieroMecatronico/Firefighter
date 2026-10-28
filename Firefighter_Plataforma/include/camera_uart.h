#ifndef CAMERA_UART_H
#define CAMERA_UART_H

#include <Arduino.h>

//============================================================
// FIREFIGHTER
// UART ESP32 PRINCIPAL <-> ESP32-C3
//============================================================

void camera_uart_init();

void camera_uart_update();

void camera_uart_send(
    const String &message
);

bool camera_uart_available();

String camera_uart_get_message();

#endif