
# ======================================================
# FIREFIGHTER - OPENMV H7 R2
# ARCHIVO: pan.py
#
# CONTROLADOR VISUAL IBVS DEL EJE PAN
#
# FUNCIONES:
#
# 1. Realizar el barrido horizontal SEARCH.
# 2. Seguir el objetivo mediante TRACKING IBVS.
# 3. Suavizar la posicion del blob con filtro EMA.
# 4. Aplicar el offset horizontal de la manguera.
# 5. Respetar los limites mecanicos del servo PAN.
# 6. Detectar cuando PAN llega a sus limites.
# 7. Informar a main.py si se necesita corregir
#    la orientacion del chasis.
#
# ARQUITECTURA:
#
# OpenMV H7 R2:
#   - Detecta el objetivo.
#   - Calcula el error horizontal.
#   - Calcula la referencia angular PAN.
#
# ESP32-C3:
#   - Recibe PAN_TARGET.
#   - Genera el PWM del servo.
#
# ESP32 PRINCIPAL:
#   - Ejecuta los giros correctivos del chasis
#     cuando main.py los solicita.
#
# IMPORTANTE:
#
# Este archivo NO mueve directamente el chasis.
# Solamente controla PAN y proporciona informacion
# para que main.py decida si necesita girar.
#
# MANUAL:
#   PAN es controlado desde el PS4 por el C3.
#
# SEMI:
#   SEARCH + TRACKING IBVS.
#
# AUTO:
#   SEARCH + TRACKING IBVS.
#   Si PAN se satura, main.py puede solicitar
#   un giro correctivo del chasis.
# ======================================================

import config
import camera_uart


# ======================================================
# 1. ESTADO DEL CONTROLADOR PAN
# ======================================================

# Referencia angular interna del controlador.
#
# Rango:
#   -90 grados ... +90 grados
#
# No corresponde directamente al angulo PWM
# del servo conectado al ESP32-C3.

pan_angle = config.PAN_HOME


# Posicion utilizada durante el barrido SEARCH.
scan_angle = config.SCAN_MIN


# Direccion del barrido:
#
# +1 = aumentar referencia PAN.
# -1 = disminuir referencia PAN.

direction = 1


# Posicion horizontal filtrada del objetivo.
#
# Inicialmente coincide con el centro optico
# de la imagen.

cx_filtrado = config.IMG_CX


# ======================================================
# 2. CONFIGURACION DE LIMITES
# ======================================================

# Margen de seguridad para identificar cuando
# PAN esta cerca de un extremo.
#
# Esta variable NO modifica los limites mecanicos.
# Solo permite detectar proximidad al limite.

PAN_LIMIT_MARGIN_DEG = 5.0


# ======================================================
# 3. CONVERTIR ANGULO INTERNO A REFERENCIA C3
#
# Controlador OpenMV:
#   -90 ... +90
#
# Servo ESP32-C3:
#   10 ... 170 grados
#
# Se utiliza un mapeo lineal.
#
# Ejemplos aproximados:
#
# PAN interno -90 -> C3 10
# PAN interno   0 -> C3 90
# PAN interno +90 -> C3 170
#
# El signo fisico del movimiento depende
# de como este montado el servo.
# ======================================================

def controller_to_c3(angle):

    # Evitar referencias fuera del rango interno.
    angle = max(
        config.SCAN_MIN,
        min(config.SCAN_MAX, angle)
    )

    # Normalizar el angulo entre 0 y 1.
    normalized = (
        angle - config.SCAN_MIN
    ) / (
        config.SCAN_MAX - config.SCAN_MIN
    )

    # Convertir al rango angular del C3.
    target = (
        config.C3_PAN_MIN
        + normalized *
        (config.C3_PAN_MAX - config.C3_PAN_MIN)
    )

    return target


# ======================================================
# 4. ENVIAR REFERENCIA PAN AL ESP32-C3
#
# Protocolo:
#
# OpenMV -> C3:
#
# PAN_TARGET=90.0
#
# El C3 interpreta la referencia y genera PWM.
# ======================================================

