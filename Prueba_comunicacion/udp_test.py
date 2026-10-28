import socket

ESP32_IP = "192.168.50.171"
ESP32_PORT = 12345

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

sock.bind(("", 12346))

# Registrar esta PC en el ESP32
sock.sendto(
    b"ping",
    (ESP32_IP, ESP32_PORT)
)

print("Esperando ESP32...")

while True:
    data, addr = sock.recvfrom(2048)

    mensaje = data.decode(
        errors="replace"
    )

    print(mensaje)

    if mensaje == "pong":
        break

# Ordenar M1 a 30 RPM
sock.sendto(
    b"m3_rpm=30",
    (ESP32_IP, ESP32_PORT)
)

# Habilitar motores
sock.sendto(
    b"start",
    (ESP32_IP, ESP32_PORT)
)

print()
print("==============================")
print("ADC DE LOS 4 SENSORES")
print("==============================")
print()

try:
    while True:
        data, addr = sock.recvfrom(2048)

        print(
            data.decode(
                errors="replace"
            )
        )

except KeyboardInterrupt:

    print()
    print("Deteniendo M1...")

    sock.sendto(
        b"stop",
        (ESP32_IP, ESP32_PORT)
    )