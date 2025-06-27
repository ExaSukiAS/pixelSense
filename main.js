const { app, BrowserWindow, ipcMain, Menu, globalShortcut } = require('electron');
const { GoogleGenerativeAI } = require("@google/generative-ai");
const fs = require("fs");
const WebSocket = require('ws');
const path = require('path');
const sharp = require('sharp');
const express = require('express');

// create window
let win;
function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 720,
    title: "NeuronSpark | GLASS",
    frame: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
  });
  win.loadFile("./UI/render.html");
}
app.whenReady().then(createWindow)

const voiceServer = express();
const voicePort = 9999; 
voiceServer.use(express.static('voice'));
voiceServer.listen(voicePort, () => {
    console.log(`Voice server url: http://127.0.0.1:${voicePort}/`);
});

const wsAudio = new WebSocket.Server({ port: 8080 });

function restartApp() {
  app.relaunch();
  app.quit();
}

wsAudio.on('connection', ws => {  // check if audio feature is turned on
  let espWsAddr = 'ws://192.168.68.105:9000';
  win.webContents.send("audio", 1); 
  console.log("sound Enabled");

  let mode;
  let esp_ws = new WebSocket(espWsAddr);  // open websocket
  let currentImageBase64 = null; // variable to store the current image base64 data

  esp_ws.on('open', () => {   // check if esp32 websocket port is opened
      console.log('ESP32 connected via websocket');
      win.webContents.send("esp_connect", 1);
  });

  class modeExecuter {
    executeMode(feature){
      mode = feature; // set the mode to the selected feature
      console.log(mode);
      switch (mode) {
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
            this.coordination();
            break;
      }
    }
    // function for text recognition feature
    async text_recognition(){
      mode = '.txt_rec';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, mode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == "terminate_task"){
          win.webContents.send("terminate", 1);
          ws.removeEventListener('message', terminate_handler);
        }
      };
      ws.addEventListener('message', terminate_handler);
    }

    // function for object detection feature
    async object_detection(){
      mode = '.obj_dtc';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, mode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          ws.removeEventListener('message', terminate_handler);
        }
      };
      ws.addEventListener('message', terminate_handler);
    }

    // function for image description feature
    async image_description(){
      mode = '.img_des';

      win.webContents.send("back_msg", 'Waiting for AI to respond... ...');
      win.webContents.send("level_indicate", 60);

      await run_AI(0, mode, true);
      win.webContents.send("level_indicate", 100);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          ws.removeEventListener('message', terminate_handler);
        }
      };
      ws.addEventListener('message', terminate_handler);
    }

    // function for freeform feature
    async freeform(){
      mode = '.freeform';

      win.webContents.send("back_msg", 'Waiting for user input... ...');
      win.webContents.send("level_indicate", 70);
      ws.send('stt'); // get user input as voice 
      const messageHandler = async (websocket_event) => {
        console.log(websocket_event.data);
        win.webContents.send("back_msg", websocket_event.data);
        await run_AI(websocket_event.data, mode, true); // run the AI and say teh ouput as voice
        win.webContents.send("level_indicate", 100);
        ws.removeEventListener('message', messageHandler);
      };
      ws.addEventListener('message', messageHandler);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          ws.removeEventListener('message', terminate_handler);
        }
      };
      ws.addEventListener('message', terminate_handler);
    }

    // function for coordination feature
    async coordination(){
      mode = '.coord';

      win.webContents.send("back_msg", 'Waiting for user input... ...');
      win.webContents.send("level_indicate", 70);
      ws.send('stt'); // get user input as voice 
      const messageHandler = async (websocket_event) => {
        console.log(websocket_event.data);
        win.webContents.send("back_msg", "Getting coordinates of hand and " + websocket_event.data + "... ...");
        await run_AI(websocket_event.data, mode, false); // run the AI 
        win.webContents.send("level_indicate", 100);
        ws.removeEventListener('message', messageHandler);
      };
      ws.addEventListener('message', messageHandler);

      const terminate_handler = async (websocket_event) => {
        if(websocket_event.data == 'terminate_task'){
          win.webContents.send("terminate", 1);
          ws.removeEventListener('message', terminate_handler);
        }
      };
      ws.addEventListener('message', terminate_handler);
    }
  }

  const modeHandler = new modeExecuter(); // create an instance of modeExecuter class

  // image handling from esp32
  esp_ws.on('message', (data) => {
    if(typeof data === 'string' && data.includes("$#TXT#$")){
      data = data.replace("$#TXT#$", "");
      if(data == "streamingStarted"){
        if(mode !== "stabelize_on"){
          modeHandler.executeMode(mode); // run the mode that user wants
        }
      } else if(data == "streamingStopped"){
        win.webContents.send("terminate", 1);
      }
    } else {
      currentImageBase64 = data.toString('base64'); // store the image data as base64
      modeHandler.executeMode(mode); // handle the mode that user wants (mode var is already set by button click event)
      win.webContents.send("update_img", currentImageBase64); // send the image data to renderer
    }
  });


  // function to fetch an image from esp32
  function requestCapture(captureMode) {
    if (esp_ws.readyState === WebSocket.OPEN) {
      esp_ws.send(captureMode); 
    }
  }

  const apiJSON = JSON.parse(fs.readFileSync('geminiAPI.json', 'utf8'));  // read api key from json file
  const apiKey = apiJSON.apiKey;
  const genAI = new GoogleGenerativeAI(apiKey); // create gemini session 
  
  // gemini configuration
  const generationConfig = {
    maxOutputTokens: 4096,
    temperature: 0.3,
    topP: 1,
    topK: 32,
  };
  const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" , generationConfig});  // initialize gemini for normal tasks
  const modelCoord = genAI.getGenerativeModel({ model: "gemini-1.5-flash" , generationConfig});  // initialize gemini for coordination

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
  async function run_AI(prompt, mode, voice_on) {
    win.webContents.send("remove_boxes", 1);
    var AI_instruction;
    if (prompt == 0){ // handle if to prompt is provided
        if (mode == ".obj_dtc"){
            prompt = 'What are the objects in this image?';
        } else if (mode == ".img_des"){
            prompt = 'Describe this image.';
        } else if (mode == ".txt_rec"){
            prompt = 'What is written here?';
        }
    }

    // select the right instruction for AI
    let instructionKeyIndex = instructions[0].indexOf(mode)
    AI_instruction = instructions[1][instructionKeyIndex];

    // json to combine prompt and AI instruction
    const promptparts = [
      {text: ``},
      {text: "hello"},
      {text: "output: "},
    ];
    promptparts[2].text = prompt;
    promptparts[1].text = AI_instruction;

    // image to send
    const imageParts = [
      {
        inlineData: {
          data: currentImageBase64,
          mimeType: "image/jpeg"
        }
      }
    ];

    if (mode == ".coord"){
      const result = await modelCoord.generateContentStream([promptparts, ...imageParts]); // get the output from gemini
      let text = '';  // stores the full-streamed text
      for await (const chunk of result.stream) {  // process each chunk of data from gemini
        const chunkText = await chunk.text();
        text += chunkText;
      }
      let cleanJsonString = text.replace(/^```json\n/, '').replace(/```$/, '');    //filter the string
      let fullJSON = JSON.parse(cleanJsonString);
      let instruction_gemini = fullJSON.instruction;

      win.webContents.send("back_msg", instruction_gemini);
      win.webContents.send("coord_process", text);
      ws.send(instruction_gemini); // say the text as voice
      text = '';
    } else {
      const result = await model.generateContentStream([promptparts, ...imageParts]); // get the output from gemini
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
            ws.send(chunk_array[0] + chunk_array[1]); // say the chunk as voice
          }
          chunk_array.length = 0;
        }
      }
      if(chunk_array.length > 0){
        if(voice_on){
          ws.send(chunk_array[0]);  // say the last chunk
        }
      }
      chunk_array.length = 0;
      text = '';
    }
  }

  // check for any user event from renderer
  ipcMain.on("msg", (event, arg) => {
    if (arg === '.txt_rec'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.obj_dtc'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.img_des'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("captureHigh");
    } else if (arg === '.freeform'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("captureHigh");
    } else if (arg === '.ai_chat'){
      mode = arg;
      ai_chat();
    } else if (arg === '.coord'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("captureHigh");
    } else if (arg === 'stabelize_on'){
      mode = 'stabelize_on';
      requestCapture("startStream");
    } else if (arg === 'stabelize_off'){
      mode = 'stabelize_off';
    } else if (arg === 'stop_speech'){
      ws.send('tts_stop');
    } else if (arg == 'restart_app'){
      restartApp();
    }
  });  
});
