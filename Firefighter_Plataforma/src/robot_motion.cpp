
#include "robot_motion.h"
#include "quad_stepper.h"

//============================================================
// FIREFIGHTER - ESP32 PRINCIPAL
// ARCHIVO: robot_motion.cpp
//
// DISTRIBUCION FISICA:
//
// M1 = Delantero izquierdo
// M2 = Delantero derecho
// M3 = Trasero derecho
// M4 = Trasero izquierdo
//
// REFERENCIA COMPROBADA:
//
// RPM negativas = rueda avanza
// RPM positivas = rueda retrocede
//
// MOVIMIENTOS:
//
// FORWARD  (- - - -)  COMPROBADO
// BACKWARD (+ + + +)  COMPROBADO
// CW       (- + + -)  COMPROBADO
// CCW      (+ - - +)  COMPROBADO
//
// LEFT     (+ - + -)  PENDIENTE DE VALIDAR
// RIGHT    (- + - +)  PENDIENTE DE VALIDAR
//
// IMPORTANTE:
// Los desplazamientos laterales propuestos
// corresponden a ruedas mecanum en configuracion X.
//============================================================


//============================================================
// VARIABLES EXTERNAS DE MOTORES
//============================================================

extern volatile float rpmSetpoints[4];


//============================================================
// ESTADO GENERAL
//============================================================

RobotMode robotMode = MODE_MANUAL;

float manualRPM = 30.0f;

// Salida auxiliar sin PID.
static float zeroOutput[4] = {
    0.0f, 0.0f, 0.0f, 0.0f
};


//============================================================
// APLICAR RPM A LOS CUATRO MOTORES
//
// Indices:
// 0 = M1 delantero izquierdo
// 1 = M2 delantero derecho
// 2 = M3 trasero derecho
// 3 = M4 trasero izquierdo
//============================================================

static void set_motor_rpm(
    float m1,
    float m2,
    float m3,
    float m4
)
{
    rpmSetpoints[0] = m1;
    rpmSetpoints[1] = m2;
    rpmSetpoints[2] = m3;
    rpmSetpoints[3] = m4;

    apply_motor_outputs(zeroOutput);
}


//============================================================
// INICIALIZACION
//============================================================

void robot_motion_init()
{
    robotMode = MODE_MANUAL;
    robot_stop();
}


//============================================================
// ADELANTE
//
// Comprobado fisicamente.
// (- - - -)
//============================================================

void robot_forward(float rpm)
{
    set_motor_rpm(
        -rpm,  // M1
        -rpm,  // M2
        -rpm,  // M3
        -rpm   // M4
    );
}


//============================================================
// ATRAS
//
// Comprobado fisicamente.
// (+ + + +)
//============================================================

void robot_backward(float rpm)
{
    set_motor_rpm(
        +rpm,  // M1
        +rpm,  // M2
        +rpm,  // M3
        +rpm   // M4
    );
}


//============================================================
// DESPLAZAMIENTO LATERAL IZQUIERDO
//
// PROPUESTA PARA MECANUM CONFIGURACION X
//
// M1 = atras
// M2 = adelante
// M3 = atras
// M4 = adelante
//
// (+ - + -)
//
// Pendiente de comprobar fisicamente.
//============================================================

void robot_left(float rpm)
{
    set_motor_rpm(
        +rpm,  // M1 delantero izquierdo
        -rpm,  // M2 delantero derecho
        +rpm,  // M3 trasero derecho
        -rpm   // M4 trasero izquierdo
    );
}


//============================================================
// DESPLAZAMIENTO LATERAL DERECHO
//
// PROPUESTA PARA MECANUM CONFIGURACION X
//
// M1 = adelante
// M2 = atras
// M3 = adelante
// M4 = atras
//
// (- + - +)
//
// Pendiente de comprobar fisicamente.
//============================================================

void robot_right(float rpm)
{
    set_motor_rpm(
        -rpm,  // M1 delantero izquierdo
        +rpm,  // M2 delantero derecho
        -rpm,  // M3 trasero derecho
        +rpm   // M4 trasero izquierdo
    );
}


//============================================================
// ROTACION ANTIHORARIA (CCW)
//
// COMPROBADA FISICAMENTE
//
// M1 y M4 retroceden.
// M2 y M3 avanzan.
//
// (+ - - +)
//============================================================

void robot_rotate_ccw(float rpm)
{
    set_motor_rpm(
        +rpm,  // M1
        -rpm,  // M2
        -rpm,  // M3
        +rpm   // M4
    );
}


//============================================================
// ROTACION HORARIA (CW)
//
// COMPROBADA FISICAMENTE
//
// M1 y M4 avanzan.
// M2 y M3 retroceden.
//
// (- + + -)
//============================================================

void robot_rotate_cw(float rpm)
{
    set_motor_rpm(
        -rpm,  // M1
        +rpm,  // M2
        +rpm,  // M3
        -rpm   // M4
    );
}


//============================================================
// DETENER LOCOMOCION
//
// RPM = 0 para los cuatro motores.
//
// La habilitacion fisica de drivers se gestiona
// mediante enable_motors() en otros modulos.
//============================================================

void robot_stop()
{
    set_motor_rpm(
        0.0f,
        0.0f,
        0.0f,
        0.0f
    );
}


//============================================================
// CAMBIAR MODO
//
// Detener locomocion antes del cambio.
//============================================================

void robot_set_mode(RobotMode mode)
{
    robot_stop();
    robotMode = mode;
}


//============================================================
// NOMBRE DEL MODO
//============================================================

const char *robot_mode_name()
{
    switch (robotMode)
    {
        case MODE_MANUAL:
            return "MANUAL";

        case MODE_SEMI_AUTO:
            return "SEMI_AUTO";

        case MODE_AUTO:
            return "AUTO";

        default:
            return "UNKNOWN";
    }
}
