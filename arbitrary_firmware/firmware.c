#include <stdio.h>

#include "pico/stdlib.h"

#include "hardware/clocks.h"
#include "hardware/pll.h"
#include "hardware/ticks.h"
#include "hardware/xosc.h"

#include "hardware/structs/qmi.h"
#include "hardware/regs/qmi.h"

#include "pico/runtime_init.h"

static void start_all_ticks(void)
{
    uint32_t cycles = clock_get_hz(clk_ref) / MHZ;
    // Note RP2040 has a single tick generator in the watchdog which serves
    // watchdog, system timer and M0+ SysTick; The tick generator is clocked from clk_ref
    // but is now adapted by the hardware_ticks library for compatibility with RP2350
    // npte: hardware_ticks library now provides an adapter for RP2040

    for (int i = 0; i < (int)TICK_COUNT; ++i)
    {
        tick_start((tick_gen_num_t)i, cycles);
    }
}

// Overwrite runtime_init_clocks to make sure the system runs at a reduced speed.
// That's needed because of the RP2350 sample preparation for this attack: the connection
// to ground isn't great, causing stability issues at high clock speeds.
void runtime_init_clocks(void)
{
    // Note: These need setting *before* the ticks are started
    // Disable resus that may be enabled from previous software
    clocks_hw->resus.ctrl = 0;

    // Increase the clock divider of the SPI flash to avoid running
    // into data integrity issues caused by the sample preparation
    qmi_hw->m[0].timing = (1 << QMI_M0_TIMING_COOLDOWN_LSB) | (4 << QMI_M0_TIMING_RXDELAY_LSB) | (32 << QMI_M0_TIMING_CLKDIV_LSB);

    // Enable the xosc
    xosc_init();

    // Before we touch PLLs, switch sys and ref cleanly away from their aux sources.
    hw_clear_bits(&clocks_hw->clk[clk_sys].ctrl, CLOCKS_CLK_SYS_CTRL_SRC_BITS);
    while (clocks_hw->clk[clk_sys].selected != 0x1)
        tight_loop_contents();
    hw_clear_bits(&clocks_hw->clk[clk_ref].ctrl, CLOCKS_CLK_REF_CTRL_SRC_BITS);
    while (clocks_hw->clk[clk_ref].selected != 0x1)
        tight_loop_contents();

    /// \tag::pll_init[]
    pll_init(pll_sys, PLL_SYS_REFDIV, PLL_SYS_VCO_FREQ_HZ, PLL_SYS_POSTDIV1, PLL_SYS_POSTDIV2);
    pll_init(pll_usb, PLL_USB_REFDIV, PLL_USB_VCO_FREQ_HZ, PLL_USB_POSTDIV1, PLL_USB_POSTDIV2);
    /// \end::pll_init[]

    // Configure clocks

    // RP2040 CLK_REF = XOSC (usually) 12MHz / 1 = 12MHz
    // RP2350 CLK_REF = XOSC (XOSC_MHZ) / N (1,2,4) = 12MHz

    // clk_ref aux select is 0 because:
    //
    // - RP2040: no aux mux on clk_ref, so this field is don't-care.
    //
    // - RP2350: there is an aux mux, but we are selecting one of the
    //   non-aux inputs to the glitchless mux, so the aux select doesn't
    //   matter. The value of 0 here happens to be the sys PLL.

    clock_configure_undivided(clk_ref,
                              CLOCKS_CLK_REF_CTRL_SRC_VALUE_XOSC_CLKSRC,
                              0,
                              XOSC_HZ);

    /// \tag::configure_clk_sys[]
    // CLK SYS = PLL SYS (usually) 125MHz / 1 = 125MHz
    clock_configure_undivided(clk_sys,
                              CLOCKS_CLK_SYS_CTRL_SRC_VALUE_CLKSRC_CLK_SYS_AUX,
                              CLOCKS_CLK_SYS_CTRL_AUXSRC_VALUE_CLKSRC_PLL_SYS,
                              SYS_CLK_HZ);
    /// \end::configure_clk_sys[]

    // CLK USB = PLL USB 48MHz / 1 = 48MHz
    clock_configure_undivided(clk_usb,
                              0, // No GLMUX
                              CLOCKS_CLK_USB_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB,
                              USB_CLK_HZ);

    // CLK ADC = PLL USB 48MHZ / 1 = 48MHz
    clock_configure_undivided(clk_adc,
                              0, // No GLMUX
                              CLOCKS_CLK_ADC_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB,
                              USB_CLK_HZ);

    // CLK PERI = clk_sys. Used as reference clock for UART and SPI serial.
    clock_configure_undivided(clk_peri,
                              0,
                              CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS,
                              SYS_CLK_HZ);

    // Finally, all clocks are configured so start the ticks
    // The ticks use clk_ref so now that is configured we can start them
    start_all_ticks();
}

void runtime_init_post_clock_resets(void)
{
}

int main()
{
    stdio_init_all();

    while (true)
    {
        printf("Success!\n");

        volatile uint32_t *otp_guarded_data_ptr = ((uint32_t *)(OTP_DATA_BASE + (0xc08 * 2)));
        printf("%04X", *otp_guarded_data_ptr & 0xFFFF);
        printf("%04X\n\n", (*otp_guarded_data_ptr & 0xFFFF0000) >> 16);

        sleep_ms(200);
    }
}
