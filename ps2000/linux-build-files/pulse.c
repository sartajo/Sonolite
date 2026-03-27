#include <stdio.h>
#include <stdint.h>
#include <libps2000/ps2000.h>

int main(void)
{
    int16_t handle;
    int16_t status;

    int32_t offset_uv = 0;
    uint32_t pk_to_pk_uv = 2000000;   // 2 Vpp
    float frequency = 5000.0f;        // 5 kHz

    printf("Opening PicoScope...\n");
    handle = ps2000_open_unit();

    if (handle <= 0)
    {
        printf("Failed to open scope. Handle = %d\n", handle);
        return 1;
    }

    printf("Scope opened. Handle = %d\n", handle);

    status = ps2000_set_sig_gen_built_in(
        handle,
        offset_uv,
        pk_to_pk_uv,
        PS2000_SQUARE,
        frequency,
        frequency,
        0.0f,          // increment
        0.0f,          // dwell time
        PS2000_UP,     // sweep type
        0              // sweeps
    );

    if (status == 0)
    {
        printf("Failed to configure signal generator.\n");
        ps2000_close_unit(handle);
        return 1;
    }

    printf("Signal generator ON\n");
    printf("Waveform: square\n");
    printf("Frequency: %.1f Hz\n", frequency);
    printf("Amplitude: %.2f Vpp\n", pk_to_pk_uv / 1000000.0);
    printf("Press Enter to stop...\n");

    getchar();

    ps2000_stop(handle);
    ps2000_close_unit(handle);

    printf("Signal generator stopped and scope closed.\n");
    return 0;
}
