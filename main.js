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

const wss = new WebSocket.Server({ port: 8080 });

function restartApp() {
  app.relaunch();
  app.quit();
}

wss.on('connection', ws => {  // check if audio feature is turned on
  let esp_ip_port = 'ws://192.168.68.104:9000';
  win.webContents.send("audio", 1); 
  console.log("sound Enabled");

  let esp_ws;
  let mode;
  let esp_data;

  // connect to esp32
  function esp_connect() {
    esp_ws = new WebSocket(esp_ip_port);  // open websocket
    let pingInterval;
    let pongReceived = false;   //bool to check if pong is received

    function startPingPong() {
        clearInterval(pingInterval);
        pingInterval = setInterval(() => {
            if (pongReceived) {   // check if esp32 responds
                pongReceived = false;
                esp_ws.ping();  // ping esp32 to receive data
            } else {
                console.log('ESP32 connection lost');
                esp_ws.terminate();  
                win.webContents.send("esp_connect", 0);
                esp_connect();
            }
        }, 5000); // interval to check connection
    }

    esp_ws.on('open', () => {   // check if esp32 websocket port is opened
        console.log('ESP32 connected via websocket');
        win.webContents.send("esp_connect", 1);
        pongReceived = true;
        startPingPong();  // check for connection stability
    });

    esp_ws.on('pong', () => {   // check if esp32 responds
        pongReceived = true;  
    });

    // message handling from esp32
    esp_ws.on('message', (data) => {
        if (typeof data === 'string') {   // pre-check if data is string
            console.log(data);
        } else if (Buffer.isBuffer(data)) {   // pre-check if data is an image
            try {
                const text = data.toString('utf8');
                if (/^[\x00-\x7F]*$/.test(text)) {  // data from esp32 is a text
                    esp_data = text;
                    console.log("esp_data:", text);
                } else {  // data from esp32 is an image
                    saveImage(data, (err) => {  
                        if (!err) {
                            handleMode(); // handle the mode that user wants (mode var is already set by button click event)
                        }
                    });
                }
            } catch (e) {
                saveImage(data, (err) => {
                    if (!err) {
                        handleMode();
                    }
                });
            }
        }
    });

    esp_ws.on('close', () => {  // check if esp32 is disconnected
        console.log('Disconnected from ESP32');
        win.webContents.send("esp_connect", 0);
        clearInterval(pingInterval);
        setTimeout(esp_connect, 200); // reconnect to esp32
    });

    esp_ws.on('error', (error) => { // check for websocket error
        console.error('ESP32 WebSocket error:', error);
        esp_ws.close();
        win.webContents.send("esp_connect", 0);
    });
}

// function to save the image
function saveImage(data, callback) {
    const filePath = path.join(__dirname, 'user.jpg');
    sharp(data)
        .rotate(0)
        .toFile(filePath, (err, info) => {
            if (err) {
                console.error('Failed to save the image:', err);
            } else {
                console.log('Image saved to:', filePath);
            }
            if (callback) callback(err);
        });
}

// function to handle mode that user wants (mode var is already set by button click event)
function handleMode() {
    console.log(mode);
    switch (mode) {
        case ".obj_dtc":
            object_detection();
            break;
        case ".img_des":
            image_description();
            break;
        case ".txt_rec":
            text_recognition();
            break;
        case ".freeform":
            freeform();
            break;
        case ".coord":
            coordination();
            break;
        case 'stabelize_on':
            stabelization();
            break;
    }
}

esp_connect();  // connect to esp32


  // function to fetch an image from esp32
  function requestCapture(highOrLow) {
    if (esp_ws.readyState === WebSocket.OPEN) {
      if (highOrLow === "high") { // high res image (1600x1200)
        esp_ws.send("captureHigh");
      } else if (highOrLow == "low"){ // low res image (480p)
        esp_ws.send("captureLow");
      }
    }
  }

  const apiJSON = JSON.parse(fs.readFileSync('geminiAPI.json', 'utf8'));  // read api key from json file
  const apiKey = apiJSON.apiKey;
  const genAI = new GoogleGenerativeAI(apiKey); // create gemini session 

  // function to convert image into gemini understandable text
  function fileToGenerativePart(path, mimeType) {
    return {
      inlineData: {
        data: Buffer.from(fs.readFileSync(path)).toString("base64"),
        mimeType
      },
    };
  }
  
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
      fileToGenerativePart("user.jpg", "image/jpeg"),
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


  async function run_AI_CHAT(prompt) {
    const result = await model.generateContentStream(prompt);
    let text = '';
    let chunk_array = [];
    let chunk_size = 2;
    for await (const chunk of result.stream) {
      const chunkText = await chunk.text();
      chunk_array.push(chunkText);
      text += chunkText;
      win.webContents.send("back_msg", text);
      if(chunk_array.length >= chunk_size){
        ws.send(chunk_array[0] + chunk_array[1]);
        chunk_array.length = 0;
      }
    }
    if(chunk_array.length > 0){
      ws.send(chunk_array[0]);
    }
  }

  // function for text recognition feature
  async function text_recognition(){
    mode = '.txt_rec';

    win.webContents.send("update_img", 1);
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
  async function object_detection(){
    mode = '.obj_dtc';

    win.webContents.send("update_img", 1);
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
  async function image_description(){
    mode = '.img_des';

    win.webContents.send("update_img", 1);
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
  async function freeform(){
    mode = '.freeform';

    win.webContents.send("update_img", 1);

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
  async function coordination(){
    mode = '.coord';

    win.webContents.send("update_img", 1);

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

  // function for AI chat feature
  async function ai_chat(){
    win.webContents.send("back_msg", 'Waiting for user input... ...');
    win.webContents.send("level_indicate", 50);
    ws.send('stt');
    const messageHandler = async (websocket_event) => {
      console.log(websocket_event.data);
      win.webContents.send("back_msg", websocket_event.data);
      await run_AI_CHAT(websocket_event.data);
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

  // function for testing for proper positioning of paper
  function stabelization(){
    win.webContents.send("update_img", 1);
  }

  let stabelizeIntervalID; 
  // check for any user event from renderer
  ipcMain.on("msg", (event, arg) => {
    if (arg === '.txt_rec'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("high");
    } else if (arg === '.obj_dtc'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("high");
    } else if (arg === '.img_des'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 20);
      requestCapture("high");
    } else if (arg === '.freeform'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("high");
    } else if (arg === '.ai_chat'){
      mode = arg;
      ai_chat();
    } else if (arg === '.coord'){
      mode = arg;
      win.webContents.send("back_msg", 'Fetching Image... ...');
      win.webContents.send("level_indicate", 40);
      requestCapture("high");
    } else if (arg === 'stabelize_on'){
      mode = 'stabelize_on';
      stabelizeIntervalID = setInterval(() => requestCapture("low"), 2000);
    } else if (arg === 'stabelize_off'){
      clearInterval(stabelizeIntervalID);
    } else if (arg === 'stop_speech'){
      ws.send('tts_stop');
    } else if (arg == 'restart_app'){
      restartApp();
    }
  });  
});