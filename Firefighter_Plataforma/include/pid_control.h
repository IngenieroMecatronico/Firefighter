#ifndef PID_CONTROL_H
#define PID_CONTROL_H

#include <Arduino.h>

extern float kp;
extern float ki;
extern float kd;

extern float output[4];

void update_pid_control(
    float *setpoint,
    float *measured
);

#endif