// server connection variables
const serverWebsocketPort = 8070;
export let socket = null;
const reconnectDelay = 2000;

let currentImgUrl = null;

let onActivationMsgFunc = null;
let onLogMsgFunc = null;
let onCoordinateMsgFunc = null;
let onImageMsgFunc = null;
let onDepthMapFunc = null;
let onLoaderMsgFunc = null;
let onStatsFunc = null;

export const setupSocket = (onActivationMsg, onLogMsg, onStats, onLoaderMsg, onCoordinateMsg, onImage, onDepthMap) =>{
    onActivationMsgFunc = onActivationMsg;
    onLogMsgFunc = onLogMsg;
    onCoordinateMsgFunc = onCoordinateMsg;
    onImageMsgFunc = onImage;
    onLoaderMsgFunc = onLoaderMsg;
    onStatsFunc = onStats;
    onDepthMapFunc = onDepthMap;

    connectToServer();
}

const connectToServer = () => {
    console.log("Attempting to connect...");
    socket = new WebSocket(`ws://localhost:${serverWebsocketPort}`);
    
    socket.binaryType = "arraybuffer"; // tell the socket to receive raw bytes for images

    socket.addEventListener('open', () => {
      onActivationMsgFunc("serverConnected");
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
            handleSocketBINmessage(event.data);
        }
    });

    socket.addEventListener('close', () => {
        onActivationMsgFunc("allDisconnected");
        setTimeout(() => {
            connectToServer();
        }, reconnectDelay);
    });

    socket.addEventListener('error', (err) => {
        onActivationMsgFunc("allDisconnected");
        socket.close();
    });
}

// handles messages from python process
const handleSocketMessage = (msgType, msg) => {
    switch(msgType){
        case "activate":
            onActivationMsgFunc(msg);
            break;
        case "log":
            onLogMsgFunc(msg);
            break;
        case "loader":
            const [percentage, message] = msg.split("@#$@"); // split into loading message and loading percentage parts
            onLoaderMsgFunc(percentage, message);
            break;
        case "stats":
            const [stats, boardType] = msg.split("$");
            let [totalSRAM, totalPSRAM, usedSRAM, usedPSRAM, cpuTemp, volt, distance, wifiSignal] = stats.split(",");
            volt = volt/10;
            onStatsFunc(boardType, totalSRAM, totalPSRAM, usedSRAM, usedPSRAM, cpuTemp, volt, distance, wifiSignal);
            break;
        case "coordinates":
            const coordinates = JSON.parse(msg);
            onCoordinateMsgFunc([coordinates.hand, coordinates.object]);
            break;
    }
}

const handleSocketBINmessage = (buffer) => {
    const view = new Uint8Array(buffer);

    const firstByte = view[0];
    const bufferType = view[1];

    // If your image messages have a header of 1:
    if (firstByte == 1 && bufferType != 4) {
        const frameID = (view[2] << 24) | (view[3] << 16) | (view[4] << 8) | view[5];
        const imageData = buffer.slice(6);
        const blob = new Blob([imageData], { type: 'image/jpeg' });

        currentImgUrl = URL.createObjectURL(blob);
        onImageMsgFunc(currentImgUrl, bufferType, frameID);
    } 
    // If firstByte is 4 (or whatever showed up in your console log)
    else if (bufferType == 4) {
        const rawDataBuffer = buffer.slice(2); 
        const depthArray16 = new Uint16Array(rawDataBuffer);
        onDepthMapFunc(depthArray16);
    }
}