def send_target():

    target = controller_to_c3(pan_angle)

    camera_uart.send(
        "PAN_TARGET={:.1f}".format(target)
    )


# ======================================================
# 5. DETECTAR LIMITES DEL CONTROLADOR
#
# IMPORTANTE:
#
# La OpenMV no recibe realimentacion angular
# del servo PAN.
#
# Por tanto, estas funciones detectan cuando
# la REFERENCIA enviada esta cerca del limite,
# no cuando el servo fisico lo alcanza.
#
# Esto se utiliza exclusivamente como indicador
# para la navegacion AUTO.
# ======================================================

def at_left_limit():

    return (
        pan_angle <=
        config.SCAN_MIN + PAN_LIMIT_MARGIN_DEG
    )


def at_right_limit():

    return (
        pan_angle >=
        config.SCAN_MAX - PAN_LIMIT_MARGIN_DEG
    )


# ======================================================
# 6. DETERMINAR NECESIDAD DE CORRECCION
#
# Se utiliza el error visual compensado.
#
# Devuelve:
#
# "LEFT":
#   PAN esta en su limite izquierdo y el
#   objetivo sigue desalineado.
#
# "RIGHT":
#   PAN esta en su limite derecho y el
#   objetivo sigue desalineado.
#
# None:
#   PAN todavia puede corregir o el objetivo
#   ya esta suficientemente alineado.
#
# NOTA:
#
# LEFT y RIGHT representan el limite logico
# del controlador, no garantizan por si solos
# el sentido fisico del giro del chasis.
# ======================================================

def correction_needed(error_x):

    # Si ya estamos dentro de la banda de
    # alineacion, no necesitamos corregir.
    if abs(error_x) <= config.DEADBAND:
        return None

    # Solo solicitar correccion si el error
    # intenta empujar PAN mas alla del limite.
    #
    # error_x < 0:
    #   el controlador intenta disminuir PAN.
    #
    # error_x > 0:
    #   el controlador intenta aumentar PAN.

    if at_left_limit() and error_x < 0:
        return "LEFT"

    if at_right_limit() and error_x > 0:
        return "RIGHT"

    return None


# ======================================================
# 7. BARRIDO HORIZONTAL SEARCH
#
# PAN recorre el intervalo:
#
# SCAN_MIN -> SCAN_MAX -> SCAN_MIN
#
# Durante SEARCH no aplicamos X_OFFSET.
#
# El objetivo es explorar el campo visual,
# no apuntar la manguera.
#
# El desplazamiento angular es de 1 grado
# interno por llamada.
#
# El tiempo real de barrido depende de la
# frecuencia con que main.py llama search().
# ======================================================

def search(blobs, state):

    global pan_angle
    global scan_angle
    global direction
    global cx_filtrado

    # Aplicar referencia actual del barrido.
    pan_angle = scan_angle

    # Enviar nueva posicion al servo.
    send_target()

    # Calcular siguiente posicion.
    scan_angle += direction

    # Limite superior del barrido.
    if scan_angle >= config.SCAN_MAX:

        scan_angle = config.SCAN_MAX
        direction = -1

    # Limite inferior del barrido.
    elif scan_angle <= config.SCAN_MIN:

        scan_angle = config.SCAN_MIN
        direction = 1

    # Si existe un blob candidato, pasar
    # al estado TRACKING.
    if blobs:

        print("[PAN] OBJETIVO ENCONTRADO")

        blob = max(
            blobs,
            key=lambda b: b.pixels
        )

        # Inicializar el filtro en la posicion
        # observada para evitar saltos grandes.
        cx_filtrado = blob.cx

        return config.TRACKING

    return state


