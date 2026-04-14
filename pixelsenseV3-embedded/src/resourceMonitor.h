#ifndef RESOURCEMONITOR_H
#define RESOURCEMONITOR_H

#include <Arduino.h>
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "driver/temp_sensor.h" 

class ResourceMonitor {
public:
    ResourceMonitor() {
        // Initialize the temperature sensor configuration
        temp_sensor_config_t temp_sensor = TSENS_CONFIG_DEFAULT();
        temp_sensor_set_config(temp_sensor);
        temp_sensor_start();
    }

    void getInfo(int* info) {
        // Internal Physical RAM
        multi_heap_info_t xHeapInfo;
        heap_caps_get_info(&xHeapInfo, MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL);
        uint32_t totalPhysicalSRAM = xHeapInfo.total_free_bytes + xHeapInfo.total_allocated_bytes;

        // PSRAM (External)
        bool hasPSRAM = psramFound();
        uint32_t totalPSRAM = hasPSRAM ? heap_caps_get_total_size(MALLOC_CAP_SPIRAM) : 0;
        uint32_t freePSRAM = hasPSRAM ? heap_caps_get_free_size(MALLOC_CAP_SPIRAM) : 0;

        // CPU Temperature
        float tsens_out;
        temp_sensor_read_celsius(&tsens_out);

        info[0] = (int)(totalPhysicalSRAM / 1024); 
        info[1] = (int)(totalPSRAM / 1024);
        info[2] = (int)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024);
        info[3] = (int)(freePSRAM / 1024);
        info[4] = getCpuFrequencyMhz();
        info[5] = (int)tsens_out; // CPU Temp in Celsius
    }
};

#endif