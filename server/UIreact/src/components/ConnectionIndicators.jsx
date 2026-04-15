export const ConnectionIndicators = ({states}) => {
    return (
          <div className="status-indicators">
            <div className="status-badge">
              <span className={`indicator ${states.esp == true ? "connected" : ""}`} />
              <span className="label">ESP32</span>
            </div>
            <div className="status-badge">
              <span className={`indicator ${states.voice == true ? "connected" : ""}`} />
              <span className="label">VOICE</span>
            </div>
            <div className="status-badge">
              <span className={`indicator ${states.server == true ? "connected" : ""}`} />
              <span className="label">SERVER</span>
            </div>
          </div>
    )
}