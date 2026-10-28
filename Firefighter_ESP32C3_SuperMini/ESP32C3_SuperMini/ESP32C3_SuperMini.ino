#include <Arduino.h>
#include <ESP32Servo.h>
#include <math.h>

// ============================================================
// FIREFIGHTER - ESP32-C3 SUPER MINI
// ESP32 PRINCIPAL <-> C3 <-> OPENMV H7 R2
//
// MANUAL:
//   ESP32 principal controla PAN / TILT / BOMBA.
//
// SEMI:
//   OpenMV controla PAN / TILT / BOMBA.
//
// AUTO:
//   OpenMV controla torreta.
//   C3 retransmite ordenes AUTO hacia MAIN.
//   C3 retransmite respuestas AUTO hacia OpenMV.
//
// UART OPENMV:
//   GPIO6 TX -> OpenMV P5 RX
//   GPIO7 RX <- OpenMV P4 TX
//
// UART MAIN:
//   GPIO20 RX <- MAIN GPIO1 TX
//   GPIO21 TX -> MAIN GPIO3 RX
// ============================================================


// ============================================================
// PINES
// ============================================================

#define PIN_PAN       0
#define PIN_TILT      1
#define PIN_PUMP      3

#define LED_ROJOS     4
#define LED_BLANCOS   5

#define OPENMV_TX     6
#define OPENMV_RX     7

#define PIN_BUZZER   10

#define MAIN_RX      20
#define MAIN_TX      21


// ============================================================
// UARTS
// ============================================================

HardwareSerial OpenMVSerial(1);
HardwareSerial MainSerial(0);


// ============================================================
// SERVOS
// ============================================================

Servo servoPan;
Servo servoTilt;


// ============================================================
// LIMITES
// ============================================================

const float PAN_MIN = 10.0f;
const float PAN_MAX = 170.0f;

const float TILT_MIN = 50.0f;
const float TILT_MAX = 180.0f;


// ============================================================
// PWM
// ============================================================

const int PAN_PWM_MIN = 1000;
const int PAN_PWM_MAX = 2000;

const int TILT_PWM_MIN = 1000;
const int TILT_PWM_MAX = 2000;


// ============================================================
// PASO MANUAL
// ============================================================

const float SERVO_STEP =
    2.0f;


// ============================================================
// POSICIONES
// ============================================================

float panAngle =
    90.0f;

float tiltAngle =
    90.0f;


// ============================================================
// ESTADO
// ============================================================

String modoActual =
    "MANUAL";

bool estopActive =
    true;

bool bombaEncendida =
    false;

bool emergenciaActiva =
    false;

bool estadoLuces =
    true;


// ============================================================
// LUCES / SIRENA
// ============================================================

unsigned long ultimoCambioLuces =
    0;

unsigned long ultimoCambioSirena =
    0;

const unsigned long INTERVALO_LUCES =
    250;

const unsigned long INTERVALO_SIRENA =
    4;

const int SIRENA_MIN =
    1500;

const int SIRENA_MAX =
    2500;

const int PASO_FRECUENCIA =
    2;

int frecuenciaSirena =
    SIRENA_MIN;

int direccionSirena =
    1;


// ============================================================
// WATCHDOG BOMBA
// ============================================================

const unsigned long PUMP_LEASE_MS =
    1200;

unsigned long ultimoPumpOn =
    0;


// ============================================================
// BUFFERS
// ============================================================

String bufferMain =
    "";

String bufferOpenMV =
    "";


// ============================================================
// ENVIAR MAIN
// ============================================================

void enviarMain(
    const String &mensaje
)
{
    MainSerial.println(
        mensaje
    );

    Serial.print(
        "[C3 -> MAIN] "
    );

    Serial.println(
        mensaje
    );
}


// ============================================================
// ENVIAR OPENMV
// ============================================================

void enviarOpenMV(
    const String &mensaje
)
{
    OpenMVSerial.println(
        mensaje
    );

    Serial.print(
        "[C3 -> OPENMV] "
    );

    Serial.println(
        mensaje
    );
}


// ============================================================
// BOMBA OFF
// ============================================================

void pumpOff()
{
    digitalWrite(
        PIN_PUMP,
        LOW
    );

    if (bombaEncendida)
    {
        bombaEncendida =
            false;

        enviarMain(
            "PUMP=OFF"
        );

        enviarOpenMV(
            "PUMP=OFF"
        );

        Serial.println(
            "[C3] BOMBA OFF"
        );
    }
}


