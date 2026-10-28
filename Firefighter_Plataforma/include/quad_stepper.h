
#pragma once
void quad_stepper_init();
void apply_motor_outputs(float *outputs);
void enable_motors(bool state);
extern bool directionCW[4];
