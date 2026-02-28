import fs from "fs";
import net from 'net';
import { imageSize } from 'image-size';

const VitTrackerPort = 8001;

// connect with CSRT tracker
const VitTracker = net.createConnection({ port: VitTrackerPort }, () => {
  console.log('Connected to Python CSRT tracker');
});

const frameFolder = 'tracker/sampleData/bottle2/';
  const initialCoordinate = {
      "xmin": 419,
      "xmax": 502,
      "ymin": 304,
      "ymax": 826,
      "label": "object"
  };

const initFramePath = `${frameFolder}frame_00000.jpg`;
if (initialCoordinate) {
    const imageBuffer = fs.readFileSync(initFramePath); // Read image as buffer
    const { width: imageWidth, height: imageHeight } = imageSize(imageBuffer);// Get image dimensions

    // Convert normalized box (0–1000 scale) to pixel coordinates
    const x = (initialCoordinate.xmin / 1000) * imageWidth;
    const y = (initialCoordinate.ymin / 1000) * imageHeight;
    const w = ((initialCoordinate.xmax - initialCoordinate.xmin) / 1000) * imageWidth;
    const h = ((initialCoordinate.ymax - initialCoordinate.ymin) / 1000) * imageHeight;

    // Send as pixel ROI [x, y, width, height] to CSRT tracker
    const rio = [x, y, w, h];
    const imgJSON = {"imgBase64": imageBuffer.toString('base64'), "objRIO": rio};
    VitTracker.write(JSON.stringify(imgJSON)+"\n");
}

let dataBuffer = ""; // Accumulator for incoming chunks
// handle data received from python VitTracker
VitTracker.on('data', async (data) => {
    dataBuffer += data.toString();
    // Due to the nature of TCP, we might receive partial JSON objects, so we need to handle that
    try {
        while (dataBuffer.length > 0) {
            // Find the end of the first JSON object in the buffer
            let boundary = dataBuffer.indexOf('}'); 
            if (boundary === -1) break; // Incomplete JSON, wait for more data

            const completeMsg = dataBuffer.slice(0, boundary + 1);
            dataBuffer = dataBuffer.slice(boundary + 1); // Remove processed part

            const msg = JSON.parse(completeMsg);
            console.log("Received from VitTracker:", msg);

            handleVitTrackerMessage(msg); 
        }
    } catch (err) {}
});

let imageNumber = 0;
function handleVitTrackerMessage(msg) {
    if (msg.init === true || msg.success === true) {
        imageNumber++;

        const framePath = `${frameFolder}frame_${String(imageNumber).padStart(5, '0')}.jpg`;

        if (!fs.existsSync(framePath)) {
          console.log("No more frames.");
          return;
        }

        const imageBuffer = fs.readFileSync(framePath);
        const currentImageBase64 = imageBuffer.toString('base64');
        const imgJSON = { imgBase64: currentImageBase64 };
        VitTracker.write(JSON.stringify(imgJSON)+"\n");
        console.log("Sent next frame to VitTracker:", framePath);
    }
}