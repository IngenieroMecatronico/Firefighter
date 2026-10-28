#include <Arduino.h>
#include "as5600_reader.h"
#include "quad_stepper.h"

const int encPins[4] = {34, 35, 33, 32};

float prevAngle[4] = {0, 0, 0, 0};

// Acumuladores para calcular RPM sobre una ventana mayor
float accumulatedAngle[4] = {0, 0, 0, 0};

unsigned long lastUpdateUs = 0;
unsigned long rpmWindowStartUs = 0;

//============================================================
// Leer ángulo
//============================================================

static float read_angle(int pin)
{
    const uint8_t samples = 15;

    uint32_t sum = 0;

    for (uint8_t i = 0; i < samples; i++)
    {
        sum += analogRead(pin);
    }

    float adcValue =
        (float)sum / (float)samples;

    return (adcValue / 4096.0f) * 360.0f;
}

//============================================================
// Inicialización
//============================================================

void as5600_init()
{
    analogReadResolution(12);

    delay(50);

    for (int i = 0; i < 4; i++)
    {
        prevAngle[i] = read_angle(encPins[i]);

        accumulatedAngle[i] = 0.0f;
    }

    lastUpdateUs = micros();
    rpmWindowStartUs = lastUpdateUs;
}

//============================================================
// Actualización
//============================================================

void update_as5600_all(float *rpmMeasured)
{
    unsigned long now = micros();

    //--------------------------------------------------------
    // Leer los 4 sensores
    //--------------------------------------------------------

    for (int i = 0; i < 4; i++)
    {
        float currentAngle =
            read_angle(encPins[i]);

        float delta =
            currentAngle - prevAngle[i];

        //----------------------------------------------------
        // Corrección 360 -> 0
        //----------------------------------------------------

        if (delta > 180.0f)
        {
            delta -= 360.0f;
        }

        if (delta < -180.0f)
        {
            delta += 360.0f;
        }

        //----------------------------------------------------
        // Rechazar ruido pequeño
        //----------------------------------------------------

        if (fabs(delta) < 0.5f)
        {
            delta = 0.0f;
        }

        //----------------------------------------------------
        // Acumular desplazamiento
        //----------------------------------------------------

        accumulatedAngle[i] += delta;

        prevAngle[i] = currentAngle;
    }

    //--------------------------------------------------------
    // Calcular RPM cada 250 ms
    //--------------------------------------------------------

    unsigned long elapsedUs =
        now - rpmWindowStartUs;

    if (elapsedUs >= 500000)
    {
        float elapsedSeconds =
            elapsedUs / 1000000.0f;

        for (int i = 0; i < 4; i++)
        {
            float revolutions =
                accumulatedAngle[i] / 360.0f;

            float rpm =
                revolutions *
                (60.0f / elapsedSeconds);

            rpmMeasured[i] = fabs(rpm);

            accumulatedAngle[i] = 0.0f;
        }

        rpmWindowStartUs = now;
    }

    lastUpdateUs = now;
}

//============================================================
// ADC crudo para diagnóstico
//============================================================

int read_as5600_raw(int index)
{
    if (index < 0 || index > 3)
    {
        return -1;
    }

    return analogRead(encPins[index]);
}