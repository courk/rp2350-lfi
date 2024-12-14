ldr r2, =0x10010000
ldr r3, =0xe000ed08
str r2, [r3]
ldr r0, [r2]
ldr r1, [r2, #4]
msr msp, r0
bx r1