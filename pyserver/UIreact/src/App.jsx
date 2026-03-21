import { useEffect, useState } from "react";
import { CameraFeed } from "./components/CameraFeed";
import { ConnectionIndicators } from "./components/ConnectionIndicators"
import { DeviceTelemetery } from "./components/deviceTelemetry"
import { ESPresourceUsage } from "./components/ESPrecourseUsage"
import { FeatureMatrix } from "./components/FeatureMatrixBtn";
import { StreamButton } from "./components/StreamButton";
import { LogPanel } from "./components/LogPanel";

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
    "ESP32 CPU Usage": { "max": 240, "usage": 120, "unit": "MHz"},
    "ESP32 SRAM Usage": { "max": 520, "usage": 100, "unit": "KB"},
    "ESP32 PSRAM Usage": { "max": 4000, "usage": 500, "unit": "KB"},
  });
  const [deviceTelemetery, setDeviceTelemetery] = useState({distance: 0, frameLatency: 0, wifiSignal: 0});
  const [connectionStates, setConnStates] = useState({esp: false, voice: false, server: false});
  const [logPanelContent, setLogPanelContent] = useState({content:"", taskPercentage:0, log:""})

  const [cameraStats, setCameraStats] = useState({fps: 0, res: "640x480", isStreaming: false});
  const [cameraBuffer, setCamBuffer] = useState("https://cdn.pixabay.com/photo/2021/12/12/20/00/play-6865967_1280.jpg");
  const [boundingBox, setBbox] = useState([]);

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

  class ButtonClicksHandler{
    constructor(){}

    handleFeature = (buttonName) => {
      console.log("clicked:  "+buttonName);
    }

    handleStream = () =>{
    }

    handleTermination = () =>{
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
          <StreamButton isStarted={false} onClick={buttonClick.handleStream}></StreamButton>
          <button className="btn btn-error" onClick={buttonClick.handleTermination}>
            <span className="material-symbols-outlined icon">cancel</span> 
            Terminate
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
