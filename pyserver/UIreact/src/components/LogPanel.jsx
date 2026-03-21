export const LogPanel = ({log, taskPercentage, content}) =>{
    return(
        <div className="log-panel">
            <div className="panel-header">
                <span className="material-symbols-outlined">auto_awesome</span>
                <h3>Inference Log &amp; AI response</h3>
            </div>
            <div className="logs" style={{display: log != "" ? "flex" : "none"}}>
                <div className="loader" />
                <div className="log-content">{`${taskPercentage}%  ${log}`}</div>
            </div>
            <span className="panel-content">{content}</span>
        </div>
    )
}