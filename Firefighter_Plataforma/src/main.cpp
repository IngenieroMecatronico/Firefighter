#include <Arduino.h>

#include "quad_stepper.h"
#include "robot_motion.h"
#include "wifi_udp.h"
#include "camera_uart.h"
#include "auto_motion.h"

//============================================================
// FIREFIGHTER - ESP32 PRINCIPAL
//
// FUNCIONES:
// - Control de cuatro steppers
// - WiFi UDP / Control PS4
// - Modos MANUAL, SEMI y AUTO
// - UART con ESP32-C3
// - Navegacion automatica
// - Gestion de E-STOP
//
// UART0:
// GPIO1 TX -> C3 GPIO20 RX
// GPIO3 RX <- C3 GPIO21 TX
//============================================================

//============================================================
// SETPOINTS DE LOS CUATRO MOTORES
//============================================================

volatile float rpmSetpoints[4] =
{
    0.0f,
    0.0f,
    0.0f,
    0.0f
};

//============================================================
// SETUP
//============================================================

void setup()
{
    //--------------------------------------------------------
    // INICIALIZAR MOTORES
    //--------------------------------------------------------

    quad_stepper_init();

    //--------------------------------------------------------
    // INICIALIZAR LOCOMOCION
    //--------------------------------------------------------

    robot_motion_init();

    //--------------------------------------------------------
    // ARRANQUE SEGURO
    //--------------------------------------------------------

    enable_motors(false);

    //--------------------------------------------------------
    // NAVEGACION AUTOMATICA
    //--------------------------------------------------------

    auto_motion_init();

    //--------------------------------------------------------
    // WIFI + UDP
    //--------------------------------------------------------

    wifi_udp_init();

    //--------------------------------------------------------
    // UART MAIN <-> C3
    //--------------------------------------------------------

    camera_uart_init();

    delay(300);

    //--------------------------------------------------------
    // APAGAR BOMBA PREVENTIVAMENTE
    //--------------------------------------------------------

    camera_uart_send("PUMP_OFF");

    //--------------------------------------------------------
    // MODO INICIAL
    //--------------------------------------------------------

    camera_uart_send("MODE=MANUAL");

    // El sistema permanece bloqueado hasta
    // completar correctamente ESTOP_RESET.
}

//============================================================
// LOOP PRINCIPAL
//============================================================

void loop()
{
    //--------------------------------------------------------
    // 1. COMANDOS WIFI / PS4
    //--------------------------------------------------------

    process_udp_commands();

    //--------------------------------------------------------
    // 2. FAILSAFE Y E-STOP
    //--------------------------------------------------------

    wifi_udp_safety_update();

    //--------------------------------------------------------
    // 3. RECIBIR UART DEL C3
    //--------------------------------------------------------

    camera_uart_update();

    //--------------------------------------------------------
    // 4. PROCESAR TODOS LOS MENSAJES PENDIENTES
    //
    // CAMBIO IMPORTANTE:
    //
    // Antes:
    // if(camera_uart_available())
    //
    // Ahora:
    // while(camera_uart_available())
    //
    // Evita dejar mensajes acumulados y permite
    // procesar ESTOP_CLEARED aunque lleguen
    // varias lineas consecutivas.
    //--------------------------------------------------------

    while (camera_uart_available())
    {
        String message =
            camera_uart_get_message();

        if (message.length() == 0)
            continue;

        //----------------------------------------------------
        // SEGURIDAD
        //----------------------------------------------------

        wifi_udp_handle_c3_message(message);

        //----------------------------------------------------
        // NAVEGACION AUTOMATICA
        //----------------------------------------------------

        auto_motion_handle(message);

        //----------------------------------------------------
        // DIAGNOSTICO HACIA PC
        //----------------------------------------------------

        wifi_udp_send_message(
            "CAMERA=" + message
        );
    }

    //--------------------------------------------------------
    // 5. ACTUALIZAR NAVEGACION AUTOMATICA
    //--------------------------------------------------------

    auto_motion_update();

    //--------------------------------------------------------
    // 6. CEDER CPU
    //--------------------------------------------------------

    delay(2);
}