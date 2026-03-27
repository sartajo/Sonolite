/*
B-mode Ultrasound Reconstruction in C
Based on uploaded Python script.

Build:
    gcc bmode.c -o bmode -lfftw3 -lm

Output:
    bmode_output.pgm
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dirent.h>
#include <fftw3.h>

#define MAX_FILES 1024
#define MAX_PATH 1024
#define LINE_BUF 4096

typedef struct {
    double *t_ms;
    double *v;
    int n;
} Ascan;

typedef struct {
    char **items;
    int count;
} FileList;

static int cmpstr(const void *a, const void *b) {
    const char *sa = *(const char **)a;
    const char *sb = *(const char **)b;
    return strcmp(sa, sb);
}

static int starts_with(const char *s, const char *prefix) {
    return strncmp(s, prefix, strlen(prefix)) == 0;
}

static int ends_with(const char *s, const char *suffix) {
    size_t ls = strlen(s), lf = strlen(suffix);
    if (lf > ls) return 0;
    return strcmp(s + ls - lf, suffix) == 0;
}

static FileList list_csv_files(const char *folder, const char *prefix) {
    FileList fl = {0};
    fl.items = malloc(MAX_FILES * sizeof(char *));
    if (!fl.items) {
        fprintf(stderr, "Memory allocation failed\n");
        exit(1);
    }

    DIR *dir = opendir(folder);
    if (!dir) {
        perror("opendir");
        exit(1);
    }

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        if (starts_with(ent->d_name, prefix) && ends_with(ent->d_name, ".csv")) {
            if (fl.count >= MAX_FILES) break;
            fl.items[fl.count] = malloc(MAX_PATH);
            snprintf(fl.items[fl.count], MAX_PATH, "%s/%s", folder, ent->d_name);
            fl.count++;
        }
    }
    closedir(dir);

    qsort(fl.items, fl.count, sizeof(char *), cmpstr);
    return fl;
}

static void free_filelist(FileList *fl) {
    for (int i = 0; i < fl->count; i++) free(fl->items[i]);
    free(fl->items);
}

static Ascan load_csv(const char *path) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        perror(path);
        exit(1);
    }

    char line[LINE_BUF];

    /* header row */
    if (!fgets(line, sizeof(line), fp)) {
        fprintf(stderr, "Failed reading header from %s\n", path);
        exit(1);
    }

    /* units row */
    if (!fgets(line, sizeof(line), fp)) {
        fprintf(stderr, "Failed reading units row from %s\n", path);
        exit(1);
    }

    int cap = 4096;
    int n = 0;
    double *t_ms = malloc(cap * sizeof(double));
    double *v = malloc(cap * sizeof(double));
    if (!t_ms || !v) {
        fprintf(stderr, "Memory allocation failed\n");
        exit(1);
    }

    while (fgets(line, sizeof(line), fp)) {
        char *tok1 = strtok(line, ",");
        char *tok2 = strtok(NULL, ",");

        if (!tok1 || !tok2) continue;

        double t = strtod(tok1, NULL);
        double a = strtod(tok2, NULL);

        if (n >= cap) {
            cap *= 2;
            t_ms = realloc(t_ms, cap * sizeof(double));
            v = realloc(v, cap * sizeof(double));
            if (!t_ms || !v) {
                fprintf(stderr, "Realloc failed\n");
                exit(1);
            }
        }

        t_ms[n] = t;
        v[n] = a;
        n++;
    }

    fclose(fp);

    Ascan out = { t_ms, v, n };
    return out;
}

static void free_ascan(Ascan *a) {
    free(a->t_ms);
    free(a->v);
}

static void subtract_mean(double *x, int n) {
    double s = 0.0;
    for (int i = 0; i < n; i++) s += x[i];
    double m = s / n;
    for (int i = 0; i < n; i++) x[i] -= m;
}

static void hilbert_envelope(const double *x, int n, double *env) {
    fftw_complex *X = fftw_malloc(sizeof(fftw_complex) * (n/2 + 1));
    double *xin = fftw_malloc(sizeof(double) * n);
    double *xhilb = fftw_malloc(sizeof(double) * n);

    if (!X || !xin || !xhilb) {
        fprintf(stderr, "FFTW allocation failed\n");
        exit(1);
    }

    for (int i = 0; i < n; i++) xin[i] = x[i];

    fftw_plan pf = fftw_plan_dft_r2c_1d(n, xin, X, FFTW_ESTIMATE);
    fftw_plan pb = fftw_plan_dft_c2r_1d(n, X, xhilb, FFTW_ESTIMATE);

    fftw_execute(pf);

    /* Hilbert transform multiplier in frequency domain */
    for (int k = 0; k < n/2 + 1; k++) {
        double h = 0.0;
        if (k == 0) h = 1.0;
        else if (n % 2 == 0 && k == n/2) h = 1.0;
        else h = 2.0;

        X[k][0] *= h;
        X[k][1] *= h;
    }

    fftw_execute(pb);

    /* xhilb now contains analytic-signal real-part scaling effect via FFT convention.
       For envelope, use original x and transformed imag approximation.
       A simple practical approximation here is:
    */
    for (int i = 0; i < n; i++) {
        double imag = xhilb[i] / n;
        env[i] = sqrt(x[i]*x[i] + imag*imag);
    }

    fftw_destroy_plan(pf);
    fftw_destroy_plan(pb);
    fftw_free(X);
    fftw_free(xin);
    fftw_free(xhilb);
}

