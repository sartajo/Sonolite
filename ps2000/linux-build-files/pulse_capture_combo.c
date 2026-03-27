#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <libps2000/ps2000.h>

#define BUFFER_SIZE 4096

static int32_t input_ranges[PS2000_MAX_RANGES] =
{
    10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000
};

static int32_t adc_to_mv(int32_t raw, int32_t range)
{
    return (raw * input_ranges[range]) / 32767;
}

int main(void)
{
    int16_t handle;
    int16_t overflow = 0;

    int32_t times[BUFFER_SIZE];
    int16_t values_a[BUFFER_SIZE];

    // Channel settings
    int16_t channel = PS2000_CHANNEL_A;
    int16_t enabled = 1;
    int16_t dc = 1;
    int16_t range = PS2000_500MV;   // change if needed

    // Acquisition settings
    int16_t oversample = 1;
    int16_t timebase = 1;
    int32_t time_interval = 0;
    int16_t time_units = 0;
    int32_t max_samples = 0;
    int32_t time_indisposed_ms = 0;

    // Signal generator settings
    int32_t offset_uv = 0;
    uint32_t pk_to_pk_uv = 2000000;   // 2 Vpp
    float frequency = 5000.0f;        // 5 kHz

    int scan_index = 0;

    printf("Creating capture folder...\n");
    if (mkdir("captures", 0777) != 0 && errno != EEXIST)
    {
        perror("Failed to create captures folder");
        return 1;
    }

    printf("Opening PicoScope...\n");
    handle = ps2000_open_unit();

    if (handle <= 0)
    {
        printf("Failed to open scope. Handle = %d\n", handle);
        return 1;
    }

    printf("Opened. Handle = %d\n", handle);

    // Enable Channel A
    if (!ps2000_set_channel(handle, channel, enabled, dc, range))
    {
        printf("Failed to set Channel A.\n");
        ps2000_close_unit(handle);
        return 1;
    }

    // Disable Channel B
    ps2000_set_channel(handle, PS2000_CHANNEL_B, 0, dc, range);

    // Find a valid timebase
    while (!ps2000_get_timebase(handle,
                                timebase,
                                BUFFER_SIZE,
                                &time_interval,
                                &time_units,
                                oversample,
                                &max_samples))
    {
        timebase++;
    }

    printf("Using timebase = %d\n", timebase);
    printf("Time interval = %d ", time_interval);

    switch (time_units)
    {
        case PS2000_FS: printf("fs\n"); break;
        case PS2000_PS: printf("ps\n"); break;
        case PS2000_NS: printf("ns\n"); break;
        case PS2000_US: printf("us\n"); break;
        case PS2000_MS: printf("ms\n"); break;
        default:        printf("(unknown units)\n"); break;
    }

    // Start built-in signal generator
    if (!ps2000_set_sig_gen_built_in(handle,
                                     offset_uv,
                                     pk_to_pk_uv,
                                     PS2000_SQUARE,
                                     frequency,
                                     frequency,
                                     0.0f,
                                     0.0f,
                                     PS2000_UP,
                                     0))
    {
        printf("Failed to start signal generator.\n");
        ps2000_close_unit(handle);
        return 1;
    }

    printf("\nSignal generator ON\n");
    printf("Waveform : square\n");
    printf("Frequency: %.1f Hz\n", frequency);
    printf("Amplitude: %.2f Vpp\n", pk_to_pk_uv / 1000000.0);
    printf("\nPress Enter to capture a waveform.\n");
    printf("Type q then Enter to quit.\n\n");

    while (1)
    {
        char line[16];
        char filename[128];
        FILE *fp = NULL;

        printf("Capture command > ");
        if (!fgets(line, sizeof(line), stdin))
            break;

        if (line[0] == 'q' || line[0] == 'Q')
            break;

        // Run immediate block capture
        if (!ps2000_run_block(handle, BUFFER_SIZE, timebase, oversample, &time_indisposed_ms))
        {
            printf("Failed to run block capture.\n");
            continue;
        }

        while (!ps2000_ready(handle))
        {
            usleep(1000);
        }

        ps2000_stop(handle);

        if (!ps2000_get_times_and_values(handle,
                                         times,
                                         values_a,
                                         NULL,
                                         NULL,
                                         NULL,
                                         &overflow,
                                         time_units,
                                         BUFFER_SIZE))
        {
            printf("Failed to get captured values.\n");
            continue;
        }

        snprintf(filename, sizeof(filename), "captures/scan_%03d.csv", scan_index);

        fp = fopen(filename, "w");
        if (!fp)
        {
            printf("Failed to create %s\n", filename);
            continue;
        }

        fprintf(fp, "sample,time_raw,adc,mv\n");
        for (int i = 0; i < BUFFER_SIZE; i++)
        {
            fprintf(fp, "%d,%d,%d,%d\n",
                    i,
                    times[i],
                    values_a[i],
                    adc_to_mv(values_a[i], range));
        }

        fclose(fp);

        printf("Saved %s\n", filename);
        scan_index++;
    }

    ps2000_close_unit(handle);
    printf("Closed PicoScope.\n");
    return 0;
}
