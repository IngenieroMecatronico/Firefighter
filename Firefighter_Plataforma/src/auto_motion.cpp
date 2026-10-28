#include "auto_motion.h"

#include "robot_motion.h"
#include "quad_stepper.h"
#include "camera_uart.h"

//============================================================
// FIREFIGHTER - ESP32 PRINCIPAL
// ARCHIVO: auto_motion.cpp
//
// NAVEGACION AUTOMATICA CONTINUA
//
// OPENMV:
//   1. Escanea el sector mediante PAN.
//   2. Si encuentra fuego:
//        AUTO_FIRE_FOUND
//   3. Si termina el scan sin fuego:
//        AUTO_SCAN_90
//
// C3:
//   Actua como puente UART.
//
// ESP32 PRINCIPAL:
//   Ejecuta el giro del chasis.
//   Confirma inicio y fin del movimiento.
//
// CICLO:
//
// SCAN
//   |
//   | sin fuego
//   v
// AUTO_SCAN_90
//   |
//   v
// GIRO ~90 grados
//   |
//   v
// AUTO_TURN_TIME_DONE
//   |
//   v
// NUEVO SCAN
//   |
//   +--------------------> repetir indefinidamente
//
// El ciclo solamente se interrumpe por:
// - AUTO_FIRE_FOUND
// - AUTO_STOP
// - cambio de modo
// - E-STOP
//
// IMPORTANTE:
// No existe IMU ni odometria.
// El angulo se aproxima mediante tiempo.
//============================================================


//============================================================
// CONFIGURACION
//============================================================

static const bool ENABLE_TIMED_TURN = true;


//============================================================
// VELOCIDAD AUTO
//
// 20 RPM fue insuficiente bajo carga.
// 30 RPM funciona correctamente con los cuatro motores.
//============================================================

static const float AUTO_RPM = 30.0f;


//============================================================
// TIEMPO DE GIRO
//
// 900 ms quedo corto.
//
// Nueva calibracion:
// 1100 ms.
//
// Ajustaremos despues de medir el angulo real.
//============================================================

static const unsigned long TURN_90_MS = 1100;

// Correcciones breves a 30 RPM. Ajustar tras medir giro real.
static const unsigned long CORRECTION_MS = 120;


//============================================================
// LIMITE ABSOLUTO DE SEGURIDAD
//
// Aunque exista un error de logica, nunca permitir
// un giro continuo.
//============================================================

static const unsigned long MAX_TURN_MS = 2500;


//============================================================
// WATCHDOG MOVIMIENTO LINEAL
//
// Reservado para la siguiente fase de AUTO.
//============================================================

static const unsigned long MOVE_WATCHDOG_MS = 350;


//============================================================
// ESTADOS
//============================================================

enum AutoState
{
    AUTO_IDLE,
    AUTO_TURNING,
    AUTO_CORRECTING,
    AUTO_MOVING
};


//============================================================
// VARIABLES
//============================================================

static AutoState state = AUTO_IDLE;

static unsigned long startedAt = 0;
static unsigned long lastCommandAt = 0;

static bool active = false;


//============================================================
// DETENER MOVIMIENTO
//============================================================

static void halt()
{
    robot_stop();

    state = AUTO_IDLE;
}


//============================================================
// INICIALIZAR
//============================================================

void auto_motion_init()
{
    active = false;

    startedAt = 0;
    lastCommandAt = 0;

    halt();
}


//============================================================
// ENTRAR A AUTO
//============================================================

void auto_motion_enter()
{
    // Siempre entrar detenido.
    halt();

    startedAt = 0;
    lastCommandAt = 0;

    active = true;

    // Informar que el sistema de locomocion AUTO esta listo.
    camera_uart_send(
        "AUTO_READY"
    );
}


//============================================================
// SALIR DE AUTO
//============================================================

void auto_motion_exit()
{
    active = false;

    halt();
}


//============================================================
// E-STOP
//============================================================

void auto_motion_estop()
{
    active = false;

    halt();

    enable_motors(
        false
    );
}


//============================================================
// PROCESAR COMANDO AUTO
//============================================================

