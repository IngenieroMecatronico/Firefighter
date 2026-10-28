#include "wifi_udp.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "robot_motion.h"
#include "quad_stepper.h"
#include "camera_uart.h"
#include "auto_motion.h"

//============================================================
// FIREFIGHTER - ESP32 PRINCIPAL
// ARCHIVO: wifi_udp.cpp
//
// FUNCIONES:
// - WiFi + UDP
// - Modos MANUAL / SEMI / AUTO
// - Locomocion
// - Failsafe
// - Comunicacion con ESP32-C3
// - E-STOP retenido
// - Rearme confirmado por C3
//
// SEGURIDAD:
//
// E-STOP:
//   robot_stop()
//   enable_motors(false)
//
// ESTOP_CLEARED:
//   robot_stop()
//   enable_motors(true)
//
// Habilitar los drivers NO mueve el robot.
// Los setpoints permanecen en cero.
//============================================================


//============================================================
// LED WIFI
//============================================================

#define WIFI_LED_PIN 2


//============================================================
// WIFI
//============================================================

static const char *ssid =
    "Robotat_2";

static const char *password =
    "Firefighter_2";

static IPAddress local_IP(
    192, 168, 50, 171
);

static IPAddress gateway(
    192, 168, 50, 1
);

static IPAddress subnet(
    255, 255, 255, 0
);


//============================================================
// UDP
//============================================================

static const uint16_t UDP_PORT =
    12345;

static WiFiUDP udp;


//============================================================
// PC REGISTRADA
//============================================================

static bool pcRegistered =
    false;

static IPAddress pcIP;

static uint16_t pcPort =
    0;


//============================================================
// FAILSAFE MANUAL / SEMI
//============================================================

static unsigned long lastManualCommand =
    0;

static bool manualMovementActive =
    false;

static const unsigned long MANUAL_TIMEOUT =
    350;


//============================================================
// E-STOP
//============================================================

static bool estopActive =
    true;

static bool resetPending =
    false;

static unsigned long lastEstopTx =
    0;

static const unsigned long ESTOP_RETRY_MS =
    200;


//============================================================
// ENVIAR UDP
//============================================================

static void sendMessage(
    const String &message
)
{
    if (!pcRegistered)
    {
        return;
    }

    udp.beginPacket(
        pcIP,
        pcPort
    );

    udp.print(
        message
    );

    udp.endPacket();
}


//============================================================
// INTERFAZ PUBLICA
//============================================================

void wifi_udp_send_message(
    const String &message
)
{
    sendMessage(
        message
    );
}


//============================================================
// PARADA DE SEGURIDAD
//
// Detiene Y deshabilita drivers.
//
// Usar para E-STOP.
//============================================================

static void stopLocomotion()
{
    robot_stop();

    manualMovementActive =
        false;

    enable_motors(
        false
    );
}


//============================================================
// REARMAR LOCOMOCION
//
// Robot detenido pero drivers habilitados.
//============================================================

static void armLocomotionStopped()
{
    robot_stop();

    manualMovementActive =
        false;

    enable_motors(
        true
    );
}


//============================================================
// ACTIVAR E-STOP
//============================================================

static void activateEstop()
{
    estopActive =
        true;

    resetPending =
        false;

    stopLocomotion();

    auto_motion_estop();

    camera_uart_send(
        "ESTOP"
    );

    camera_uart_send(
        "PUMP_OFF"
    );

    lastEstopTx =
        millis();
}


//============================================================
// MENSAJES DEL C3
//============================================================

