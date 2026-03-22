#ifndef RESOURCEMONITOR_H
#define RESOURCEMONITOR_H

#include <Arduino.h>
#include "esp_system.h"
#include "esp_heap_caps.h"

class ResourceMonitor{
    private:
    public:
        ResourceMonitor(){} // void constructor

        void getInfo(int* info){
            // "visible" Data Heap 
            uint32_t heapSRAM = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
            
            // Total Internal Physical RAM (Closer to the 512KB)
            // This includes regions not normally available for 'malloc'
            multi_heap_info_t xHeapInfo;
            heap_caps_get_info(&xHeapInfo, MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL);
            uint32_t totalPhysicalSRAM = xHeapInfo.total_free_bytes + xHeapInfo.total_allocated_bytes;

            // PSRAM (External)
            bool hasPSRAM = psramFound();
            uint32_t totalPSRAM = hasPSRAM ? heap_caps_get_total_size(MALLOC_CAP_SPIRAM) : 0;
            uint32_t freePSRAM = hasPSRAM ? heap_caps_get_free_size(MALLOC_CAP_SPIRAM) : 0;

            info[0] = (int)(totalPhysicalSRAM / 1024); // The "Actual" Total (should be ~320-400KB)
            info[1] = (int)(totalPSRAM / 1024);
            info[2] = (int)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024);
            info[3] = (int)(freePSRAM / 1024);
            info[4] = getCpuFrequencyMhz();
        }
};

#endif