#ifndef DEVICEMONITOR_H
#define DEVICEMONITOR_H

#include <Arduino.h>
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "driver/temp_sensor.h" 

class DeviceMonitor {
private:
    int batPin;
    float filteredVoltage = 0.0;
    const float alpha = 0.1; // filter smoothing factor
    const float referenceVoltage = 3.3;
    const float R1 = 11.8;
    const float R2 = 22.0;

public:
    DeviceMonitor(int batteryPin) {
        // Initialize the temperature sensor configuration
        temp_sensor_config_t temp_sensor = TSENS_CONFIG_DEFAULT();
        temp_sensor_set_config(temp_sensor);
        temp_sensor_start();

        batPin = batteryPin;
        pinMode(batPin, INPUT);
        analogReadResolution(12);
        analogSetAttenuation(ADC_11db);

        filteredVoltage = getRawVoltage(); // initialize filter with an actual reading
    }

    float getRawVoltage() {
        int raw = analogRead(batPin);
        float pinVoltage = (raw / 4095.0) * referenceVoltage;
        return pinVoltage * (R1 + R2)/R2;
    }

    void updateFilter() {
        float currentReading = getRawVoltage();
        filteredVoltage = (alpha * currentReading) + ((1.0 - alpha) * filteredVoltage); // exponential moving average filter
    }

    void getInfo(int* info) {
        updateFilter();

        multi_heap_info_t xHeapInfo;
        heap_caps_get_info(&xHeapInfo, MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL);
        uint32_t totalPhysicalSRAM = xHeapInfo.total_free_bytes + xHeapInfo.total_allocated_bytes;

        bool hasPSRAM = psramFound();
        uint32_t totalPSRAM = hasPSRAM ? heap_caps_get_total_size(MALLOC_CAP_SPIRAM) : 0;
        uint32_t freePSRAM = hasPSRAM ? heap_caps_get_free_size(MALLOC_CAP_SPIRAM) : 0;

        float tsens_out;
        temp_sensor_read_celsius(&tsens_out);

        info[0] = (int)(totalPhysicalSRAM / 1024);
        info[1] = (int)(totalPSRAM / 1024);
        info[2] = (int)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024);
        info[3] = (int)(freePSRAM / 1024);
        info[4] = (int)tsens_out;
        info[5] = (int)(filteredVoltage * 10); 
    }
};

#endif