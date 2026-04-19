import { useEffect, useState } from "react";
import { CameraFeed } from "./components/CameraFeed";
import { ConnectionIndicators } from "./components/ConnectionIndicators";
import { FeatureMatrix } from "./components/FeatureMatrixBtn";
import { StreamButton } from "./components/StreamButton";
import { LogPanel } from "./components/LogPanel";
import { setupSocket, socket } from "./socket";
import { DevInfo } from "./components/DevInfo";
import { ViewControlCard } from "./components/ViewControl";
import { BatteryIndicator } from "./components/batteryIndicator";

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
    "left":{
      "SRAM Usage": { "max": 0, "usage": 0, "unit": "KB"},
    },
    "right":{
      "SRAM Usage": { "max": 0, "usage": 0, "unit": "KB"},
    }
  });
  const [deviceTelemetery, setDeviceTelemetery] = useState({
    "left":{
      "WiFi Signal": {value: 0, unit: "dBm"}, 
      "CPU Temperature": {value: 0, unit: "°C"},
      "TOF reading": {value: 0, unit: "cm"}
    },
    "right":{
      "WiFi Signal": {value: 0, unit: "dBm"}, 
      "CPU Temperature": {value: 0, unit: "°C"},
      "TOF reading": {value: 0, unit: "cm"}
    }
  });
  const [voltage, setVoltage] = useState(0);

  const [connectionStates, setConnStates] = useState({espLeft: false, espRight: false, server: false});
  const [logPanelContent, setLogPanelContent] = useState({content:"", taskPercentage:0, log:""})

  const [cameraBuffer, setCamBuffer] = useState(["./assets/footage.jpg", "./assets/footage.jpg", "./assets/footage.jpg"]);
  const [boundingBox, setBbox] = useState([]);

  const [streamState, setStreamState] = useState({left: false, right: false});
  const [viewState, setViewState] = useState({left: true, right: true, depth: true});
  const [frameWidth, setFrameWidth] = useState({left: 49, right: 49, depth: 49});

  useEffect(() =>{
    
  }, [viewState])

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
          case "espLeftConnected":
              setConnStates((prev) => ({...prev, espLeft: true}));
              break;
          case "espRightConnected":
              setConnStates((prev) => ({...prev, espRight: true}));
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

    handleStats(boardType, totalSRAM, totalPSRAM, usedSRAM, usedPSRAM, cpuTemp, volt, distance, wifiSignal){
      setESPresources((prev) => ({
        ...prev,
        [boardType]: {
          "SRAM Usage": { max: totalSRAM, usage: usedSRAM, unit: "KB" }
        }
      }));
      setDeviceTelemetery((prev) => ({
        ...prev,
        [boardType]: {
          "WiFi Signal": {value: wifiSignal, unit: "dBm"}, 
          "CPU Temperature": {value: cpuTemp, unit: "°C"},
          "TOF reading": {value: distance/10, unit: "cm"}
        }
      }));
      // only accept voltage from teh left board, because teh right board will provide garbage voltage readings
      if(boardType == "left"){
        setVoltage(volt);
      }
    }

    handleLoader(percentage, msg){
      setLogPanelContent((prev) => ({...prev, taskPercentage: percentage, log: msg}));
    }

    handleCoordinate(coordinate){
      setBbox(coordinate);
    }

    handleImg(image, imageTypeInt){ // imageTypeInt can be : 1 for left view, 2 for right view and 3 for depth view
      // change teh specific image
      setCamBuffer(prevBuffer => 
        prevBuffer.map((item, index) => 
          index === imageTypeInt-1 ? image : item
        )
      );
    }
  }

  const initApp = () =>{
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

    handleStream = (deviceType) =>{
      if(deviceType == "left"){
        socket.send(streamState.left ? "stopLeftImageStream" : "startLeftImageStream")
        setStreamState((prev) => ({...prev, left: !prev.left}));
      } else if(deviceType == "right"){
        socket.send(streamState.right ? "stopRightImageStream" : "startRightImageStream")
        setStreamState((prev) => ({...prev, right: !prev.right}));
      }
    }

    handleTermination = () =>{
      terminateTask();
    }

    handleView = (viewType) => {
      setViewState((prev) => {
        const nextState = { ...prev, [viewType]: !prev[viewType] };
        const activeCount = Object.values(nextState).filter(Boolean).length;
        setFrameWidth(() => ({
          left:  (activeCount === 1 && nextState.left)  ? 100 : 49,
          right: (activeCount === 1 && nextState.right) ? 100 : 49,
          depth: (activeCount === 1 && nextState.depth) ? 100 : 49,
        }));

        return nextState;
      });
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
          <StreamButton status={streamState} onClick={buttonClick.handleStream}></StreamButton>
          <button className="btn btn-error" onClick={buttonClick.handleTermination}>
            <span className="material-symbols-outlined icon">cancel</span> Terminate
          </button>
          <BatteryIndicator voltage={voltage}></BatteryIndicator>
        </div>
      </header>
      <div className="app-layout">
        <aside className="sidebar">
          <DevInfo resources={ESPresources.left} info={deviceTelemetery.left} heading="ESP LEFT"></DevInfo>
          <DevInfo resources={ESPresources.right} info={deviceTelemetery.right} heading="ESP RIGHT"></DevInfo>
        </aside>
        <main className="main-content">
          <div className="dashboard-grid">
            <div className="grid-primary">
              <div className="cameraFeedGrid">
                <div className="cameraFrame" style={{display: viewState.left ? "flex" : "none", width: `${frameWidth.left}%`}}>
                  <CameraFeed buffer={cameraBuffer[0]} normalizedBbox={boundingBox}></CameraFeed> 
                </div>
                <div className="cameraFrame" style={{display: viewState.right ? "flex" : "none", width: `${frameWidth.right}%`}}>
                  <CameraFeed buffer={cameraBuffer[1]} normalizedBbox={boundingBox}></CameraFeed> 
                </div>
                <div className="cameraFrame" style={{display: viewState.depth ? "flex" : "none", width: `${frameWidth.depth}%`}}>
                  <CameraFeed buffer={cameraBuffer[2]} normalizedBbox={boundingBox}></CameraFeed> 
                </div>
              </div>
              <LogPanel log={logPanelContent.log} taskPercentage={logPanelContent.taskPercentage} content={logPanelContent.content}></LogPanel>
            </div>
            <div className="grid-secondary">
              <div className="matrix-card">
                <h3>Feature Control Matrix</h3>
                <FeatureMatrix featureButtons={featureMatrixButtons} onClick={buttonClick.handleFeature}></FeatureMatrix>
              </div><div className="viewCards">
                <ViewControlCard status={viewState} onClick={buttonClick.handleView}></ViewControlCard>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}

export default App