// ============================================================
// BOMBA ON
// ============================================================

void pumpOn()
{
    if (estopActive)
    {
        pumpOff();

        return;
    }

    ultimoPumpOn =
        millis();

    if (!bombaEncendida)
    {
        digitalWrite(
            PIN_PUMP,
            HIGH
        );

        bombaEncendida =
            true;

        enviarMain(
            "PUMP=ON"
        );

        enviarOpenMV(
            "PUMP=ON"
        );

        Serial.println(
            "[C3] BOMBA ON"
        );
    }
}


// ============================================================
// WATCHDOG BOMBA
// ============================================================

void actualizarSeguridadBomba()
{
    if (
        estopActive ||
        (
            bombaEncendida &&
            millis() - ultimoPumpOn >
            PUMP_LEASE_MS
        )
    )
    {
        pumpOff();
    }
}


// ============================================================
// PAN -> PWM
// ============================================================

int panToMicroseconds(
    float angle
)
{
    angle =
        constrain(
            angle,
            PAN_MIN,
            PAN_MAX
        );

    return (int)roundf(
        PAN_PWM_MIN +
        (angle - PAN_MIN) *
        (PAN_PWM_MAX - PAN_PWM_MIN) /
        (PAN_MAX - PAN_MIN)
    );
}


// ============================================================
// TILT -> PWM
// ============================================================

int tiltToMicroseconds(
    float angle
)
{
    angle =
        constrain(
            angle,
            TILT_MIN,
            TILT_MAX
        );

    return (int)roundf(
        TILT_PWM_MIN +
        (angle - TILT_MIN) *
        (TILT_PWM_MAX - TILT_PWM_MIN) /
        (TILT_MAX - TILT_MIN)
    );
}


// ============================================================
// PAN
// ============================================================

void escribirPan(
    float target
)
{
    if (
        estopActive ||
        !isfinite(target)
    )
    {
        return;
    }

    target =
        constrain(
            target,
            PAN_MIN,
            PAN_MAX
        );

    if (
        fabsf(
            target - panAngle
        ) < 0.05f
    )
    {
        return;
    }

    panAngle =
        target;

    servoPan.writeMicroseconds(
        panToMicroseconds(
            panAngle
        )
    );
}


// ============================================================
// TILT
// ============================================================

void escribirTilt(
    float target
)
{
    if (
        estopActive ||
        !isfinite(target)
    )
    {
        return;
    }

    target =
        constrain(
            target,
            TILT_MIN,
            TILT_MAX
        );

    if (
        fabsf(
            target - tiltAngle
        ) < 0.05f
    )
    {
        return;
    }

    tiltAngle =
        target;

    servoTilt.writeMicroseconds(
        tiltToMicroseconds(
            tiltAngle
        )
    );
}


// ============================================================
// MOVIMIENTO TORRETA
// ============================================================

void moverPan(
    float delta
)
{
    escribirPan(
        panAngle + delta
    );
}


void moverTilt(
    float delta
)
{
    escribirTilt(
        tiltAngle + delta
    );
}


void centrarTorreta()
{
    escribirPan(
        90.0f
    );

    escribirTilt(
        90.0f
    );
}


// ============================================================
// LEDS
// ============================================================

void ledsOff()
{
    digitalWrite(
        LED_ROJOS,
        LOW
    );

    digitalWrite(
        LED_BLANCOS,
        LOW
    );
}


// ============================================================
// EMERGENCIA
// ============================================================

void desactivarEmergencia()
{
    emergenciaActiva =
        false;

    ledsOff();

    noTone(
        PIN_BUZZER
    );
}


void activarEmergencia()
{
    if (estopActive)
    {
        return;
    }

    emergenciaActiva =
        true;

    estadoLuces =
        true;

    ultimoCambioLuces =
        millis();

    ultimoCambioSirena =
        millis();

    frecuenciaSirena =
        SIRENA_MIN;

    direccionSirena =
        1;

    digitalWrite(
        LED_ROJOS,
        HIGH
    );

    digitalWrite(
        LED_BLANCOS,
        LOW
    );

    tone(
        PIN_BUZZER,
        frecuenciaSirena
    );
}


void toggleEmergencia()
{
    if (emergenciaActiva)
    {
        desactivarEmergencia();
    }
    else
    {
        activarEmergencia();
    }
}


// ============================================================
// LUCES
// ============================================================

