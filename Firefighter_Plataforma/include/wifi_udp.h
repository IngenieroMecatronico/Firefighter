#ifndef WIFI_UDP_H
#define WIFI_UDP_H

#include <Arduino.h>

//============================================================
// INICIALIZAR WIFI + UDP
//============================================================

void wifi_udp_init();

//============================================================
// PROCESAR COMANDOS UDP
//============================================================

void process_udp_commands();

//============================================================
// ENVIAR ESTADO DEL ROBOT
//============================================================

void wifi_udp_send_status();

//============================================================
// FAILSAFE DE LOCOMOCION
//============================================================

void wifi_udp_safety_update();

//============================================================
// ENVIAR MENSAJES A LA PC
//============================================================

void wifi_udp_send_message(
    const String &message
);

//============================================================
// PROCESAR RESPUESTAS DEL ESP32-C3
//
// NUEVA FUNCION:
//
// - ESTOP_ACTIVE
// - ESTOP_CLEARED
// - Confirmaciones futuras del C3
//============================================================

void wifi_udp_handle_c3_message(
    const String &message
);

#endif // WIFI_UDP_H