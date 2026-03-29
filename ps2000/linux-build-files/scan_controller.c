/*
 * Scan Controller (PicoScope + Servo + B-mode Pipeline)
 *
 * This program performs an automated ultrasound scan by coordinating:
 *   1) PicoScope signal generation and waveform capture
 *   2) Servo motor movement between scan positions
 *   3) Post-processing via a Python B-mode reconstruction script
 *
 * Workflow:
 *   - Creates a new folder (capture_XX) for the scan session
 *   - Initializes the PicoScope and enables the built-in signal generator
 *   - Performs a scan from 0° to 180° in fixed angular steps
 *       • At each position:
 *           - Captures a waveform (A-scan)
 *           - Saves it as scan_XXX.csv
 *           - Moves the servo to the next angle
 *   - After the final capture at 180°:
 *       • Moves the servo back to the home position (0°)
 *   - Calls bMode.py to reconstruct and save the final image
 *
 * Key Notes:
 *   - Step size (STEP_DEG) controls both motion and number of captures
 *   - Total captures = (180 / STEP_DEG) + 1
 *   - Each CSV contains: sample index, time_raw, ADC value, and voltage (mV)
 *   - All output (data + image) is stored in the generated capture folder
 *
 * Dependencies:
 *   - PicoSDK (libps2000)
 *   - Python scripts: servo_step.py and bMode.py
 *
 * Compile:
 *   gcc scan_controller.c -o scan_controller \
 *       -I/opt/picoscope/include/libps2000 \
 *       -L/opt/picoscope/lib \
 *       -lps2000
 *
 *           Authored by Omar Sartaj
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <string.h>
#include <limits.h>

#include <ps2000.h>

#define BUFFER_SIZE 4096
#define MAX_PATH_LEN 1024

#define MAX_ANGLE_DEG 180
#define STEP_DEG 10

static int32_t input_ranges[PS2000_MAX_RANGES] =
{
    10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000
};

static int32_t adc_to_mv(int32_t raw, int32_t range)
{
    return (raw * input_ranges[range]) / 32767;
}

static int folder_exists(const char *path)
{
    struct stat st;
    return (stat(path, &st) == 0 && S_ISDIR(st.st_mode));
}

static int create_next_capture_folder(char *foldername, size_t len)
{
    int index = 0;

    while (1)
    {
        snprintf(foldername, len, "capture_%02d", index);

        if (!folder_exists(foldername))
        {
            if (mkdir(foldername, 0777) != 0)
            {
                perror("Failed to create capture folder");
                return 0;
            }

            return 1;
        }

        index++;
        if (index > 9999)
        {
            fprintf(stderr, "Too many capture folders.\n");
            return 0;
        }
    }
}

static int init_scope(int16_t *handle,
                      int16_t channel,
                      int16_t enabled,
                      int16_t dc,
                      int16_t range,
                      int16_t *timebase,
                      int16_t oversample,
                      int32_t *time_interval,
                      int16_t *time_units,
                      int32_t *max_samples)
{
    *handle = ps2000_open_unit();

    if (*handle <= 0)
    {
        printf("Failed to open scope. Handle = %d\n", *handle);
        return 0;
    }

    printf("Opened PicoScope. Handle = %d\n", *handle);

    if (!ps2000_set_channel(*handle, channel, enabled, dc, range))
    {
        printf("Failed to set Channel A.\n");
        ps2000_close_unit(*handle);
        return 0;
    }

    if (!ps2000_set_channel(*handle, PS2000_CHANNEL_B, 0, dc, range))
    {
        printf("Warning: failed to disable Channel B.\n");
    }

    while (!ps2000_get_timebase(*handle,
                                *timebase,
                                BUFFER_SIZE,
                                time_interval,
                                time_units,
                                oversample,
                                max_samples))
    {
        (*timebase)++;
    }

    printf("Using timebase = %d\n", *timebase);
    printf("Time interval = %d ", *time_interval);

    switch (*time_units)
    {
        case PS2000_FS: printf("fs\n"); break;
        case PS2000_PS: printf("ps\n"); break;
        case PS2000_NS: printf("ns\n"); break;
        case PS2000_US: printf("us\n"); break;
        case PS2000_MS: printf("ms\n"); break;
        default:        printf("(unknown units)\n"); break;
    }

    return 1;
}

static int setup_signal_generator(int16_t handle,
                                  int32_t offset_uv,
                                  uint32_t pk_to_pk_uv,
                                  float frequency)
{
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
        return 0;
    }

    printf("\nSignal generator ON\n");
    printf("Waveform : square\n");
    printf("Frequency: %.1f Hz\n", frequency);
    printf("Amplitude: %.2f Vpp\n\n", pk_to_pk_uv / 1000000.0);

    return 1;
}

static int capture_and_save(int16_t handle,
                            int16_t range,
                            int16_t timebase,
                            int16_t oversample,
                            int16_t time_units,
                            const char *filename)
{
    int16_t overflow = 0;
    int32_t time_indisposed_ms = 0;

    int32_t times[BUFFER_SIZE];
    int16_t values_a[BUFFER_SIZE];

    FILE *fp = NULL;

    if (!ps2000_run_block(handle, BUFFER_SIZE, timebase, oversample, &time_indisposed_ms))
    {
        printf("Failed to run block capture.\n");
        return 0;
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
        return 0;
    }

    fp = fopen(filename, "w");
    if (!fp)
    {
        printf("Failed to create %s\n", filename);
        return 0;
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
    return 1;
}

static int run_servo_step(int step_deg)
{
    char command[MAX_PATH_LEN];
    snprintf(command, sizeof(command), "python3 servo_step.py %d", step_deg);

    int status = system(command);
    if (status != 0)
    {
        printf("Warning: servo_step.py returned non-zero status.\n");
        return 0;
    }
    return 1;
}

static int run_bmode(const char *capture_folder)
{
    char command[MAX_PATH_LEN];
    snprintf(command, sizeof(command), "python3 image_constructor.py %s", capture_folder);

    int status = system(command);
    if (status != 0)
    {
        printf("Warning: image_constructor.py returned non-zero status.\n");
        return 0;
    }
    return 1;
}

static void shutdown_scope(int16_t handle)
{
    if (handle > 0)
    {
        ps2000_close_unit(handle);
        printf("Closed PicoScope.\n");
    }
}

int main(void)
{
    int16_t handle = 0;

    int16_t channel = PS2000_CHANNEL_A;
    int16_t enabled = 1;
    int16_t dc = 1;
    int16_t range = PS2000_500MV;

    int16_t oversample = 1;
    int16_t timebase = 1;
    int32_t time_interval = 0;
    int16_t time_units = 0;
    int32_t max_samples = 0;

    int32_t offset_uv = 0;
    uint32_t pk_to_pk_uv = 2000000;
    float frequency = 5000.0f;

    int capture_count = 0;
    char capture_folder[MAX_PATH_LEN];
    char filename[MAX_PATH_LEN];

    if (MAX_ANGLE_DEG % STEP_DEG != 0)
    {
        printf("Error: STEP_DEG (%d) must divide MAX_ANGLE_DEG (%d) exactly.\n",
               STEP_DEG, MAX_ANGLE_DEG);
        return 1;
    }

    capture_count = (MAX_ANGLE_DEG / STEP_DEG) + 1;

    printf("Scan setup:\n");
    printf("  Step size      : %d deg\n", STEP_DEG);
    printf("  Max angle      : %d deg\n", MAX_ANGLE_DEG);
    printf("  Capture count  : %d\n", capture_count);
    printf("  Final behavior : return home after last capture\n\n");

    if (!create_next_capture_folder(capture_folder, sizeof(capture_folder)))
    {
        return 1;
    }

    printf("Created folder: %s\n", capture_folder);

    if (!init_scope(&handle,
                    channel,
                    enabled,
                    dc,
                    range,
                    &timebase,
                    oversample,
                    &time_interval,
                    &time_units,
                    &max_samples))
    {
        return 1;
    }

    if (!setup_signal_generator(handle, offset_uv, pk_to_pk_uv, frequency))
    {
        shutdown_scope(handle);
        return 1;
    }

    printf("Starting scan...\n\n");

    for (int scan_index = 0; scan_index < capture_count; scan_index++)
    {
        int current_angle = scan_index * STEP_DEG;

        snprintf(filename,
                 sizeof(filename),
                 "%s/scan_%03d.csv",
                 capture_folder,
                 scan_index);

        printf("Capture %d / %d at %d deg\n",
               scan_index + 1,
               capture_count,
               current_angle);

        if (!capture_and_save(handle,
                              range,
                              timebase,
                              oversample,
                              time_units,
                              filename))
        {
            printf("Stopping scan because capture failed.\n");
            shutdown_scope(handle);
            return 1;
        }

        if (scan_index < capture_count - 1)
        {
            printf("Moving servo to next angle...\n");
            if (!run_servo_step(STEP_DEG))
            {
                printf("Stopping scan because servo move failed.\n");
                shutdown_scope(handle);
                return 1;
            }

            usleep(300000);
        }

        printf("\n");
    }

    printf("Returning servo to home position...\n");
    if (!run_servo_step(STEP_DEG))
    {
        printf("Warning: final return-home servo move failed.\n");
    }
    else
    {
        usleep(300000);
    }

    printf("Running image reconstruction...\n");
    run_bmode(capture_folder);

    shutdown_scope(handle);
    printf("Scan complete.\n");

    return 0;
}
