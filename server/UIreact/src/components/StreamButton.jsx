export const StreamButton = ({status, onClick}) =>{
    return (
        <div className = "streamButtons">
            <button className="btn btn-primary" onClick={() => onClick("left")}>
                <span className="material-symbols-outlined icon">videocam</span> 
                {status.left ? "Stop Left Stream" : "Stream Left"}
            </button>
            <button className="btn btn-primary" onClick={() => onClick("right")}>
                <span className="material-symbols-outlined icon">videocam</span> 
                {status.right ? "Stop Right Stream" : "Stream Right"}
            </button>
        </div>
    )
};