
#include <Arduino.h>
#include "pid_control.h"
#include "quad_stepper.h"

float kp = 0.25f;
float ki = 0.0f;
float kd = 0.0f;

float integral[4]={0};
float prevErr[4]={0};
float output[4]={0};

void update_pid_control(float *setpoint,float *measured){

    for(int i=0;i<4;i++){

        float err=
            setpoint[i]-measured[i];
        if (fabs(err) < 2.0f)
        {
            err = 0.0f;
        }
        integral[i]+=err;

        float limit = abs(setpoint[i]) * 1.5f;

        if(integral[i] > limit)
            integral[i] = limit;

        if(integral[i] < -limit)
            integral[i] = -limit;

        float deriv=
            err-prevErr[i];

        output[i]=
            kp*err+
            ki*integral[i]+
            kd*deriv;

        //if(abs(output[i])<
        //   abs(setpoint[i])*0.05f){

        //    output[i]=0;
        //}

        prevErr[i]=err;
    }

    apply_motor_outputs(output);
}