bool auto_motion_handle(
    const String &message
)
{
    //--------------------------------------------------------
    // NO ES COMANDO AUTO
    //--------------------------------------------------------

    if (!message.startsWith("AUTO_"))
    {
        return false;
    }


    //--------------------------------------------------------
    // AUTO NO ESTA ACTIVO
    //--------------------------------------------------------

    if (!active)
    {
        camera_uart_send(
            "AUTO_REJECTED_MODE"
        );

        return true;
    }


    //--------------------------------------------------------
    // STOP / FUEGO ENCONTRADO
    //
    // Prioridad sobre cualquier movimiento.
    //--------------------------------------------------------

    if (
        message == "AUTO_STOP" ||
        message == "AUTO_FIRE_FOUND"
    )
    {
        halt();

        camera_uart_send(
            "AUTO_STOPPED"
        );

        return true;
    }


    //--------------------------------------------------------
    // GIRO HACIA EL SIGUIENTE SECTOR
    //--------------------------------------------------------

    if (message == "AUTO_SCAN_90")
    {
        //----------------------------------------------------
        // YA ESTA GIRANDO
        //
        // Ignorar otra solicitud.
        // No reiniciar el temporizador.
        //----------------------------------------------------

        if (state == AUTO_TURNING)
        {
            return true;
        }


        //----------------------------------------------------
        // DETENER ANTES DE INICIAR
        //----------------------------------------------------

        halt();


        //----------------------------------------------------
        // PROTECCION DE CALIBRACION
        //----------------------------------------------------

        if (!ENABLE_TIMED_TURN)
        {
            camera_uart_send(
                "AUTO_TURN_NEEDS_CALIBRATION"
            );

            return true;
        }


        //----------------------------------------------------
        // HABILITAR DRIVERS
        //----------------------------------------------------

        enable_motors(
            true
        );


        //----------------------------------------------------
        // INICIAR TEMPORIZADOR
        //----------------------------------------------------

        startedAt = millis();

        state = AUTO_TURNING;


        //----------------------------------------------------
        // GIRO SOBRE EL PROPIO EJE
        //
        // robot_rotate_cw():
        //
        // M1 = -
        // M2 = +
        // M3 = +
        // M4 = -
        //
        // Los cuatro motores participan.
        //----------------------------------------------------

        robot_rotate_cw(
            AUTO_RPM
        );


        //----------------------------------------------------
        // CONFIRMAR INICIO
        //----------------------------------------------------

        camera_uart_send(
            "AUTO_TURN_STARTED"
        );

        return true;
    }


    //--------------------------------------------------------
    // CORRECCION DE CHASIS POR SATURACION PAN
    //--------------------------------------------------------
    if (message == "AUTO_ROTATE_CCW" || message == "AUTO_ROTATE_CW")
    {
        // No aceptar ordenes mientras se ejecuta otro giro.
        if (state != AUTO_IDLE)
            return true;

        halt();
        enable_motors(true);
        startedAt = millis();
        state = AUTO_CORRECTING;

        if (message == "AUTO_ROTATE_CCW")
            robot_rotate_ccw(AUTO_RPM);
        else
            robot_rotate_cw(AUTO_RPM);

        camera_uart_send("AUTO_TURN_STARTED");
        return true;
    }

    //--------------------------------------------------------
    // TRASLACION AUTONOMA
    //
    // TODAVIA NO HABILITADA.
    //
    // La activaremos despues de validar:
    //
    // SCAN -> TURN -> SCAN
    //
    // y la orientacion del chasis hacia el fuego.
    //--------------------------------------------------------

    if (
        message == "AUTO_FORWARD" ||
        message == "AUTO_BACKWARD" ||
        message == "AUTO_LEFT" ||
        message == "AUTO_RIGHT"
    )
    {
        halt();

        camera_uart_send(
            "AUTO_TRANSLATION_NOT_READY"
        );

        return true;
    }


    //--------------------------------------------------------
    // COMANDO DESCONOCIDO
    //--------------------------------------------------------

    camera_uart_send(
        "AUTO_UNKNOWN_COMMAND"
    );

    return true;
}


//============================================================
// ACTUALIZACION AUTO
//============================================================

void auto_motion_update()
{
    //--------------------------------------------------------
    // AUTO INACTIVO
    //--------------------------------------------------------

    if (!active)
    {
        return;
    }


    //--------------------------------------------------------
    // GIRO EN CURSO
    //--------------------------------------------------------

    if (state == AUTO_TURNING)
    {
        unsigned long elapsed =
            millis() - startedAt;


        //----------------------------------------------------
        // TERMINAR GIRO
        //----------------------------------------------------

        if (
            elapsed >= TURN_90_MS ||
            elapsed >= MAX_TURN_MS
        )
        {
            //------------------------------------------------
            // DETENER LOS CUATRO MOTORES
            //------------------------------------------------

            halt();


            //------------------------------------------------
            // INFORMAR FIN DEL GIRO
            //
            // C3 debe retransmitir esto a OpenMV.
            //
            // OpenMV entonces comienza un nuevo SCAN.
            //------------------------------------------------

            camera_uart_send(
                "AUTO_TURN_TIME_DONE"
            );
        }

        return;
    }


    //--------------------------------------------------------
    // FINALIZAR GIRO CORRECTIVO
    //--------------------------------------------------------
    if (state == AUTO_CORRECTING)
    {
        const unsigned long elapsed = millis() - startedAt;
        if (elapsed >= CORRECTION_MS || elapsed >= MAX_TURN_MS)
        {
            halt();
            camera_uart_send("AUTO_TURN_TIME_DONE");
        }
        return;
    }

    //--------------------------------------------------------
    // MOVIMIENTO LINEAL
    //
    // Reservado para fase posterior.
    //--------------------------------------------------------

    if (state == AUTO_MOVING)
    {
        if (
            millis() - lastCommandAt >
            MOVE_WATCHDOG_MS
        )
        {
            halt();

            camera_uart_send(
                "AUTO_MOTION_TIMEOUT"
            );
        }
    }
}