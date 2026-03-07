import { toggleStatusPill, colors, featureRunningIndication, setLoader, drawConnectedBoundingBoxes } from "./utilities.js";
import { marked } from 'https://cdn.jsdelivr.net/npm/marked@4.0.10/lib/marked.esm.js';

// DOM elements
const espStatusPill = document.getElementById("espStatusPill");
const voiceStatusPill = document.getElementById("voiceStatusPill");
const serverStatusPill = document.getElementById("serverStatusPill");

// Top row buttons
const terminateButton = document.getElementById("terminateButton");
const streamButton = document.getElementById("streamButton");

// Grid buttons
const txtRecButton = document.getElementById("txt_rec");
const objDtcButton = document.getElementById("obj_dtc");
const imgDesButton = document.getElementById("img_des");
const freeformButton = document.getElementById("freeform");
const coordButton = document.getElementById("coord");
const aiChatButton = document.getElementById("ai_chat");

const cameraImage = document.getElementById("cameraImage");
const imageContainer = document.querySelector(".imageContainer");
const systemLogSpan = document.getElementById("systemLogSpan");

const taskLoader = document.querySelector(".taskLoader");
const taskPercentageSpan = document.getElementById("taskPercentageSpan");
const levelInnerDiv = document.getElementById("levelInnerDiv");

let socket = null;
let reconnectDelay = 2000;
let serverConnected = false;
// connects with python server
// Add this helper to the top of your script to track the current URL
let currentImgUrl = null;

function connect() {
    console.log("Attempting to connect...");
    socket = new WebSocket('ws://localhost:8070');
    
    // CRITICAL: Tell the socket to receive raw bytes for images
    socket.binaryType = "arraybuffer";

    socket.addEventListener('open', () => {
        serverConnected = true;
        toggleStatusPill(serverStatusPill, true);
    });

    socket.addEventListener('message', event => {
        if (typeof event.data === 'string') {
            const msgArray = event.data.split("$@#$");
            if (msgArray.length == 2) {
                const msgType = msgArray[0];
                const msg = msgArray[1];
                handleSocketMessage(msgType, msg);
            }
        } else {
            handleBinaryMessage(event.data);
        }
    });

    socket.addEventListener('close', () => {
        serverConnected = false;
        toggleStatusPill(serverStatusPill, false);
        toggleStatusPill(espStatusPill, false);
        toggleStatusPill(voiceStatusPill, false);
        setTimeout(connect, reconnectDelay);
    });

    socket.addEventListener('error', (err) => {
        serverConnected = false;
        toggleStatusPill(serverStatusPill, false);
        toggleStatusPill(espStatusPill, false);
        toggleStatusPill(voiceStatusPill, false);
        socket.close();
    });
}
connect();

// mode buttons
txtRecButton.addEventListener('click', () => { socket.send(".txt_rec");})
objDtcButton.addEventListener('click', () => { socket.send(".obj_dtc"); })
imgDesButton.addEventListener('click', () => { socket.send(".img_des"); })
freeformButton.addEventListener('click', () => { socket.send(".freeform"); })
coordButton.addEventListener('click', () => { socket.send(".coord"); })
aiChatButton.addEventListener('click', () => { socket.send(".ai_chat"); })
terminateButton.addEventListener('click', () => { 
    socket.send("terminate"); 
    terminateTask();
})
let streamToggle = false;
streamButton.addEventListener('click', () => {
    socket.send(streamToggle ? "stopStream" : "startStream");

    const stremIcon = `<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#e3e3e3"><path d="M371-200h218l-20-80H391l-20 80Zm-11-160h240q83 0 141.5-58.5T800-560q0-83-58.5-141.5T600-760H360q-83 0-141.5 58.5T160-560q0 83 58.5 141.5T360-360Zm63.5-143.5Q400-527 400-560t23.5-56.5Q447-640 480-640t56.5 23.5Q560-593 560-560t-23.5 56.5Q513-480 480-480t-56.5-23.5ZM260-600q17 0 28.5-11.5T300-640q0-17-11.5-28.5T260-680q-17 0-28.5 11.5T220-640q0 17 11.5 28.5T260-600ZM160-120v-80h129l21-84q-99-17-164.5-94.5T80-560q0-117 81.5-198.5T360-840h240q117 0 198.5 81.5T880-560q0 104-65.5 181.5T650-284l21 84h129v80H160Zm433-327q47-47 47-113t-47-113q-47-47-113-47t-113 47q-47 47-47 113t47 113q47 47 113 47t113-47ZM480-560ZM371-200h218-218Z"/></svg>`;
    streamButton.innerHTML = streamToggle ? `${stremIcon}Start Stream` : `${stremIcon}Stop Stream`;

    streamButton.style.backgroundColor = streamToggle ? colors.blue : colors.lightBlue;
    streamButton.style.color = streamToggle ? "white" : colors.darkGrey;

    const svg = streamButton.querySelector("svg");
    svg.style.fill = streamToggle ? "white" : colors.darkGrey;

    streamToggle = !streamToggle;
})

// handles messages from python process
function handleSocketMessage(msgType, msg){
    console.log(msgType+"  "+msg);
    if(msgType == "activate"){
        switch(msg){
            case "espConnected":
                toggleStatusPill(espStatusPill, true);
                break;
            case "voiceConnected":
                toggleStatusPill(voiceStatusPill, true);
                break;
            case ".freeform":
                featureRunningIndication(freeformButton, true);
                break;
            case ".txt_rec":
                featureRunningIndication(txtRecButton, true);
                break;
            case ".obj_dtc":
                featureRunningIndication(objDtcButton, true);
                break;
            case ".img_des":
                featureRunningIndication(imgDesButton, true);
                break;
            case ".coord":
                featureRunningIndication(coordButton, true);
                break;
            case ".ai_chat":
                featureRunningIndication(aiChatButton, true);
                break;
            case "terminateTask":
                terminateTask();
                break;
            default:
                break;
        }
    } else if (msgType == "loader"){
        msg = parseInt(msg)
        setLoader(taskLoader, taskPercentageSpan, levelInnerDiv, msg);
    } else if (msgType == "log"){
        systemLogSpan.innerHTML = marked(msg);
    } else if (msgType == "coordinates"){
        let coordinates = JSON.parse(msg);
        const handCoord = coordinates.hand;
        const objCoord = coordinates.object;
        coordinates = [handCoord, objCoord];
        drawConnectedBoundingBoxes(coordinates, imageContainer, cameraImage, systemLogSpan, true);
    }
}

function handleBinaryMessage(buffer) {
    const view = new Uint8Array(buffer);
    // b'\x01' + image_bytes
    const header = view[0];
    if (header === 1) { // 1 = IMG type
        const imageData = buffer.slice(1);
        const blob = new Blob([imageData], { type: 'image/jpeg' });

        if (currentImgUrl) {
            URL.revokeObjectURL(currentImgUrl);
        }

        currentImgUrl = URL.createObjectURL(blob);
        cameraImage.src = currentImgUrl;
    }
}

function terminateTask(){
    setLoader(taskLoader, taskPercentageSpan, levelInnerDiv, "0");
    featureRunningIndication(freeformButton, false);
    featureRunningIndication(txtRecButton, false);
    featureRunningIndication(objDtcButton, false);
    featureRunningIndication(imgDesButton, false);
    featureRunningIndication(coordButton, false);
    featureRunningIndication(aiChatButton, false);
    systemLogSpan.innerHTML = "";
}
