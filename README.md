# Sonolite
A small, open-source ultrasound device built to send sound pulses, receive echoes, and turn them into basic imaging data.

Working in collaboration with:

McMaster Health Sciences; Dr. Troy Farncombe

University of Toronto Medical Sciences; Dr. F. Stuart Foster

Update:

# Ultrasound Update: Implementation of Picoscope/Pulser/Fabricated Transducer 
This document outlines the basic hardware setup and software processing pipeline used to generate a single-element ultrasound B-scan image using a custom pulser board, a PicoScope 2204A, and MATLAB. 

## 1. Hardware Setup
The system operates similarly to the previous step, but with the addition of the pulser. The DC power supply feeds the pulser, and pulser is connected to the transducer, and also has Rx/Tx with the picoscope. The picoscope is then connected to the MacBook/laptop, which runs Matlab and picoscope scope, and the image is generated in Matlab. The system operates in a pulse-echo configuration where the PicoScope acts as the master clock, triggering a custom high-voltage pulser board to fire the transducer.

**Connections:**
* **PicoScope AWG (Gen) $\rightarrow$ Pulser Board (Trigger In / X1):** Sends a low-voltage square wave to wake up the board and command it to fire.
* **Pulser Board (RF Out / X4) $\rightarrow$ PicoScope Channel A:** Sends the amplified acoustic echo back to the oscilloscope.
* **Pulser Board (X2) $\rightarrow$ Transducer:** The physical connection to the piezoelectric crystal.
* **DC Power Supply $\rightarrow$ Pulser Board:** Provides the necessary high voltage for the board to generate the transmission pulse (the "Main Bang").

## 2. PicoScope 7 Configuration & Data Capture
To view and capture the raw RF (Radio Frequency) acoustic waves, the PicoScope 7 software is configured as follows:

* **Generator (AWG):** * Type: Square Wave
  * Frequency: 1 kHz (fires the transducer 1,000 times per second)
  * Amplitude: 1 V
  * Offset: 1 V (Creates a clean 0V to +2V logic pulse)
* **Timebase (X-Axis):** Set to `5 µs/div` to zoom in on the fast-moving acoustic echoes.
* **Channel A (Y-Axis):** Set to `±1 V` or `±2 V` depending on the echo strength.
* **Trigger:** Set to `Auto` or `Repeat`, Source `Channel A`, with a rising edge threshold of `~400 mV` to freeze the waveform on the screen.

**Exporting Data:**
Once an echo is acquired (e.g., bouncing off the bottom of a water cup), the waveform is paused and saved as a standard `.txt` file. This exports the raw `Time` and `Channel A Voltage` arrays.

## 3. MATLAB Image Generation
An ultrasound image (B-scan) is created by stacking multiple 1D acoustic recordings (A-scans) side-by-side. The raw RF voltage data is converted into grayscale pixel intensity using envelope detection.

### The Processing Script
The following MATLAB code reads the exported `.txt` files, extracts the voltage data, calculates the signal envelope, and displays the final 2D image.

# Main Experimentation
<img width="604" height="734" alt="image" src="https://github.com/user-attachments/assets/953ec253-adfc-4391-a4cc-b5aea1620888" />

Figure 1: System Breakdown

<img width="367" height="649" alt="image" src="https://github.com/user-attachments/assets/9fbff16f-edfa-4b09-b6ab-52af1208e7b4" />

Figure 2: Labelled Current Setup

<img width="340" height="674" alt="image" src="https://github.com/user-attachments/assets/5607c612-68da-4bdf-b980-3cae8b70404b" />

Figure 3: Setup Unlabeled

<img width="633" height="471" alt="image" src="https://github.com/user-attachments/assets/1dd5362d-21bc-47a2-822a-4795c37ed19d" />

Figure 4: Input Pulse Parameters

<img width="474" height="391" alt="image" src="https://github.com/user-attachments/assets/57db59be-475e-4120-a52f-e0932235c398" />

Figure 5: Raw Reading of Transducer using NI Instrument Studio:

<img width="617" height="430" alt="image" src="https://github.com/user-attachments/assets/f25c8b86-7d62-48cf-9efe-808444948f4e" />

Figure 6: Movement of the Transducer:

<img width="827" height="503" alt="image" src="https://github.com/user-attachments/assets/9ae4322b-feab-4ce8-8124-17f29f430d83" />

Figure 7: Single Reading of the Transducer of the Container in MATLAB

<img width="795" height="520" alt="image" src="https://github.com/user-attachments/assets/1d9cc5fc-9381-4a80-853a-a2a7e3eafeb3" />

Figure 8: Conversion of the Number of Samples to the two-way distance of the transducer

<img width="823" height="522" alt="image" src="https://github.com/user-attachments/assets/1911d6d8-fd2b-4ed8-9129-53d417c7c43e" />

Figure 9: Conversion of two-way distance to one-way distance

<img width="837" height="510" alt="image" src="https://github.com/user-attachments/assets/dc0453b0-b229-4b3b-99b5-99473fd373de" />

Figure 10: Compilation of Individual Transducer Readings to an Image










