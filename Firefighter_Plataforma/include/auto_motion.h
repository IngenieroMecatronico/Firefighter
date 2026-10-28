#ifndef AUTO_MOTION_H
#define AUTO_MOTION_H
#include <Arduino.h>
// Ordenes provenientes del C3, no de UDP.
void auto_motion_init();
void auto_motion_enter();
void auto_motion_exit();
void auto_motion_estop();
void auto_motion_update();
bool auto_motion_handle(const String &message);
#endif
