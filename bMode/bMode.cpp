/**
 * B-mode Ultrasound Reconstruction
 * Converted from MATLAB script.
 *
 * Dependencies:
 *   - libmatio  (reading .mat files):  sudo apt install libmatio-dev
 *   - FFTW3     (Hilbert transform):   sudo apt install libfftw3-dev
 *   - matplotlib-cpp or gnuplot (optional, for plotting)
 *
 * Compile:
 *   g++ -O2 -std=c++17 bmode_scan.cpp -o bmode_scan -lmatio -lfftw3
 *
 * Usage:
 *   ./bmode_scan
 *   (edit the Settings section below as needed)
 */

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <glob.h>       // POSIX glob for file pattern matching
#include <matio.h>      // libmatio for .mat file reading
#include <fftw3.h>      // FFTW for FFT-based Hilbert transform

// ============================================================
// Settings (edit if needed)
// ============================================================
static const char*  FILE_PATTERN  = "20260225_*.mat";
static const double C             = 1480.0;   // speed of sound in water (m/s)
static const double DYN_RANGE_DB  = 50.0;     // display dynamic range (dB)
static const bool   USE_TGC       = true;     // time gain compensation on/off
static const double TGC_ALPHA     = 1.5;      // TGC strength (0.5 – 3)

// ============================================================
// Helper: glob file list
// ============================================================
std::vector<std::string> globFiles(const std::string& pattern)
{
    glob_t result{};
    std::vector<std::string> files;
    if (glob(pattern.c_str(), GLOB_TILDE, nullptr, &result) == 0) {
        for (size_t i = 0; i < result.gl_pathc; ++i)
            files.emplace_back(result.gl_pathv[i]);
    }
    globfree(&result);
    std::sort(files.begin(), files.end());
    return files;
}

// ============================================================
// Helper: load a scalar double field from a mat_t
// ============================================================
double loadScalar(mat_t* mat, const char* name, const std::string& fname)
{
    matvar_t* v = Mat_VarRead(mat, name);
    if (!v) throw std::runtime_error("Missing field '" + std::string(name) + "' in " + fname);
    double val = *static_cast<double*>(v->data);
    Mat_VarFree(v);
    return val;
}

// ============================================================
// Helper: load a 1-D double array field from a mat_t
// ============================================================
std::vector<double> loadArray(mat_t* mat, const char* name, const std::string& fname)
{
    matvar_t* v = Mat_VarRead(mat, name);
    if (!v) throw std::runtime_error("Missing field '" + std::string(name) + "' in " + fname);
    size_t n = v->dims[0] * v->dims[1];
    std::vector<double> out(n);
    double* ptr = static_cast<double*>(v->data);
    std::copy(ptr, ptr + n, out.begin());
    Mat_VarFree(v);
    return out;
}

// ============================================================
// Hilbert envelope via FFTW  (in-place, column by column)
// Returns |analytic signal| for each column of B (N x K)
// ============================================================
std::vector<double> hilbertEnvelope(const std::vector<double>& B, size_t N, size_t K)
{
    std::vector<double> env(N * K);

    // Allocate FFTW buffers once
    fftw_complex* freq = fftw_alloc_complex(N);
    double*       buf  = fftw_alloc_real(N);

    fftw_plan planFwd = fftw_plan_dft_r2c_1d((int)N, buf, freq, FFTW_ESTIMATE);
    fftw_plan planInv = fftw_plan_dft_c2r_1d((int)N, freq, buf, FFTW_ESTIMATE);

    for (size_t k = 0; k < K; ++k) {
        // Copy column into buf
        for (size_t n = 0; n < N; ++n) buf[n] = B[n * K + k];

        // Forward FFT
        fftw_execute(planFwd);

        // Apply Hilbert weighting in frequency domain
        //   DC (0) and Nyquist stay unchanged
        //   Positive freqs [1 .. N/2-1] multiplied by 2
        //   Negative freqs [N/2+1 .. N-1] set to 0
        size_t Nhalf = N / 2;
        for (size_t i = 1; i < Nhalf; ++i) {
            freq[i][0] *= 2.0;
            freq[i][1] *= 2.0;
        }
        for (size_t i = Nhalf + 1; i < N; ++i) {
            freq[i][0] = 0.0;
            freq[i][1] = 0.0;
        }

        // Inverse FFT
        fftw_execute(planInv);

        // Compute envelope magnitude, normalise by N (FFTW convention)
        // The imaginary part of the analytic signal is in buf (real part of IFFT output)
        // We need both real and imaginary; reconstruct:
        //   real(analytic) = original signal
        //   imag(analytic) = IFFT result / N  (from the doubled positive freqs trick)
        for (size_t n = 0; n < N; ++n) {
            double re = B[n * K + k];
            double im = buf[n] / (double)N;
            env[n * K + k] = std::sqrt(re * re + im * im);
        }
    }

    fftw_destroy_plan(planFwd);
    fftw_destroy_plan(planInv);
    fftw_free(freq);
    fftw_free(buf);

    return env;
}