void actualizarLucesEmergencia()
{
    if (
        !emergenciaActiva ||
        estopActive
    )
    {
        return;
    }

    if (
        millis() - ultimoCambioLuces <
        INTERVALO_LUCES
    )
    {
        return;
    }

    ultimoCambioLuces =
        millis();

    estadoLuces =
        !estadoLuces;

    digitalWrite(
        LED_ROJOS,
        estadoLuces
        ? HIGH
        : LOW
    );

    digitalWrite(
        LED_BLANCOS,
        estadoLuces
        ? LOW
        : HIGH
    );
}


// ============================================================
// SIRENA
// ============================================================

void actualizarSirena()
{
    if (
        !emergenciaActiva ||
        estopActive
    )
    {
        return;
    }

    if (
        millis() - ultimoCambioSirena <
        INTERVALO_SIRENA
    )
    {
        return;
    }

    ultimoCambioSirena =
        millis();

    frecuenciaSirena +=
        PASO_FRECUENCIA *
        direccionSirena;

    if (
        frecuenciaSirena >=
        SIRENA_MAX
    )
    {
        frecuenciaSirena =
            SIRENA_MAX;

        direccionSirena =
            -1;
    }
    else if (
        frecuenciaSirena <=
        SIRENA_MIN
    )
    {
        frecuenciaSirena =
            SIRENA_MIN;

        direccionSirena =
            1;
    }

    tone(
        PIN_BUZZER,
        frecuenciaSirena
    );
}


// ============================================================
// ACTIVAR ESTOP
// ============================================================

void activarEstop()
{
    if (estopActive)
    {
        pumpOff();

        desactivarEmergencia();

        return;
    }

    estopActive =
        true;

    pumpOff();

    desactivarEmergencia();

    enviarOpenMV(
        "ESTOP"
    );

    enviarMain(
        "ESTOP_ACTIVE"
    );
}


// ============================================================
// REARMAR ESTOP
// ============================================================

void rearmarEstop()
{
    pumpOff();

    desactivarEmergencia();

    modoActual =
        "MANUAL";

    estopActive =
        false;

    enviarOpenMV(
        "MODE=MANUAL"
    );

    enviarMain(
        "ESTOP_CLEARED"
    );

    Serial.println(
        "[C3] ESTOP REARMADO; MODO MANUAL"
    );
}


// ============================================================
// TARGET
// ============================================================

bool leerTarget(
    const String &cmd,
    const char *prefix,
    float &out
)
{
    String p(
        prefix
    );

    if (
        !cmd.startsWith(p)
    )
    {
        return false;
    }

    String raw =
        cmd.substring(
            p.length()
        );

    raw.trim();

    if (!raw.length())
    {
        return false;
    }

    char *end =
        nullptr;

    float value =
        strtof(
            raw.c_str(),
            &end
        );

    if (
        end == raw.c_str() ||
        *end != '\0' ||
        !isfinite(value)
    )
    {
        return false;
    }

    out =
        value;

    return true;
}


// ============================================================
// COMANDOS MAIN
// ============================================================

