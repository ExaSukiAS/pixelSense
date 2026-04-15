import { useEffect, useState } from "react";
import { CameraFeed } from "./components/CameraFeed";
import { ConnectionIndicators } from "./components/ConnectionIndicators"
import { DeviceTelemetery } from "./components/deviceTelemetry"
import { ESPresourceUsage } from "./components/ESPrecourseUsage"
import { FeatureMatrix } from "./components/FeatureMatrixBtn";
import { StreamButton } from "./components/StreamButton";
import { LogPanel } from "./components/LogPanel";
import { setupSocket, socket } from "./socket";
import { initVoice } from "./voice"

function App() { 
  const [featureMatrixButtons, setFeatureButton] = useState({
    "Text Recognition": {"icon": "text_fields", "isActive": false},
    "Object Detection": {"icon": "target","isActive": false},
    "Image Desc": {"icon": "image_search","isActive": false},
    "Freeform": {"icon": "draw","isActive": false},
    "Coordination": {"icon": "account_tree","isActive": false},
    "AI Chat": {"icon": "chat","isActive": false}
  });
  const [ESPresources, setESPresources] = useState({
    "ESP32 CPU Usage": { "max": 0, "usage": 0, "unit": "MHz"},
    "ESP32 SRAM Usage": { "max": 0, "usage": 0, "unit": "KB"},
    "ESP32 PSRAM Usage": { "max": 0, "usage": 0, "unit": "KB"},
  });
  const [deviceTelemetery, setDeviceTelemetery] = useState({distance: 0, frameLatency: 0, wifiSignal: 0});
  const [connectionStates, setConnStates] = useState({esp: false, voice: false, server: false});
  const [logPanelContent, setLogPanelContent] = useState({content:"", taskPercentage:0, log:""})

  const [cameraStats, setCameraStats] = useState({fps: 0, res: "640x480", isStreaming: false});
  const [cameraBuffer, setCamBuffer] = useState("https://cdn.pixabay.com/photo/2021/12/12/20/00/play-6865967_1280.jpg");
  const [boundingBox, setBbox] = useState([]);

  const [streamState, setStreamState] = useState(false);

  // activates or deactivates a feature button
  const setFeatureActive = (name, value) => {
    setFeatureButton(prev => ({
      ...prev,
      [name]: {
        ...prev[name],
        isActive: value
      }
    }));
  };

  const terminateTask = () => {
    socket.send("terminate"); 
    // reset UI
    setLogPanelContent({content:"", taskPercentage:0, log:""});
    setFeatureButton({
      "Text Recognition": {"icon": "text_fields", "isActive": false},
      "Object Detection": {"icon": "target","isActive": false},
      "Image Desc": {"icon": "image_search","isActive": false},
      "Freeform": {"icon": "draw","isActive": false},
      "Coordination": {"icon": "account_tree","isActive": false},
      "AI Chat": {"icon": "chat","isActive": false}
    })
  };

  class Socket{
    constructor(){}

    handleActivationMsg(msg){
      switch(msg){
          case "serverConnected":
              setConnStates((prev) => ({...prev, server: true}));
              break;
          case "espConnected":
              setConnStates((prev) => ({...prev, esp: true}));
              break;
          case "voiceConnected":
              setConnStates((prev) => ({...prev, voice: true}));
              break;
          case "allDisconnected":
              setConnStates({esp: false, voice: false, server: false});
              break;
          case ".freeform":
              setFeatureActive("Freeform", true);
              break;
          case ".txt_rec":
              setFeatureActive("Text Recognition", true);
              break;
          case ".obj_dtc":
              setFeatureActive("Object Detection", true);
              break;
          case ".img_des":
              setFeatureActive("Image Desc", true);
              break;
          case ".coord":
              setFeatureActive("Coordination", true);
              break;
          case ".ai_chat":
              setFeatureActive("AI Chat", true);
              break;
          case "terminateTask":
              terminateTask();
              break;
          default:
              break;
      }
    }

    handleLogs(log){
      setLogPanelContent((prev) => ({...prev, content: log}));
    }

    handleStats(totalSRAM, totalPSRAM, usedSRAM, usedPSRAM, cpu, distance){
      setESPresources({
        "ESP32 CPU Usage": { "max": 240, "usage": cpu, "unit": "MHz"},
        "ESP32 SRAM Usage": { "max": totalSRAM, "usage": usedSRAM, "unit": "KB"},
        "ESP32 PSRAM Usage": { "max": totalPSRAM, "usage": usedPSRAM, "unit": "KB"},
      });
      setDeviceTelemetery((prev) => ({...prev, distance: distance/10}));
    }

    handleLoader(percentage, msg){
      setLogPanelContent((prev) => ({...prev, taskPercentage: percentage, log: msg}));
    }

    handleCoordinate(coordinate){
      setBbox(coordinate);
    }

    handleImg(image){
      setCamBuffer(image);
    }
  }

  const initApp = () =>{
    initVoice();
    const socketHandler = new Socket();
    setupSocket(
      socketHandler.handleActivationMsg, 
      socketHandler.handleLogs, 
      socketHandler.handleStats,
      socketHandler.handleLoader,
      socketHandler.handleCoordinate, 
      socketHandler.handleImg
    );
  }
  useEffect(() => {initApp()}, []);

  class ButtonClicksHandler{
    constructor(){}

    handleFeature = (buttonName) => {
      switch (buttonName) {
        case "Freeform":
          socket.send(".freeform");
          break;
        case "Text Recognition":
          socket.send(".txt_rec");
          break;
        case "Object Detection":
          socket.send(".obj_dtc");
          break;
        case "Image Desc":
          socket.send(".img_des");
          break;
        case "Coordination":
          socket.send(".coord");
          break;
        case "AI Chat":
          socket.send(".ai_chat");
          break;
        default:
          console.warn(`Unknown feature: ${buttonName}`);
      }
    }

    handleStream = () =>{
      socket.send(streamState ? "stopImageStream" : "startImageStream")
      setStreamState((prev) => (!prev));
    }

    handleTermination = () =>{
      terminateTask();
    }
  }
  const buttonClick = new ButtonClicksHandler();

  return (
    <>
      <header className="top-bar">
        <div className="top-bar__brand">
          <span className="logo-text">Pixelsense</span>
          <ConnectionIndicators states={connectionStates}></ConnectionIndicators>
        </div>
        <div className="top-bar__actions">
          <StreamButton isStarted={streamState} onClick={buttonClick.handleStream}></StreamButton>
          <button className="btn btn-error" onClick={buttonClick.handleTermination}>
            <span className="material-symbols-outlined icon">cancel</span> Terminate
          </button>
          <button className="btn btn-tertiary" id="enableAudioButton">
                <span className="material-symbols-outlined icon">mic</span> Audio
          </button>
        </div>
      </header>
      <div className="app-layout">
        <aside className="sidebar">
          <DeviceTelemetery distance={deviceTelemetery.distance} frameLatency={deviceTelemetery.frameLatency} wifiSignal={deviceTelemetery.wifiSignal}></DeviceTelemetery>
          <ESPresourceUsage resources={ESPresources}></ESPresourceUsage>
        </aside>
        <main className="main-content">
          <div className="dashboard-grid">
            <div className="grid-primary">
              <CameraFeed buffer={cameraBuffer} normalizedBbox={boundingBox} fps={cameraStats.fps} resolution={cameraStats.res} isStreaming={cameraStats.isStreaming}></CameraFeed> 
              <LogPanel log={logPanelContent.log} taskPercentage={logPanelContent.taskPercentage} content={logPanelContent.content}></LogPanel>
            </div>
            <div className="grid-secondary">
              <div className="matrix-card">
                <h3>Feature Control Matrix</h3>
                <FeatureMatrix featureButtons={featureMatrixButtons} onClick={buttonClick.handleFeature}></FeatureMatrix>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}

export default App