// ============================================================
// Save result as a simple CSV for external plotting
// ============================================================
void saveCSV(const std::string& path,
             const std::vector<double>& env_db,
             const std::vector<double>& depth_mm,
             size_t N, size_t K)
{
    std::ofstream f(path);
    if (!f) throw std::runtime_error("Cannot open " + path + " for writing");

    // Header: depth_mm, col1, col2, ...
    f << "depth_mm";
    for (size_t k = 0; k < K; ++k) f << ",col" << (k + 1);
    f << "\n";

    for (size_t n = 0; n < N; ++n) {
        f << depth_mm[n];
        for (size_t k = 0; k < K; ++k)
            f << "," << env_db[n * K + k];
        f << "\n";
    }
}

// ============================================================
// Main
// ============================================================
int main()
{
    // --- Load file list ---
    std::vector<std::string> files = globFiles(FILE_PATTERN);
    if (files.empty()) {
        std::cerr << "No files found matching: " << FILE_PATTERN << "\n";
        return 1;
    }
    size_t K = files.size();
    std::cout << "Found " << K << " file(s).\n";

    // --- Load first file for timing ---
    mat_t* mat0 = Mat_Open(files[0].c_str(), MAT_ACC_RDONLY);
    if (!mat0) throw std::runtime_error("Cannot open " + files[0]);

    std::vector<double> A0 = loadArray(mat0, "A", files[0]);
    double Tstart    = loadScalar(mat0, "Tstart",    files[0]);
    double Tinterval = loadScalar(mat0, "Tinterval", files[0]);
    Mat_Close(mat0);

    size_t N = A0.size();

    // Build time vector
    std::vector<double> t(N);
    for (size_t i = 0; i < N; ++i)
        t[i] = Tstart + (double)i * Tinterval;

    // --- Load all A-scans into B (row-major: B[n*K + k]) ---
    std::vector<double> B(N * K, 0.0);

    for (size_t k = 0; k < K; ++k) {
        mat_t* mat = Mat_Open(files[k].c_str(), MAT_ACC_RDONLY);
        if (!mat) { std::cerr << "Cannot open " << files[k] << ", skipping.\n"; continue; }

        std::vector<double> a = loadArray(mat, "A", files[k]);
        Mat_Close(mat);

        if (a.size() != N) {
            std::cerr << "Warning: length mismatch in " << files[k]
                      << " (got " << a.size() << ", expected " << N << "). Trunc/pad applied.\n";
            a.resize(N, 0.0);
        }
        for (size_t n = 0; n < N; ++n)
            B[n * K + k] = a[n];
    }

    // --- Crop pre-trigger (t < 0) ---
    size_t startIdx = 0;
    while (startIdx < N && t[startIdx] < 0.0) ++startIdx;

    N -= startIdx;
    t.erase(t.begin(), t.begin() + (long)startIdx);
    std::vector<double> Bcrop(N * K);
    for (size_t n = 0; n < N; ++n)
        for (size_t k = 0; k < K; ++k)
            Bcrop[n * K + k] = B[(n + startIdx) * K + k];
    B = std::move(Bcrop);

    // --- Envelope detection (Hilbert) ---
    std::vector<double> env = hilbertEnvelope(B, N, K);

    // Normalize
    double maxEnv = *std::max_element(env.begin(), env.end());
    for (auto& v : env) v /= (maxEnv + 1e-300);

    // --- Optional TGC ---
    if (USE_TGC) {
        double tMax = t.back();
        for (size_t n = 0; n < N; ++n) {
            double g = std::exp(TGC_ALPHA * (t[n] / tMax));
            for (size_t k = 0; k < K; ++k)
                env[n * K + k] *= g;
        }
        maxEnv = *std::max_element(env.begin(), env.end());
        for (auto& v : env) v /= (maxEnv + 1e-300);
    }

    // --- Log compression (dB) ---
    std::vector<double> env_db(N * K);
    for (size_t i = 0; i < N * K; ++i)
        env_db[i] = 20.0 * std::log10(env[i] + 1e-12);

    // --- Convert time -> depth (mm) ---
    std::vector<double> depth_mm(N);
    for (size_t n = 0; n < N; ++n)
        depth_mm[n] = (C * t[n] / 2.0) * 1000.0;

    // --- Save to CSV (plot with Python/MATLAB/gnuplot) ---
    const std::string outCSV = "bmode_output.csv";
    saveCSV(outCSV, env_db, depth_mm, N, K);
    std::cout << "Saved B-mode data to " << outCSV << "\n";
    std::cout << "Depth range: " << depth_mm.front() << " – " << depth_mm.back() << " mm\n";
    std::cout << "Dynamic range: " << DYN_RANGE_DB << " dB\n";

    // --- Optional: quick plot with gnuplot (if available) ---
    // Uncomment the lines below if gnuplot is installed:
    // std::string cmd = "gnuplot -e \""
    //     "set terminal png size 1200,600; set output 'bmode.png';"
    //     "set yrange [" + std::to_string(depth_mm.back()) + ":" + std::to_string(depth_mm.front()) + "];"
    //     "set cbrange [" + std::to_string(-DYN_RANGE_DB) + ":0];"
    //     "set palette gray; plot 'bmode_output.csv' matrix with image\"";
    // system(cmd.c_str());

    return 0;
}