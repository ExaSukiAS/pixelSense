# PixelSense by NeuronSpark

**PixelSense** is an innovative wearable assistive technology project developed by **NeuronSpark**. Designed to significantly improve the daily lives of individuals with visual impairments, PixelSense is seamlessly integrated into a pair of eyeglasses.

This cutting-edge device is packed with features, including:

* **Camera:**  Captures the wearer's surroundings, providing visual input for analysis.
* **Infrared Distance Sensor:**  Detects obstacles and measures distances, enhancing spatial awareness.
* **Microphone:**  Records audio, enabling voice commands and environmental sound analysis.
* **Speaker:**  Provides audio feedback, delivering information and guidance to the user.
* **Internet-Connected MCU (Microcontroller Unit):**  Processes data, connects to online services, and enables advanced features.
* **User Interaction Buttons:**  Allows for intuitive control and interaction with the device's functionalities.

## Getting Started with PixelSense

To run PixelSense, please follow these steps:

1. **Install Node.js:** Ensure that Node.js is installed on your system. You can download it from the official [Node.js website](https://nodejs.org/).

2. **Install Dependencies:** Navigate to the PixelSense project directory in your terminal and run the following command to download all necessary packages:

   ```bash
   npm install
   ```

3. **Create Configuration Files:** You need to create two files in the project directory:

   * **`user.jpg`:** This file will be used by the server to store images

   * **`geminiAPI.json`:**  This file will store your Gemini API key.

4. **Configure Gemini API Key:** Open the `geminiAPI.json` file and paste your API key in the following JSON format:

   ```json
   {
       "apiKey": "your-api-key"
   }
   ```

   **Important:** Replace `"your-api-key"` with your actual Gemini API key. Ensure the API key is correctly placed within the JSON structure.

---

**PixelSense** aims to empower visually impaired individuals by providing them with enhanced environmental awareness and assistance through advanced technology integrated into a comfortable and familiar wearable form factor.

```
