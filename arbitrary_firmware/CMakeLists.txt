cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(test_project C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(firmware
        firmware.c
)

pico_set_linker_script(firmware ${CMAKE_SOURCE_DIR}/memmap_shifted.ld)

pico_enable_stdio_usb(firmware 1)
pico_enable_stdio_uart(firmware 0)

pico_add_extra_outputs(firmware)
target_link_libraries(firmware pico_stdlib)