# ======================================================
# 8. TRACKING IBVS PAN
#
# El objetivo es reducir el error horizontal
# entre el centroide del blob y la referencia
# de apuntado.
#
# Referencia:
#
# IMG_CX = 160
# X_OFFSET = -80
#
# Objetivo horizontal:
#
# 160 - 80 = 80 pixeles
#
# Por tanto, la llama debe estabilizarse
# aproximadamente en X = 80.
#
# El offset compensa la separacion fisica
# entre la camara y la manguera.
# ======================================================

def tracking(
    blobs,
    state,
    IMG_CX,
    ALPHA,
    KP,
    DEADBAND,
    MAX_STEP
):

    global pan_angle
    global scan_angle
    global cx_filtrado

    # ==================================================
    # 8.1 OBJETIVO PERDIDO
    # ==================================================

    if not blobs:

        print("[PAN] OBJETIVO PERDIDO")

        # Reanudar el barrido desde la ultima
        # posicion angular utilizada.
        scan_angle = pan_angle

        return config.SEARCH, None

    # ==================================================
    # 8.2 SELECCIONAR BLOB PRINCIPAL
    # ==================================================

    blob = max(
        blobs,
        key=lambda b: b.pixels
    )

    cx = blob.cx

    # ==================================================
    # 8.3 FILTRO EXPONENCIAL EMA
    #
    # Reduce variaciones bruscas del centroide.
    #
    # Se conserva la convencion original:
    #
    # cx_filtrado =
    #     ALPHA * anterior
    #     + (1 - ALPHA) * actual
    # ==================================================

    cx_filtrado = (
        ALPHA * cx_filtrado
        + (1 - ALPHA) * cx
    )

    # ==================================================
    # 8.4 REFERENCIA HORIZONTAL COMPENSADA
    #
    # El offset se obtiene desde config.py.
    #
    # No se fija numericamente aqui para
    # conservar la calibracion existente.
    # ==================================================

    objetivo_x = IMG_CX + config.X_OFFSET

    error_x = objetivo_x - cx_filtrado

    # ==================================================
    # 8.5 CONTROLADOR PROPORCIONAL
    #
    # Si el error supera DEADBAND, aplicar
    # una correccion proporcional limitada.
    # ==================================================

    if abs(error_x) > DEADBAND:

        correccion = KP * error_x

        # Limitar magnitud de correccion.
        if correccion > MAX_STEP:
            correccion = MAX_STEP

        elif correccion < -MAX_STEP:
            correccion = -MAX_STEP

        # Actualizar referencia PAN.
        pan_angle += correccion

    # ==================================================
    # 8.6 LIMITES DEL CONTROLADOR
    #
    # Evita enviar referencias fuera
    # del intervalo permitido.
    # ==================================================

    if pan_angle > config.SCAN_MAX:
        pan_angle = config.SCAN_MAX

    elif pan_angle < config.SCAN_MIN:
        pan_angle = config.SCAN_MIN

    # ==================================================
    # 8.7 ENVIAR REFERENCIA AL C3
    # ==================================================

    send_target()

    # ==================================================
    # 8.8 INFORMACION PARA MAIN.PY
    #
    # Incluimos los datos originales y algunos
    # indicadores adicionales.
    #
    # main.py puede utilizar correction_needed()
    # para decidir si necesita un giro del chasis.
    # ==================================================

    correction = correction_needed(error_x)

    return state, {
        "blob": blob,
        "cx": cx,
        "cx_filtrado": cx_filtrado,
        "error": error_x,
        "pan_angle": pan_angle,
        "c3_target": controller_to_c3(pan_angle),
        "at_left_limit": at_left_limit(),
        "at_right_limit": at_right_limit(),
        "correction_needed": correction
    }


# ======================================================
# 9. CENTRAR PAN
#
# Restablece el controlador a PAN_HOME.
#
# No modifica X_OFFSET.
#
# Utilizado para devolver el servo a su
# referencia central.
# ======================================================

def center():

    global pan_angle
    global scan_angle
    global cx_filtrado

    pan_angle = config.PAN_HOME
    scan_angle = config.PAN_HOME

    cx_filtrado = config.IMG_CX

    send_target()
