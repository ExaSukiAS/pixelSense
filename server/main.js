const { app, BrowserWindow, ipcMain } = require('electron');
const { GoogleGenerativeAI } = require("@google/generative-ai");
const fs = require("fs");
const WebSocket = require('ws');
const net = require('net');
const express = require('express');
const { imageSize } = require('image-size');

// create window
let win;
function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 720,
    title: "NeuronSpark | PixelSense",
    frame: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
  });
  win.loadFile("./UI/render.html");
}
app.whenReady().then(createWindow)

const espIP = '192.168.68.106'; // local IP of esp32

// all websocket and TCP connection ports
const voiceUIport = 9999;
const websocketAudioPort = 8080;
const espPort = 9000;
const CSRTtrackerPort = 8001;

// voice server for handling audio TTS and STT
const voiceServer = express();
voiceServer.use(express.static('voice'));
voiceServer.listen(voiceUIport, () => {
    console.log(`Voice server url: http://127.0.0.1:${voiceUIport}/`);
});
const wsAudio = new WebSocket.Server({ port: websocketAudioPort });

// connect with CSRT tracker
const CSRTtracker = net.createConnection({ port: CSRTtrackerPort }, () => {
  console.log('Connected to Python CSRT tracker');
});

function restartApp() {
  app.relaunch();
  app.quit();
}