void wifi_udp_handle_c3_message(
    const String &message
)
{
    //--------------------------------------------------------
    // C3 CONFIRMA E-STOP
    //--------------------------------------------------------

    if (
        message ==
        "ESTOP_ACTIVE"
    )
    {
        estopActive =
            true;

        resetPending =
            false;

        stopLocomotion();

        auto_motion_estop();

        sendMessage(
            "ESTOP_ACTIVE"
        );

        return;
    }


    //--------------------------------------------------------
    // C3 CONFIRMA REARME
    //--------------------------------------------------------

    if (
        message ==
        "ESTOP_CLEARED"
    )
    {
        //----------------------------------------------------
        // Aceptamos el ACK mientras MAIN siga bloqueado.
        //----------------------------------------------------

        if (estopActive)
        {
            //------------------------------------------------
            // LIBERAR ESTOP
            //------------------------------------------------

            estopActive =
                false;

            resetPending =
                false;


            //------------------------------------------------
            // CANCELAR AUTO PREVIO
            //------------------------------------------------

            auto_motion_exit();


            //------------------------------------------------
            // TODO REARME REGRESA A MANUAL
            //------------------------------------------------

            robot_set_mode(
                MODE_MANUAL
            );


            //------------------------------------------------
            // ROBOT QUIETO, DRIVERS HABILITADOS
            //------------------------------------------------

            armLocomotionStopped();


            //------------------------------------------------
            // SINCRONIZAR C3
            //------------------------------------------------

            camera_uart_send(
                "MODE=MANUAL"
            );


            //------------------------------------------------
            // INFORMAR PC
            //------------------------------------------------

            sendMessage(
                "OK ESTOP_CLEARED"
            );
        }

        return;
    }
}


//============================================================
// INICIALIZAR WIFI + UDP
//============================================================

void wifi_udp_init()
{
    pinMode(
        WIFI_LED_PIN,
        OUTPUT
    );

    digitalWrite(
        WIFI_LED_PIN,
        LOW
    );


    //--------------------------------------------------------
    // WIFI STA
    //--------------------------------------------------------

    WiFi.mode(
        WIFI_STA
    );


    //--------------------------------------------------------
    // IP FIJA
    //--------------------------------------------------------

    WiFi.config(
        local_IP,
        gateway,
        subnet
    );


    //--------------------------------------------------------
    // CONECTAR
    //--------------------------------------------------------

    WiFi.begin(
        ssid,
        password
    );


    //--------------------------------------------------------
    // ESPERAR WIFI
    //--------------------------------------------------------

    while (
        WiFi.status() !=
        WL_CONNECTED
    )
    {
        digitalWrite(
            WIFI_LED_PIN,
            !digitalRead(
                WIFI_LED_PIN
            )
        );

        delay(
            250
        );
    }


    //--------------------------------------------------------
    // WIFI OK
    //--------------------------------------------------------

    digitalWrite(
        WIFI_LED_PIN,
        HIGH
    );


    //--------------------------------------------------------
    // UDP
    //--------------------------------------------------------

    udp.begin(
        UDP_PORT
    );
}


//============================================================
// STATUS
//============================================================

void wifi_udp_send_status()
{
    sendMessage(
        "STATUS MODE=" +
        String(
            robot_mode_name()
        ) +
        " RPM=" +
        String(
            manualRPM,
            1
        ) +
        " ESTOP=" +
        String(
            estopActive
            ? "ON"
            : "OFF"
        )
    );
}


//============================================================
// PROCESAR UDP
//============================================================

