#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <libps2000/ps2000.h>

#define AWG_BUFFER_SIZE 4096
#define AWG_PHASE_ACCUMULATOR 4294967296.0   // 2^32
#define AWG_DDS_FREQUENCY     48000000.0     // 48 MHz (Pico internal clock)

int main(void)
{
    int16_t handle;
    uint8_t waveform[AWG_BUFFER_SIZE];
    int waveformSize = AWG_BUFFER_SIZE;

    // Desired signal:
    // 5 kHz repetition, 1% duty cycle, 2 Vpp, centered around 0 V
    double frequency = 5000.0;
    int32_t offset_uV = 0;
    uint32_t pkToPk_uV = 2000000;   // 2 Vpp

    // AWG values for old ps2000 API are 0..255
    // midpoint ~128
    uint8_t lowLevel  = 64;
    uint8_t highLevel = 192;

    // 1% of 4096 samples = about 41 samples high
    int highSamples = (int)(0.01 * waveformSize);
    if (highSamples < 1)
        highSamples = 1;

    // Build one pulse per period
    for (int i = 0; i < waveformSize; i++)
    {
        if (i < highSamples)
            waveform[i] = highLevel;
        else
            waveform[i] = lowLevel;
    }

    printf("Opening PicoScope...\n");
    handle = ps2000_open_unit();

    if (handle <= 0)
    {
        printf("Failed to open scope. Handle = %d\n", handle);
        return 1;
    }

    printf("Scope opened. Handle = %d\n", handle);

    // Same delta calculation used by the example
    // delta = ((frequency * waveformSize) / awgBufferSize) * AWG_PHASE_ACCUMULATOR * (1/AWG_DDS_FREQUENCY)
    // Since waveformSize == awgBufferSize here, this simplifies nicely.
    double delta = ((frequency * waveformSize) / (double)AWG_BUFFER_SIZE) *
                   AWG_PHASE_ACCUMULATOR *
                   (1.0 / AWG_DDS_FREQUENCY);

    if (!ps2000_set_sig_gen_arbitrary(
            handle,
            offset_uV,
            pkToPk_uV,
            (uint32_t)delta,
            (uint32_t)delta,
            0,
            0,
            waveform,
            waveformSize,
            PS2000_UP,
            0))
    {
        printf("Failed to configure arbitrary waveform generator.\n");
        ps2000_close_unit(handle);
        return 1;
    }

    printf("AWG ON\n");
    printf("Repetition rate: %.1f Hz\n", frequency);
    printf("Amplitude: %.2f Vpp\n", pkToPk_uV / 1000000.0);
    printf("Duty cycle: %.2f%%\n", 100.0 * highSamples / waveformSize);
    printf("High samples: %d of %d\n", highSamples, waveformSize);
    printf("Press Enter to stop...\n");

    getchar();

    ps2000_stop(handle);
    ps2000_close_unit(handle);

    printf("Stopped and closed.\n");
    return 0;
}
