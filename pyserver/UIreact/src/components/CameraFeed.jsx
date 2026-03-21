import { useEffect, useRef, useState } from "react"

// converts normalized box data (must be in 0 to 1000 scale) to pixel format
const getPixelBbox = (normalizedBbox, imgWidth, imgHeight) =>{
    return({
        "x": normalizedBbox.x*imgWidth/1000, 
        "y": normalizedBbox.y*imgHeight/1000,
        "width": normalizedBbox.width*imgWidth/1000,
        "height": normalizedBbox.height*imgHeight/1000
    })
};

// box data format: [{"x":xVal, "y":yVal, "width":width, "height":height, "label":label}, ...]
const getBboxConnectionLine = (pixelBboxes) =>{
    if (pixelBboxes.length != 2) return{x:0, y:0, length:0, angle:0};

    const boxMids = [
        {"x": pixelBboxes[0].x + pixelBboxes[0].width / 2, "y": pixelBboxes[0].y + pixelBboxes[0].height / 2},
        {"x": pixelBboxes[1].x + pixelBboxes[1].width / 2, "y": pixelBboxes[1].y + pixelBboxes[1].height / 2}
    ]

    const lineLength = Math.sqrt((boxMids[1].x - boxMids[0].x) ** 2 + (boxMids[1].y - boxMids[0].y) ** 2);
    const lineAngle = Math.atan2(boxMids[1].y - boxMids[0].y, boxMids[1].x - boxMids[0].x) * (180 / Math.PI);
    const lineOriginX = boxMids[0].x;
    const lineOriginY = boxMids[0].y;

    return {x:lineOriginX, y:lineOriginY, length:lineLength, angle:lineAngle};
};

// box data format: [{"x":xVal, "y":yVal, "width":width, "height":height, "label":label}, ...]
export const CameraFeed = ({buffer, normalizedBbox, fps, resolution, isStreaming}) => {
    const imgRef = useRef(null);
    const [imgSize, setImgSize] = useState({ width: 0, height: 0 });
    const [connectionLine, setConnectionLine] = useState({x:0, y:0, length:0, angle:0});

    useEffect(() => {
        if (imgSize.width === 0 || normalizedBbox.length === 0) return;

        const pixelBboxes = normalizedBbox.map(box =>
            getPixelBbox(box, imgSize.width, imgSize.height)
        );

        const line = getBboxConnectionLine(pixelBboxes);
        setConnectionLine(line);
    }, [normalizedBbox, imgSize]);

    return (
        <div className="video-feed">

            {/* Draw bounding boxes */}
            {normalizedBbox.map((box, index) => {
                    const pixelBbox = getPixelBbox(box, imgSize.width, imgSize.height);
                    return (
                        <div key={index} className="bbox" style={{top: `${pixelBbox.y}px`, left: `${pixelBbox.x}px`, width: `${pixelBbox.width}px`, height: `${pixelBbox.height}px`}}>
                            <div className="bbox-label">{box.label}</div>
                        </div>
                    )
            })}

            <div 
                className="connection-line" 
                style={{
                    width: `${connectionLine.length}px`,
                    top: `${connectionLine.y}px`,
                    left: `${connectionLine.x}px`,
                    transform: `rotate(${connectionLine.angle}deg)`
                }}
            ></div>

            <img  ref={imgRef} className="feed-image" src={buffer} onLoad={() => {setImgSize({width: imgRef.current.width, height: imgRef.current.height});}}/>

            <div className="feed-overlay">
                <div className="live-badge">
                    <span className={`pulse-dot ${isStreaming ? "live" : ""}`} />
                    <span>{isStreaming ? "LIVE CAPTURE" : "STATIC CAPTURE"}</span>
                </div>
                <div className="stream-stats">{resolution} | {fps}FPS</div>
            </div>

        </div>
    );
};