void process_udp_commands()
{
    //--------------------------------------------------------
    // VERIFICAR PAQUETE
    //--------------------------------------------------------

    int packetSize =
        udp.parsePacket();

    if (
        packetSize <= 0
    )
    {
        return;
    }


    //--------------------------------------------------------
    // LEER COMANDO
    //--------------------------------------------------------

    char packet[128];

    int len =
        udp.read(
            packet,
            sizeof(packet) - 1
        );

    if (
        len <= 0
    )
    {
        return;
    }

    packet[len] =
        '\0';

    String cmd(
        packet
    );

    cmd.trim();


    //--------------------------------------------------------
    // REGISTRAR PC
    //--------------------------------------------------------

    pcIP =
        udp.remoteIP();

    pcPort =
        udp.remotePort();

    pcRegistered =
        true;


    //--------------------------------------------------------
    // PING
    //--------------------------------------------------------

    if (
        cmd ==
        "ping"
    )
    {
        sendMessage(
            "pong"
        );

        return;
    }


    //--------------------------------------------------------
    // STATUS
    //--------------------------------------------------------

    if (
        cmd ==
        "status"
    )
    {
        wifi_udp_send_status();

        return;
    }


    //--------------------------------------------------------
    // E-STOP
    //--------------------------------------------------------

    if (
        cmd ==
        "estop"
    )
    {
        activateEstop();

        sendMessage(
            "OK ESTOP_ACTIVE"
        );

        return;
    }


    //--------------------------------------------------------
    // ESTOP RESET
    //--------------------------------------------------------

    if (
        cmd ==
        "estop_reset"
    )
    {
        //----------------------------------------------------
        // YA LIBERADO
        //----------------------------------------------------

        if (!estopActive)
        {
            sendMessage(
                "OK ESTOP_ALREADY_CLEARED"
            );

            return;
        }


        //----------------------------------------------------
        // SI YA ESPERAMOS ACK
        //----------------------------------------------------

        if (resetPending)
        {
            sendMessage(
                "WAIT ESTOP_RESET_ACK"
            );

            return;
        }


        //----------------------------------------------------
        // INICIAR HANDSHAKE
        //----------------------------------------------------

        resetPending =
            true;

        stopLocomotion();

        camera_uart_send(
            "ESTOP_RESET"
        );

        lastEstopTx =
            millis();

        sendMessage(
            "WAIT ESTOP_RESET_ACK"
        );

        return;
    }


    //--------------------------------------------------------
    // PUMP OFF
    //
    // Siempre permitido.
    //--------------------------------------------------------

    if (
        cmd ==
        "pump_off"
    )
    {
        camera_uart_send(
            "PUMP_OFF"
        );

        sendMessage(
            "OK PUMP_OFF_REQUESTED"
        );

        return;
    }


    //--------------------------------------------------------
    // STOP NORMAL
    //
    // STOP NO ES E-STOP.
    //
    // Detener sin deshabilitar drivers.
    //--------------------------------------------------------

    if (
        cmd ==
        "stop"
    )
    {
        robot_stop();

        manualMovementActive =
            false;

        if (
            robotMode ==
            MODE_AUTO
        )
        {
            auto_motion_exit();
        }

        sendMessage(
            "OK STOP"
        );

        return;
    }


    //--------------------------------------------------------
    // BLOQUEO GLOBAL POR E-STOP
    //--------------------------------------------------------

    if (estopActive)
    {
        stopLocomotion();

        sendMessage(
            "BLOCKED ESTOP_ACTIVE"
        );

        return;
    }


    //--------------------------------------------------------
    // PING OPENMV
    //--------------------------------------------------------

    if (
        cmd ==
        "camera_ping"
    )
    {
        camera_uart_send(
            "PING"
        );

        sendMessage(
            "OK CAMERA_PING"
        );

        return;
    }


    //--------------------------------------------------------
    // LUCES + SIRENA
    //--------------------------------------------------------

    if (
        cmd ==
        "emergency_toggle"
    )
    {
        camera_uart_send(
            "EMERGENCY_TOGGLE"
        );

        sendMessage(
            "OK EMERGENCY_TOGGLE"
        );

        return;
    }


    //--------------------------------------------------------
    // MANUAL
    //--------------------------------------------------------

    if (
        cmd ==
        "mode=manual"
    )
    {
        camera_uart_send(
            "PUMP_OFF"
        );

        auto_motion_exit();

        robot_set_mode(
            MODE_MANUAL
        );

        manualMovementActive =
            false;

        enable_motors(
            true
        );

        camera_uart_send(
            "MODE=MANUAL"
        );

        sendMessage(
            "OK MODE=MANUAL"
        );

        return;
    }


    //--------------------------------------------------------
    // SEMI
    //--------------------------------------------------------

    if (
        cmd ==
        "mode=semi"
    )
    {
        camera_uart_send(
            "PUMP_OFF"
        );

        auto_motion_exit();

        robot_set_mode(
            MODE_SEMI_AUTO
        );

        manualMovementActive =
            false;

        enable_motors(
            true
        );

        camera_uart_send(
            "MODE=SEMI"
        );

        sendMessage(
            "OK MODE=SEMI_AUTO"
        );

        return;
    }


    //--------------------------------------------------------
    // AUTO
    //--------------------------------------------------------

    if (
        cmd ==
        "mode=auto"
    )
    {
        camera_uart_send(
            "PUMP_OFF"
        );

        robot_set_mode(
            MODE_AUTO
        );

        auto_motion_enter();

        manualMovementActive =
            false;

        enable_motors(
            true
        );

        camera_uart_send(
            "MODE=AUTO"
        );

        sendMessage(
            "OK MODE=AUTO"
        );

        return;
    }


    //--------------------------------------------------------
    // VELOCIDAD
    //--------------------------------------------------------

    if (
        cmd.startsWith(
            "speed="
        )
    )
    {
        float newRPM =
            cmd.substring(
                6
            ).toFloat();

        manualRPM =
            constrain(
                newRPM,
                5.0f,
                80.0f
            );

        sendMessage(
            "OK SPEED=" +
            String(
                manualRPM,
                1
            )
        );

        return;
    }


    //--------------------------------------------------------
    // TORRETA MANUAL
    //--------------------------------------------------------

    if (
        cmd == "pan_left" ||
        cmd == "pan_right" ||
        cmd == "tilt_up" ||
        cmd == "tilt_down" ||
        cmd == "turret_center" ||
        cmd == "pump_on"
    )
    {
        if (
            robotMode !=
            MODE_MANUAL
        )
        {
            sendMessage(
                "IGNORED TURRET_NOT_MANUAL"
            );

            return;
        }

        String out =
            cmd;

        out.toUpperCase();

        camera_uart_send(
            out
        );

        sendMessage(
            "OK " +
            out
        );

        return;
    }


    //--------------------------------------------------------
    // LOCOMOCION SOLO MANUAL / SEMI
    //--------------------------------------------------------

    if (
        robotMode != MODE_MANUAL &&
        robotMode != MODE_SEMI_AUTO
    )
    {
        sendMessage(
            "IGNORED AUTO_MODE"
        );

        return;
    }


    //--------------------------------------------------------
    // MOVIMIENTO
    //--------------------------------------------------------

    if (
        cmd ==
        "forward"
    )
    {
        robot_forward(
            manualRPM
        );
    }

    else if (
        cmd ==
        "backward"
    )
    {
        robot_backward(
            manualRPM
        );
    }

    else if (
        cmd ==
        "left"
    )
    {
        robot_left(
            manualRPM
        );
    }

    else if (
        cmd ==
        "right"
    )
    {
        robot_right(
            manualRPM
        );
    }

    else if (
        cmd ==
        "rotate_ccw"
    )
    {
        robot_rotate_ccw(
            manualRPM
        );
    }

    else if (
        cmd ==
        "rotate_cw"
    )
    {
        robot_rotate_cw(
            manualRPM
        );
    }

    else
    {
        sendMessage(
            "ERROR UNKNOWN_COMMAND"
        );

        return;
    }


    //--------------------------------------------------------
    // ACTUALIZAR FAILSAFE
    //--------------------------------------------------------

    lastManualCommand =
        millis();

    manualMovementActive =
        true;


    //--------------------------------------------------------
    // ACK
    //--------------------------------------------------------

    String ack =
        cmd;

    ack.toUpperCase();

    sendMessage(
        "OK " +
        ack
    );
}


