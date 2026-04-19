export const ConnectionIndicators = ({states}) => {
    return (
          <div className="status-indicators">
            <div className="status-badge">
              <span className={`indicator ${states.espLeft == true ? "connected" : ""}`} />
              <span className="label">ESPS3 LEFT</span>
            </div>
            <div className="status-badge">
              <span className={`indicator ${states.espRight == true ? "connected" : ""}`} />
              <span className="label">ESPS3 RIGHT</span>
            </div>
            <div className="status-badge">
              <span className={`indicator ${states.server == true ? "connected" : ""}`} />
              <span className="label">SERVER</span>
            </div>
          </div>
    )
}