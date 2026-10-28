#include <Arduino.h>
#include "quad_stepper.h"

//==================== Pines ====================

#define ENABLE_PIN 23

const uint8_t stepPins[4] = {26, 19, 16, 14};
const uint8_t dirPins[4]  = {25, 18, 4, 27};

//==================== Variables externas ====================

// Las define el PID
extern volatile float rpmSetpoints[4];
extern volatile float rpmMeasured[4];

//==================== Variables internas ====================

bool directionCW[4] = {true, false, false, true};

volatile bool activeMotors[4] =
{
    false,
    false,
    false,
    false
};

volatile bool stepState[4] =
{
    false,
    false,
    false,
    false
};

volatile uint8_t microstepping = 32;

hw_timer_t *timers[4];
//============================================================
// Variables internas
//============================================================

uint64_t halfPeriodUS[4] =
{
    0,
    0,
    0,
    0
};

//============================================================
// Prototipos
//============================================================

static uint64_t calculate_half_period_us(
    uint8_t motorIndex,
    float error
);

static void update_timer_interval(
    uint8_t motorIndex,
    float commandedRPM
);
//==================== ISR ====================

void IRAM_ATTR isr0()
{
    stepState[0] = !stepState[0];
    digitalWrite(stepPins[0], stepState[0]);
}

void IRAM_ATTR isr1()
{
    stepState[1] = !stepState[1];
    digitalWrite(stepPins[1], stepState[1]);
}

void IRAM_ATTR isr2()
{
    stepState[2] = !stepState[2];
    digitalWrite(stepPins[2], stepState[2]);
}

void IRAM_ATTR isr3()
{
    stepState[3] = !stepState[3];
    digitalWrite(stepPins[3], stepState[3]);
}

//==================== Inicialización ====================

void quad_stepper_init()
{
    pinMode(ENABLE_PIN, OUTPUT);

    for(int i = 0; i < 4; i++)
    {
        pinMode(stepPins[i], OUTPUT);
        pinMode(dirPins[i], OUTPUT);

        digitalWrite(stepPins[i], LOW);
        digitalWrite(dirPins[i],
                     directionCW[i] ? HIGH : LOW);
    }

    timers[0] = timerBegin(0,80,true);
    timers[1] = timerBegin(1,80,true);
    timers[2] = timerBegin(2,80,true);
    timers[3] = timerBegin(3,80,true);

    timerAttachInterrupt(timers[0], &isr0, true);
    timerAttachInterrupt(timers[1], &isr1, true);
    timerAttachInterrupt(timers[2], &isr2, true);
    timerAttachInterrupt(timers[3], &isr3, true);

    for(int i = 0; i < 4; i++)
    {
        timerAlarmWrite(timers[i],1000,true);
        timerAlarmEnable(timers[i]);
    }

    enable_motors(false);
}

//==================== Enable ====================

void enable_motors(bool state)
{
    digitalWrite(
        ENABLE_PIN,
        state ? LOW : HIGH
    );
}

//============================================================
// TRUE CLONE
// update_timer_interval()
//============================================================

static void update_timer_interval(uint8_t motorIndex,
                                  float commandedRPM)
{
    halfPeriodUS[motorIndex] =
        calculate_half_period_us(
            motorIndex,
            commandedRPM
        );

    timerAlarmDisable(
        timers[motorIndex]
    );

    if(halfPeriodUS[motorIndex] == 0 ||
       !activeMotors[motorIndex])
    {
        digitalWrite(
            stepPins[motorIndex],
            LOW
        );

        stepState[motorIndex] = false;

        return;
    }

    timerAlarmWrite(
        timers[motorIndex],
        halfPeriodUS[motorIndex],
        true
    );

    stepState[motorIndex] = false;

    digitalWrite(
        stepPins[motorIndex],
        LOW
    );

    timerAlarmEnable(
        timers[motorIndex]
    );
}void apply_motor_outputs(float *pidOutput)
{
    static float lastCommand[4] =
    {
        999999.0f,
        999999.0f,
        999999.0f,
        999999.0f
    };

    static bool lastDir[4] =
    {
        true,
        false,
        false,
        true
    };

    const bool invertDir[4] =
    {
        false,
        true,
        true,
        false
    };

    for(int i = 0; i < 4; i++)
    {
        //====================================================
        // Comando FINAL firmado
        //====================================================

        float commandedRPM =
            rpmSetpoints[i] + pidOutput[i];

        //====================================================
        // Motor activo
        //====================================================

        activeMotors[i] =
            fabs(commandedRPM) > 0.01f;

        //====================================================
        // Dirección
        //====================================================

        if(activeMotors[i])
        {
            directionCW[i] =
                commandedRPM >= 0.0f;

            if(directionCW[i] != lastDir[i])
            {
                lastDir[i] =
                    directionCW[i];

                bool dir =
                    directionCW[i] ^
                    invertDir[i];

                digitalWrite(
                    dirPins[i],
                    dir ? HIGH : LOW
                );
            }
        }

        //====================================================
        // Actualizar velocidad
        //====================================================

        if(fabs(commandedRPM - lastCommand[i]) > 0.001f)
        {
            lastCommand[i] =
                commandedRPM;

            update_timer_interval(
                i,
                commandedRPM
            );
        }
    }
}
static uint64_t calculate_half_period_us(
    uint8_t motorIndex,
    float commandedRPM
)
{
    const uint16_t steps_per_rev_base = 200;

    // La dirección ya se maneja con DIR.
    // Para STEP solamente necesitamos la magnitud.
    float r = fabs(commandedRPM);

    if(r <= 0.01f)
    {
        return 0;
    }

    float totalSteps =
        (float)steps_per_rev_base *
        (float)microstepping;

    float period_us =
        60000000.0f /
        (totalSteps * r);

    if(period_us <= 0.0f)
    {
        return 0;
    }

    // ISR cambia HIGH/LOW en cada interrupción,
    // por eso usamos medio período.
    return (uint64_t)(period_us / 2.0f);
}