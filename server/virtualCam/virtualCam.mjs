import net from 'net';
import sharp from 'sharp';
import WebSocket, { WebSocketServer } from 'ws';

// ESP32-CAM connection details
const espHostName = "pixelsense_esp.local";
const esp32CamPort = 9000;

// Open a WebSocket connection to the ESP32-CAM
const espWsAddress = `ws://${espHostName}:${esp32CamPort}`;
const esp_ws = new WebSocket(espWsAddress);  
esp_ws.on('open', () => {  
    console.log('ESP32 connected via websocket');
    requestCapture("startStream"); // start the stream immediately when the server starts
});

// function to fetch an image from esp32
// capture modes: "captureLow", "captureHigh", "startStream"
function requestCapture(captureMode) {
    if (esp_ws.readyState === WebSocket.OPEN) {
        esp_ws.send(captureMode); 
    }
}

// image handling from esp32
let currentImageBuffer = null; // buffer to store the current image data
esp_ws.on('message', async (data) => {
    currentImageBuffer = data; // store the image data in the buffer
    if(currentImageBuffer){
        await sendImage(currentImageBuffer); // send the current image to the virtual cam immediately after connecting
        currentImageBuffer = null; // clear the buffer after sending
    }
});

// connect with python virtual cam
const VirtualCamPort = 8002;
const VirtualCam = net.createConnection({ port: VirtualCamPort }, () => {
    console.log('Connected to Python Virtual Cam');
});

async function sendImage(imgBuffer) {
    // Read and Resize the image
    const resizedImageBuffer = await sharp(imgBuffer)
        .resize(640, 480)
        .toBuffer();

    // Create the header with the new size
    const header = Buffer.alloc(4);
    header.writeUInt32BE(resizedImageBuffer.length, 0);

    // Send header, then resized image
    VirtualCam.write(header);
    VirtualCam.write(resizedImageBuffer);
    console.log(`Sent resized image: ${resizedImageBuffer.length} bytes`);
}

let dataBuffer = ""; // Accumulator for incoming chunks
// handle data received from python virtual cam
VirtualCam.on('data', async (data) => {
   dataBuffer += data.toString();
    try {
        while (dataBuffer.includes('\n')) {
            // Find the boundary based on the newline character Python now sends
            let boundary = dataBuffer.indexOf('\n'); 
            const completeMsg = dataBuffer.slice(0, boundary); // Get string up to \n
            dataBuffer = dataBuffer.slice(boundary + 1); // Remove processed part

            if (completeMsg.trim() === "") continue;

            const msg = completeMsg.trim();

            if(msg == 'success'){
                if(currentImageBuffer){
                    await sendImage(currentImageBuffer); // send the current image to the virtual cam
                    currentImageBuffer = null; // clear the buffer after sending
                }
            }
        }
    } catch (err) {
        console.error("JSON Parse Error in Node.js:", err);
    }
});