//============================================================
// FAILSAFE + RETRY ESTOP
//============================================================

void wifi_udp_safety_update()
{
    //--------------------------------------------------------
    // E-STOP ACTIVO
    //--------------------------------------------------------

    if (estopActive)
    {
        stopLocomotion();

        auto_motion_estop();

        unsigned long now =
            millis();


        //----------------------------------------------------
        // REINTENTO HANDSHAKE
        //----------------------------------------------------

        if (
            now - lastEstopTx >=
            ESTOP_RETRY_MS
        )
        {
            if (resetPending)
            {
                //------------------------------------------------
                // Seguimos solicitando hasta recibir
                // ESTOP_CLEARED.
                //------------------------------------------------

                camera_uart_send(
                    "ESTOP_RESET"
                );
            }
            else
            {
                camera_uart_send(
                    "ESTOP"
                );
            }

            lastEstopTx =
                now;
        }

        return;
    }


    //--------------------------------------------------------
    // AUTO
    //
    // No aplicar failsafe manual.
    //--------------------------------------------------------

    if (
        robotMode != MODE_MANUAL &&
        robotMode != MODE_SEMI_AUTO
    )
    {
        manualMovementActive =
            false;

        return;
    }


    //--------------------------------------------------------
    // MANUAL / SEMI
    //--------------------------------------------------------

    if (
        manualMovementActive &&
        millis() - lastManualCommand >
        MANUAL_TIMEOUT
    )
    {
        robot_stop();

        manualMovementActive =
            false;
    }
}