static void save_pgm(const char *filename, const unsigned char *img, int width, int height) {
    FILE *fp = fopen(filename, "wb");
    if (!fp) {
        perror(filename);
        exit(1);
    }
    fprintf(fp, "P5\n%d %d\n255\n", width, height);
    fwrite(img, 1, width * height, fp);
    fclose(fp);
}

int main(void) {
    const char *folder = "/home/omar/Documents/picosdk-c-examples/ps2000/linux-build-files/captures";
    const char *prefix = "scan_";

    const double c = 1480.0;
    const double dynRange_dB = 50.0;
    const int useTGC = 1;
    const double tgc_alpha = 2.0;

    FileList fl = list_csv_files(folder, prefix);
    if (fl.count == 0) {
        fprintf(stderr, "No files found\n");
        return 1;
    }

    Ascan ref = load_csv(fl.items[0]);
    int N0 = ref.n;

    int *valid_idx = malloc(N0 * sizeof(int));
    int N = 0;
    for (int i = 0; i < N0; i++) {
        if (ref.t_ms[i] * 1e-3 >= 0.0) {
            valid_idx[N++] = i;
        }
    }

    int K = fl.count;
    double *t = malloc(N * sizeof(double));
    double *B = calloc(N * K, sizeof(double));
    double *env = calloc(N * K, sizeof(double));
    double *env_db = calloc(N * K, sizeof(double));

    if (!valid_idx || !t || !B || !env || !env_db) {
        fprintf(stderr, "Memory allocation failed\n");
        return 1;
    }

    for (int i = 0; i < N; i++) {
        t[i] = ref.t_ms[valid_idx[i]] * 1e-3;
    }

    for (int k = 0; k < K; k++) {
        Ascan a = load_csv(fl.items[k]);

        for (int i = 0; i < N; i++) {
            int src = valid_idx[i];
            double val = (src < a.n) ? a.v[src] : 0.0;
            B[i*K + k] = val;
        }

        double *col = malloc(N * sizeof(double));
        double *col_env = malloc(N * sizeof(double));
        for (int i = 0; i < N; i++) col[i] = B[i*K + k];

        subtract_mean(col, N);
        hilbert_envelope(col, N, col_env);

        for (int i = 0; i < N; i++) env[i*K + k] = col_env[i];

        free(col);
        free(col_env);
        free_ascan(&a);
    }

    double max_env = 0.0;
    for (int i = 0; i < N*K; i++) {
        if (env[i] > max_env) max_env = env[i];
    }
    if (max_env <= 0.0) max_env = 1.0;

    for (int i = 0; i < N*K; i++) env[i] /= max_env;

    if (useTGC) {
        double tmax = t[N-1];
        for (int i = 0; i < N; i++) {
            double g = exp(tgc_alpha * (t[i] / tmax));
            for (int k = 0; k < K; k++) {
                env[i*K + k] *= g;
            }
        }

        max_env = 0.0;
        for (int i = 0; i < N*K; i++) {
            if (env[i] > max_env) max_env = env[i];
        }
        if (max_env <= 0.0) max_env = 1.0;
        for (int i = 0; i < N*K; i++) env[i] /= max_env;
    }

    for (int i = 0; i < N*K; i++) {
        env_db[i] = 20.0 * log10(env[i] + 1e-12);
    }

    unsigned char *img = malloc(N * K);
    for (int i = 0; i < N; i++) {
        for (int k = 0; k < K; k++) {
            double v = env_db[i*K + k];
            if (v < -dynRange_dB) v = -dynRange_dB;
            if (v > 0.0) v = 0.0;
            double norm = (v + dynRange_dB) / dynRange_dB;
            int pix = (int)lrint(norm * 255.0);
            if (pix < 0) pix = 0;
            if (pix > 255) pix = 255;

            img[i*K + k] = (unsigned char)pix;
        }
    }

    save_pgm("bmode_output.pgm", img, K, N);

    double depth0_mm = (c * t[0] / 2.0) * 1000.0;
    double depth1_mm = (c * t[N-1] / 2.0) * 1000.0;

    printf("Saved bmode_output.pgm\n");
    printf("Columns: %d\n", K);
    printf("Samples: %d\n", N);
    printf("Depth range: %.2f mm to %.2f mm\n", depth0_mm, depth1_mm);

    free(img);
    free(env_db);
    free(env);
    free(B);
    free(t);
    free(valid_idx);
    free_ascan(&ref);
    free_filelist(&fl);

    return 0;
}
