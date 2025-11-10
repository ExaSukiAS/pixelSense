const WebSocket = require('ws');

const espIP = '192.168.68.106'; // local IP of esp32
const espPort = 9000;

const espWsAddr = `ws://${espIP}:${espPort}`;
const esp_ws = new WebSocket(espWsAddr);  // open esp32 websocket
esp_ws.on('open', () => {   // check if esp32 websocket port is opened
    console.log('ESP32 connected via websocket');
});

esp_ws.on('message', (data) => {
    if(data.includes("$#TXT#$")){
        data = data.toString().replace("$#TXT#$", "");
        console.log("text data received:"+data);
    } else {
        console.log("image received");
    }
});