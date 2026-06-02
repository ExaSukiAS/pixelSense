# PixelSense

AI-powered smart eyewear designed to make the lives of visually impaired people interactive and easier. 

> "Listen to the world"

---

## Project Overview
PixelSense is a wearable assistive technology project integrated into eyeglasses, featuring:
* Two cameras for stereo vision
* Laser distance sensors
* Microphones
* Stereo speakers
* Internet-connected MCU
* User-interaction buttons

The project aims to enhance the independence of visually impaired individuals by enabling them to perceive their environment through spatial audio and descriptive instructions.

---

## Features

### 1. Depth Perception
Enables users to navigate their surroundings through real-time auditory environmental mapping. Leveraging dual-lens stereoscopic cameras, the device continuously generates a high-precision absolute depth map, which is translated into a multi-dimensional spatial audio landscape delivered via integrated stereo speakers. The spatialization algorithm encodes the environment using three parameters:
* **X-Axis (Horizontal Localization):** Mapped through interaural level differences (ILD). The system performs a rhythmic "sweep" across the scene, transitioning audio intensity from the left to right channel.
* **Y-Axis (Vertical Elevation):** Represented through a frequency-mapped pentatonic scale consisting of 20 distinct bands. The pitch modulates from a fundamental frequency at the top of the frame to a perfect fifth, reaching a full octave at the bottom.
* **Z-Axis (Proximity & Distance):** Communicated through dynamic volume modulation governed by an inverse-exponential function (distant objects produce a subtle auditory footprint, while immediate obstacles trigger a significantly louder signal).

### 2. Freeform
Enables users to understand their environment through conversational descriptions. The device captures an image, processes user-posed questions (via microphone) about the surroundings, and delivers answers (via inbuilt speakers) using a Large Language Model (LLM).

### 3. Coordination
Provides object location relative to the user's hand in real-time. It utilizes a Vision Transformer (ViT) tracker to provide real-time spatial guidance. By performing a continuous geometric analysis of bounding boxes for both the hand and the designated object (uttered by the user), the system calculates precise directional vectors translated into frequency-coded auditory feedback.

### 4. Text Recognition
Reads text aloud by capturing an image of text (books, signs, handwriting), performing Optical Character Recognition (OCR), and vocalizes the content through the inbuilt speakers.

### 5. Proximity Alert System
Provides high-speed obstacle detection by utilizing two integrated Time-of-Flight (ToF) sensors for real-time obstacle avoidance. Operating with a 50ms latency, it ensures rapid response times for identifying physical barriers (such as walls) using frequency-modulated auditory alerts where the acoustic pitch dynamically shifts in relation to proximity.

---

## Problem Addressing

* **Lack of 3D Spatial Awareness and Safe Navigation:** Visually impaired individuals struggle to perceive room layouts, overhanging objects, or hazard distances. PixelSense addresses this through Depth Perception and its Proximity Alert system (50ms low-latency ToF alerts).
* **Difficulty Grasping and Locating Specific Objects:** Finding items often requires frustrating or dangerous "tactile fumbling." The Coordination feature uses a Vision Transformer (ViT) tracker to guide the user's hand precisely to the target using acoustic vectors.
* **Disconnect from Complex Environmental Context:** Missing out on contextual nuances limits autonomy. The Freeform feature combines camera capture with an LLM to answer open-ended questions about the surroundings.
* **Inaccessibility of Printed Text in the Physical World:** Menus, signs, and books present constant barriers. The Text Recognition module automates reading via high-accuracy OCR and reads it aloud.

---

## Hardware Details

| Component | Purpose |
| --- | --- |
| **2x ESP32 S3 MCU** | Connect to server, Audio processing and streaming, image processing and streaming, reading TOF and touch sensors, and connecting everything together. |
| **2x OV3660 3MP camera** | Capturing images. |
| **2x MSM261D3526H1CPM digital MEMS microphone** | Capturing audio samples and sending to ESP32 via I2S for user interactions. |
| **2x MAX98357A DAC + Amplifier** | Playing audio samples received from ESP32 via I2S. |
| **2x VL53L0X TOF infrared-laser distance sensor** | Low-latency obstacle avoidance. |
| **2x TTP223 touch sensors** | User interactions. |
| **500mAH Battery** | Powering the whole system. |

---

## Server-Side (Back-End) Details

Because the wearable device has limited hardware capabilities, heavy AI tasks are offloaded to an internet-connected, Python-based server that connects to individual ESP32 microcontrollers via **WebSockets**.

### Network Protocols
* **TCP:** Used for establishing a connection through a handshake and sending/receiving small commands and information (e.g., ToF distance readings, feature execution orders).
* **UDP:** Used to stream audio and JPEG images bidirectionally between the server and the ESP32.

### Core Server Executions

#### Speech Recognition
When a feature requiring speech recognition is requested, the ESP32 streams audio samples (8Khz, 16bit quality) to the server via UDP. The server transcribes the audio in real-time using OpenAI's **Tiny Whisper** model.

#### The LLM & Text-to-Speech
Features like Text Recognition and Freeform rely on an LLM for human-like descriptions.
* **Model:** Gemini 3 Flash model is used for superior text recognition and natural text output.
* **Text-to-Speech:** Text from the LLM is transcribed into 12KHz, 16bit audio via **Piper text to speech** and streamed from the server to the ESP32 via UDP to be played through the DAC and Amplifier modules.

#### Coordination Feature Architecture
To bypass the latency of continuous live video tracking with an LLM and the category limitations of generic models (like YOLO), PixelSense uses a hybrid architecture operating in three phases:
1. **Initialization (LLM):** The user names an object, a single camera frame is sent to **Gemini 2.5 Flash** (optimized for spatial awareness), which generates initial bounding box coordinates (x, y, width, height).
2. **Real-Time Tracking (ViT):** The initial bounding box is fed to a high-speed **Vision Transformer (ViT) tracker**, which continuously tracks the object in real-time without heavy computational overhead.
3. **Spatial Guidance:** **MediaPipe** algorithms track the user's hand simultaneously. The system calculates the directional vector between the hand and the tracked object, sending coordinates to the ESP32 to generate dynamic, frequency-coded audio cues.

#### Depth Map Estimation Pipeline
1. **Synchronous Data Streaming:** Dual ESP32 MCUs capture and stream synchronized JPEG image pairs (640x480 resolution) via UDP.
2. **Stereo Rectification:** The server aligns the frames using **OpenCV’s stereo rectification** algorithm, using pre-calculated matrices from chessboard pattern calibration.
3. **Disparity Calculation:** Rectified pairs are processed via a **Stereo Semi-Global Block Matching (SGBM)** algorithm to calculate pixel disparity.
4. **Map Refinement:** The raw disparity map is processed through a **Weighted Least Squares (WLS)** filter to reduce noise and smooth edges.
5. **Final Depth Generation:** The absolute 3D depth map is calculated by combining the refined disparity map with pre-calibrated physical parameters (baseline lens distance and focal lengths).