wsAudio.on('connection', audio => {  // check if audio feature is turned on
  win.webContents.send("audio", 1); 
  console.log("sound Enabled");

  let currentMode; // current running mode (freeform, image description, text recognition, coordination and object detection)
  let trackedObjName = ""; // currently tracked object name
  let currentImageBase64 = null; // variable to store the current image base64 data

  const espWsAddr = `ws://${espIP}:${espPort}`;
  const esp_ws = new WebSocket(espWsAddr);  // open esp32 websocket
  esp_ws.on('open', () => {   // check if esp32 websocket port is opened
      console.log('ESP32 connected via websocket');
      win.webContents.send("esp_connect", 1);
  });

  // image handling from esp32
  let initTries = 5; // number of initial frames to skip for .coord mode (this is to allow the esp32 cam to stabelize the image stream)
  let APItriggered = false;
  esp_ws.on('message', (data) => {
    if(data.includes("$#TXT#$")){
      data = data.toString().replace("$#TXT#$", "");
      console.log("From ESP32", data);
      if(data == "streamingStopped"){
        // reset variables and UI
        initTries = 5;
        APItriggered = false;
        win.webContents.send("terminate", 1);
      } else if (data == "touch1_single"){
        win.webContents.send("ble_trigger", ".txt_rec");
      } else if (data == "touch2_single"){
        win.webContents.send("ble_trigger", ".freeform");
      } else if (data == "touch1_double"){
        win.webContents.send("ble_trigger", ".coord");
      } else if (data == "touch2_double"){
        win.webContents.send("ble_trigger", ".img_des");
      }
    } else {
      currentImageBase64 = data.toString('base64'); // store the image data as base64
      win.webContents.send("update_img", currentImageBase64); // send the image data to renderer
      if(currentMode == '.coord'){ // start realtime coordination mode
        initTries--;
        if(initTries <= 0){ 
          if(!APItriggered){
            APItriggered = true;
            modeHandler.executeMode(currentMode); // handle the initiation coordination mode(once per stream)
          }
        }
      } else { // handle other modes (non-realtime)
        modeHandler.executeMode(currentMode); // handle the currentMode that user wants (currentMode var is already set by button click event)
      }
    }
  });

  class modeExecuter {
    executeMode(feature){
      currentMode = feature; // set the currentMode to the selected feature
      switch (currentMode) {
        case ".obj_dtc":
            this.object_detection();
            break;
        case ".img_des":
            this.image_description();
            break;
        case ".txt_rec":
            this.text_recognition();
            break;
        case ".freeform":
            this.freeform();
            break;
        case ".coord":
            this.initiateCoordination();
            break;
      }
    }
    // function for text recognition feature
    async text_recognition(){
      currentMode = '.txt_rec';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, currentMode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == "terminate_task"){
          win.webContents.send("terminate", 1);
          audio.removeEventListener('message', terminate_handler);
        }
      };
      audio.addEventListener('message', terminate_handler);
    }

    // function for object detection feature
    async object_detection(){
      currentMode = '.obj_dtc';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, currentMode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          audio.removeEventListener('message', terminate_handler);
        }
      };
      audio.addEventListener('message', terminate_handler);
    }

    // function for image description feature
    async image_description(){
      currentMode = '.img_des';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, currentMode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          audio.removeEventListener('message', terminate_handler);
        }
      };
      audio.addEventListener('message', terminate_handler);
    }

    // function for freeform feature
    async freeform(){
      currentMode = '.freeform';

      win.webContents.send("back_msg", 'Waiting for user input... ...');
      win.webContents.send("level_indicate", 70);
      audio.send('stt'); // get user input as voice 
      const messageHandler = async (websocket_event) => {
        console.log(websocket_event.data);
        win.webContents.send("back_msg", websocket_event.data);
        await run_AI(websocket_event.data, currentMode, true); // run the AI and say teh ouput as voice
        win.webContents.send("level_indicate", 100);
        audio.removeEventListener('message', messageHandler);
      };
      audio.addEventListener('message', messageHandler);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          audio.removeEventListener('message', terminate_handler);
        }
      };
      audio.addEventListener('message', terminate_handler);
    }

    // function for coordination feature
    async initiateCoordination(){
      currentMode = '.coord';

      win.webContents.send("back_msg", 'Waiting for user input... ...');
      win.webContents.send("level_indicate", 70);
      audio.send('stt'); // get user input as voice 
      const messageHandler = async (websocket_event) => {
        win.webContents.send("back_msg", "Getting initial coordinates of hand and " + websocket_event.data + "... ...");
        const initialCoordinate = await run_AI(websocket_event.data, currentMode, false); // get initial coordinates as JSON object from gemini
        if (initialCoordinate) {
          const imageBuffer = Buffer.from(currentImageBase64, 'base64'); // Decode base64 image to buffer
          const { width: imageWidth, height: imageHeight } = imageSize(imageBuffer);// Get image dimensions
          if (!imageWidth || !imageHeight) {return;}

          // Convert normalized box (0–1000 scale) to pixel coordinates
          const x = (initialCoordinate.xmin / 1000) * imageWidth;
          const y = (initialCoordinate.ymin / 1000) * imageHeight;
          const w = ((initialCoordinate.xmax - initialCoordinate.xmin) / 1000) * imageWidth;
          const h = ((initialCoordinate.ymax - initialCoordinate.ymin) / 1000) * imageHeight;
          trackedObjName = websocket_event.data; // set the currently tracked object name

          // Send as pixel ROI [x, y, width, height] to CSRT tracker
          const rio = [x, y, w, h];
          const imgJSON = {"imgBase64": currentImageBase64, "objRIO": rio};
          CSRTtracker.write(JSON.stringify(imgJSON));
        }

        win.webContents.send("level_indicate", 100);
        audio.removeEventListener('message', messageHandler);
      };
      audio.addEventListener('message', messageHandler);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          audio.removeEventListener('message', terminate_handler);
        }
      };
      audio.addEventListener('message', terminate_handler);
    }
  }
  const modeHandler = new modeExecuter(); // create an instance of modeExecuter class

  // handle data received from python CSRT tracker
  CSRTtracker.on('data', async (data) => {
    const msg = JSON.parse(data.toString());
    
    win.webContents.send("drawBoxAndLine", [{x: msg.objRIO[0], y: msg.objRIO[1], width: msg.objRIO[2], height: msg.objRIO[3], label: trackedObjName},{x: msg.handRIO[0], y: msg.handRIO[1], width: msg.handRIO[2], height: msg.handRIO[3], label: 'Hand'}]);

    if(msg.init == true){
      const imgJSON = {"imgBase64": currentImageBase64};
      CSRTtracker.write(JSON.stringify(imgJSON));
      return;
    }
  });

  // function to fetch an image from esp32
  // capture modes: "captureLow", "captureHigh", "startStream"
  function requestCapture(captureMode) {
    if (esp_ws.readyState === WebSocket.OPEN) {
      esp_ws.send(captureMode); 
    }
  }

  const apiJSON = JSON.parse(fs.readFileSync('geminiAPI.json', 'utf8'));
  const apiKey = apiJSON.apiKey;
  const genAI = new GoogleGenerativeAI(apiKey); // create gemini session 
  
  // gemini configuration
  const generationConfig = {maxOutputTokens: 4096, temperature: 0.3, topP: 1, topK: 32};
  const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash" , generationConfig});  // initialize gemini model for normal tasks
  const modelCoord = genAI.getGenerativeModel({ model: "gemini-2.0-flash" , generationConfig});  // initialize gemini model for coordination

  const instructionFilePath = 'instructions.txt'; // instruction text file path
  let instructionTxt = fs.readFileSync(instructionFilePath, 'utf8');    // read the instruction file
  let instructions = [['.obj_dtc', '.img_des', '.txt_rec', '.freeform', '.coord'], [``, ``, ``, ``, ``]]; // 2D array for instruction keys and data

  // fetches data from the instruction text file, formats it and stores in the "instructions" array
  let instructionArray = instructionTxt.split('$$');
  instructionArray.forEach((element, index) => {
      let elementIndex = instructions[0].indexOf(element);
      if(elementIndex > -1){
          instructions[1][elementIndex] = instructionArray[index+1];
      }
  });

  // function to run the AI, display text on UI and output speech
  async function run_AI(prompt, currentMode, voice_on) {
    win.webContents.send("remove_boxes", 1);
    if (prompt == 0){ // handle if no prompt is provided
        if (currentMode == ".obj_dtc"){
            prompt = 'What are the objects in this image?';
        } else if (currentMode == ".img_des"){
            prompt = 'Describe this image.';
        } else if (currentMode == ".txt_rec"){
            prompt = 'What is written here?';
        }
    }

    // select the right instruction for AI
    let instructionKeyIndex = instructions[0].indexOf(currentMode)
    const AI_instruction = instructions[1][instructionKeyIndex];

    // image to send
    const imageParts = [
      {
        inlineData: {
          data: currentImageBase64,
          mimeType: "image/jpeg"
        }
      }
    ];

    const AIquery = [[{text: AI_instruction}, {text: prompt}], ...imageParts];

    if (currentMode == ".coord"){
      const result = await modelCoord.generateContentStream(AIquery); // get the output from gemini
      let text = '';  // stores the full-streamed text
      for await (const chunk of result.stream) {  // process each chunk of data from gemini
        const chunkText = await chunk.text();
        text += chunkText;
      }
      let cleanJsonString = text.replace(/^```json\n/, '').replace(/```$/, '');    //filter the string
      let fullJSON = JSON.parse(cleanJsonString);
      return fullJSON;  // return the full JSON object
    } else {
      const result = await model.generateContentStream(AIquery); // get the output from gemini
      let text = '';  // stores the full-streamed text

      // chunks for text to speech
      let chunk_array = [];
      let chunk_size = 2;
      for await (const chunk of result.stream) {  // process each chunk of data from gemini
        const chunkText = await chunk.text();
        chunk_array.push(chunkText);
        text += chunkText;
        win.webContents.send("back_msg", text);
        if(chunk_array.length >= chunk_size){
          if(voice_on){
            audio.send(chunk_array[0] + chunk_array[1]); // say the chunk as voice
          }
          chunk_array.length = 0;
        }
      }
      if(chunk_array.length > 0){
        if(voice_on){
          audio.send(chunk_array[0]);  // say the last chunk
        }
      }
      chunk_array.length = 0;
      text = '';
    }
  }

  // check for any user event from renderer
  ipcMain.on("msg", (event, arg) => {
    if (arg === '.txt_rec'){
      currentMode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.obj_dtc'){
      currentMode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.img_des'){
      currentMode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.freeform'){
      currentMode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("captureHigh");
    } else if (arg === '.ai_chat'){
      currentMode = arg;
      ai_chat();
    } else if (arg === '.coord'){
      currentMode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("startStream");
    } else if (arg === 'stabelize_on'){
      currentMode = 'stabelize_on';
      requestCapture("startStream");
    } else if (arg === 'stabelize_off'){
      currentMode = 'stabelize_off';
    } else if (arg === 'stop_speech'){
      audio.send('tts_stop');
    } else if (arg == 'restart_app'){
      restartApp();
    }
  });  
});