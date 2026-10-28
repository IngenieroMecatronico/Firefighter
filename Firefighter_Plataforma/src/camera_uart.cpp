#include "camera_uart.h"

//============================================================
// FIREFIGHTER - ESP32 PRINCIPAL
// UART0 <-> ESP32-C3
//
// GPIO1 TX -> C3 GPIO20 RX
// GPIO3 RX <- C3 GPIO21 TX
//
// 115200 baud
//
// Cola FIFO para evitar perder mensajes UART.
//============================================================

// Buffer para construir cada linea recibida.
static String rxBuffer = "";

// Cola de mensajes completos.
static const uint8_t RX_QUEUE_SIZE = 16;

static String rxQueue[RX_QUEUE_SIZE];

static uint8_t queueHead = 0;
static uint8_t queueTail = 0;
static uint8_t queueCount = 0;

//============================================================
// GUARDAR MENSAJE
//============================================================

static void queuePush(const String &message)
{
    if (message.length() == 0)
        return;

    // Cola llena: no sobrescribir mensajes anteriores.
    if (queueCount >= RX_QUEUE_SIZE)
        return;

    rxQueue[queueTail] = message;

    queueTail =
        (queueTail + 1) % RX_QUEUE_SIZE;

    queueCount++;
}

//============================================================
// INICIALIZAR UART0
//============================================================

void camera_uart_init()
{
    Serial.begin(115200, SERIAL_8N1, 3, 1);

    rxBuffer = "";

    queueHead = 0;
    queueTail = 0;
    queueCount = 0;

    delay(100);
}

//============================================================
// ENVIAR MENSAJE AL C3
//============================================================

void camera_uart_send(const String &message)
{
    Serial.println(message);
}

//============================================================
// RECIBIR MENSAJES
//============================================================

void camera_uart_update()
{
    while (Serial.available() > 0)
    {
        char c = (char)Serial.read();

        // Ignorar retorno de carro.
        if (c == '\r')
            continue;

        // Mensaje completo.
        if (c == '\n')
        {
            rxBuffer.trim();

            if (rxBuffer.length() > 0)
                queuePush(rxBuffer);

            rxBuffer = "";

            continue;
        }

        // Construir mensaje.
        rxBuffer += c;

        // Proteccion ante datos corruptos.
        if (rxBuffer.length() > 128)
            rxBuffer = "";
    }
}

//============================================================
// MENSAJES DISPONIBLES
//============================================================

bool camera_uart_available()
{
    return queueCount > 0;
}

//============================================================
// OBTENER SIGUIENTE MENSAJE FIFO
//============================================================

String camera_uart_get_message()
{
    if (queueCount == 0)
        return "";

    String message = rxQueue[queueHead];

    rxQueue[queueHead] = "";

    queueHead =
        (queueHead + 1) % RX_QUEUE_SIZE;

    queueCount--;

    return message;
}