void procesarComandoMain(
    String comando
)
{
    comando.trim();

    if (!comando.length())
    {
        return;
    }

    Serial.print(
        "[MAIN -> C3] "
    );

    Serial.println(
        comando
    );


    //---------------------------------------------------------
    // ESTOP
    //---------------------------------------------------------

    if (
        comando ==
        "ESTOP"
    )
    {
        activarEstop();

        return;
    }


    //---------------------------------------------------------
    // PUMP OFF
    //---------------------------------------------------------

    if (
        comando ==
        "PUMP_OFF"
    )
    {
        pumpOff();

        return;
    }


    //---------------------------------------------------------
    // ESTOP RESET
    //
    // Si esta bloqueado:
    //   rearma y responde.
    //
    // Si ya esta liberado pero MAIN sigue solicitando:
    //   repetir ACK.
    //
    // MAIN dejara de solicitar en cuanto reciba
    // correctamente ESTOP_CLEARED.
    //---------------------------------------------------------

    if (
        comando ==
        "ESTOP_RESET"
    )
    {
        if (estopActive)
        {
            rearmarEstop();
        }
        else
        {
            enviarMain(
                "ESTOP_CLEARED"
            );
        }

        return;
    }


    //---------------------------------------------------------
    // BLOQUEO ESTOP
    //---------------------------------------------------------

    if (estopActive)
    {
        return;
    }


    //---------------------------------------------------------
    // CAMBIO DE MODO
    //---------------------------------------------------------

    if (
        comando == "MODE=MANUAL" ||
        comando == "MODE=SEMI" ||
        comando == "MODE=AUTO"
    )
    {
        pumpOff();

        modoActual =
            comando.substring(
                5
            );

        enviarOpenMV(
            comando
        );

        return;
    }


    //---------------------------------------------------------
    // RESPUESTAS AUTO MAIN -> OPENMV
    //---------------------------------------------------------

    if (
        comando == "AUTO_READY" ||
        comando == "AUTO_TURN_STARTED" ||
        comando == "AUTO_TURN_TIME_DONE" ||
        comando == "AUTO_STOPPED" ||
        comando == "AUTO_SCAN_COMPLETE" ||
        comando == "AUTO_TURN_NEEDS_CALIBRATION" ||
        comando == "AUTO_REJECTED_MODE" ||
        comando == "AUTO_TRANSLATION_NOT_READY" ||
        comando == "AUTO_MOTION_TIMEOUT" ||
        comando == "AUTO_UNKNOWN_COMMAND"
    )
    {
        enviarOpenMV(
            comando
        );

        return;
    }


    //---------------------------------------------------------
    // EMERGENCIA
    //---------------------------------------------------------

    if (
        comando ==
        "EMERGENCY_TOGGLE"
    )
    {
        toggleEmergencia();

        return;
    }


    //---------------------------------------------------------
    // MANUAL TORRETA
    //---------------------------------------------------------

    if (
        modoActual ==
        "MANUAL"
    )
    {
        if (
            comando ==
            "PAN_RIGHT"
        )
        {
            moverPan(
                SERVO_STEP
            );

            return;
        }

        if (
            comando ==
            "PAN_LEFT"
        )
        {
            moverPan(
                -SERVO_STEP
            );

            return;
        }

        if (
            comando ==
            "TILT_UP"
        )
        {
            moverTilt(
                -SERVO_STEP
            );

            return;
        }

        if (
            comando ==
            "TILT_DOWN"
        )
        {
            moverTilt(
                SERVO_STEP
            );

            return;
        }

        if (
            comando ==
            "TURRET_CENTER"
        )
        {
            centrarTorreta();

            return;
        }

        if (
            comando ==
            "PUMP_ON"
        )
        {
            pumpOn();

            return;
        }
    }


    //---------------------------------------------------------
    // PING OPENMV
    //---------------------------------------------------------

    if (
        comando ==
        "PING"
    )
    {
        enviarOpenMV(
            "PING"
        );

        return;
    }
}


// ============================================================
// COMANDOS OPENMV
// ============================================================

void procesarComandoOpenMV(
    String comando
)
{
    comando.trim();

    if (!comando.length())
    {
        return;
    }

    Serial.print(
        "[OPENMV -> C3] "
    );

    Serial.println(
        comando
    );


    //---------------------------------------------------------
    // PING / PONG
    //---------------------------------------------------------

    if (
        comando ==
        "PING"
    )
    {
        enviarOpenMV(
            "PONG"
        );

        return;
    }


    //---------------------------------------------------------
    // PUMP OFF
    //---------------------------------------------------------

    if (
        comando ==
        "PUMP_OFF"
    )
    {
        pumpOff();

        return;
    }


    //---------------------------------------------------------
    // ESTOP
    //---------------------------------------------------------

    if (estopActive)
    {
        return;
    }


    //---------------------------------------------------------
    // SEMI / AUTO TORRETA
    //---------------------------------------------------------

    if (
        modoActual == "SEMI" ||
        modoActual == "AUTO"
    )
    {
        float target;

        if (
            leerTarget(
                comando,
                "PAN_TARGET=",
                target
            )
        )
        {
            escribirPan(
                target
            );

            return;
        }

        if (
            leerTarget(
                comando,
                "TILT_TARGET=",
                target
            )
        )
        {
            escribirTilt(
                target
            );

            return;
        }

        if (
            comando ==
            "PUMP_ON"
        )
        {
            pumpOn();

            return;
        }
    }


    //---------------------------------------------------------
    // AUTO OPENMV -> MAIN
    //---------------------------------------------------------

    if (
        modoActual ==
        "AUTO"
    )
    {
        if (
            comando == "AUTO_SCAN_90" ||
            comando == "AUTO_STOP" ||
            comando == "AUTO_FIRE_FOUND" ||
            comando == "AUTO_FORWARD" ||
            comando == "AUTO_BACKWARD" ||
            comando == "AUTO_LEFT" ||
            comando == "AUTO_RIGHT" ||
            comando == "AUTO_ROTATE_CW" ||
            comando == "AUTO_ROTATE_CCW" ||
            comando.startsWith(
                "AUTO_SPEED="
            )
        )
        {
            enviarMain(
                comando
            );

            return;
        }
    }
}


