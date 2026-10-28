import sensor
import time

# ======================================================
# FIREFIGHTER - VISION
# OPENMV H7 R2 - Firmware v5.0.0
# ======================================================

def init():

    sensor.reset()

    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.QVGA)

    # Camara montada invertida
    sensor.set_vflip(True)
    sensor.set_hmirror(True)

    # Permitir que la camara se adapte a la luz
    sensor.set_auto_gain(True)
    sensor.set_auto_whitebal(True)
    sensor.set_auto_exposure(True)

    # Esperar estabilizacion
    sensor.skip_frames(time=3000)

    # Congelar ajustes para estabilizar colores
    sensor.set_auto_gain(False)
    sensor.set_auto_whitebal(False)
    sensor.set_auto_exposure(False)

    print("Camara calibrada y estabilizada")


def snapshot():
    return sensor.snapshot()


def find_blobs(
    img,
    threshold,
    pixels_threshold,
    area_threshold,
    merge
):
    return img.find_blobs(
        [threshold],
        pixels_threshold=pixels_threshold,
        area_threshold=area_threshold,
        merge=merge
    )
