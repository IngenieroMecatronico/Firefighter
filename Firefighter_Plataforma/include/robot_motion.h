#ifndef ROBOT_MOTION_H
#define ROBOT_MOTION_H

#include <Arduino.h>

//============================================================
// MODOS DEL ROBOT
//============================================================

enum RobotMode
{
    MODE_MANUAL,
    MODE_SEMI_AUTO,
    MODE_AUTO
};

extern RobotMode robotMode;

//============================================================
// VELOCIDAD MANUAL
//============================================================

extern float manualRPM;

//============================================================
// FUNCIONES DE MOVIMIENTO
//============================================================

void robot_motion_init();

void robot_forward(float rpm);
void robot_backward(float rpm);

void robot_left(float rpm);
void robot_right(float rpm);

void robot_rotate_ccw(float rpm);
void robot_rotate_cw(float rpm);

void robot_stop();

void robot_set_mode(RobotMode mode);

const char *robot_mode_name();

#endif