// ============================================================
// LEER MAIN
// ============================================================

void leerMain()
{
    while (
        MainSerial.available()
    )
    {
        char c =
            (char)MainSerial.read();

        if (
            c == '\n'
        )
        {
            procesarComandoMain(
                bufferMain
            );

            bufferMain =
                "";
        }
        else if (
            c != '\r'
        )
        {
            bufferMain +=
                c;

            if (
                bufferMain.length() >
                128
            )
            {
                bufferMain =
                    "";
            }
        }
    }
}


// ============================================================
// LEER OPENMV
// ============================================================

void leerOpenMV()
{
    while (
        OpenMVSerial.available()
    )
    {
        char c =
            (char)OpenMVSerial.read();

        if (
            c == '\n'
        )
        {
            procesarComandoOpenMV(
                bufferOpenMV
            );

            bufferOpenMV =
                "";
        }
        else if (
            c != '\r'
        )
        {
            bufferOpenMV +=
                c;

            if (
                bufferOpenMV.length() >
                128
            )
            {
                bufferOpenMV =
                    "";
            }
        }
    }
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
    //---------------------------------------------------------
    // BOMBA
    //---------------------------------------------------------

    pinMode(
        PIN_PUMP,
        OUTPUT
    );

    digitalWrite(
        PIN_PUMP,
        LOW
    );


    //---------------------------------------------------------
    // LEDS / BUZZER
    //---------------------------------------------------------

    pinMode(
        LED_ROJOS,
        OUTPUT
    );

    pinMode(
        LED_BLANCOS,
        OUTPUT
    );

    pinMode(
        PIN_BUZZER,
        OUTPUT
    );

    ledsOff();

    noTone(
        PIN_BUZZER
    );


    //---------------------------------------------------------
    // USB DEBUG
    //---------------------------------------------------------

    Serial.begin(
        115200
    );

    delay(
        300
    );


    //---------------------------------------------------------
    // SERVOS
    //---------------------------------------------------------

    servoPan.setPeriodHertz(
        50
    );

    servoPan.attach(
        PIN_PAN,
        PAN_PWM_MIN,
        PAN_PWM_MAX
    );

    servoTilt.setPeriodHertz(
        60
    );

    servoTilt.attach(
        PIN_TILT,
        TILT_PWM_MIN,
        TILT_PWM_MAX
    );


    //---------------------------------------------------------
    // POSICIONES INICIALES
    //---------------------------------------------------------

    servoPan.writeMicroseconds(
        panToMicroseconds(
            panAngle
        )
    );

    servoTilt.writeMicroseconds(
        tiltToMicroseconds(
            tiltAngle
        )
    );


    //---------------------------------------------------------
    // UART OPENMV
    //---------------------------------------------------------

    OpenMVSerial.begin(
        115200,
        SERIAL_8N1,
        OPENMV_RX,
        OPENMV_TX
    );


    //---------------------------------------------------------
    // UART MAIN
    //---------------------------------------------------------

    MainSerial.begin(
        115200,
        SERIAL_8N1,
        MAIN_RX,
        MAIN_TX
    );


    //---------------------------------------------------------
    // INFORMACION
    //---------------------------------------------------------

    Serial.println();
    Serial.println(
        "========================================"
    );

    Serial.println(
        "FIREFIGHTER - ESP32-C3"
    );

    Serial.println(
        "========================================"
    );

    Serial.println();

    Serial.println(
        "UART MAIN BIDIRECCIONAL VALIDADO"
    );

    Serial.println(
        "ESTOP HANDSHAKE ROBUSTO"
    );

    Serial.println(
        "PUENTE AUTO HABILITADO"
    );

    Serial.println();


    //---------------------------------------------------------
    // ARRANQUE BLOQUEADO
    //---------------------------------------------------------

    enviarMain(
        "ESTOP_ACTIVE"
    );

    enviarOpenMV(
        "ESTOP"
    );

    Serial.println(
        "[C3] SISTEMA LISTO"
    );
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
    leerMain();

    leerOpenMV();

    actualizarSeguridadBomba();

    actualizarLucesEmergencia();

    actualizarSirena();

    delay(
        1
    );
}