export const StreamButton = ({isStarted, onClick}) =>{
    return (
        <button className="btn btn-primary" onClick={onClick}>
            <span className="material-symbols-outlined icon">videocam</span> 
            {isStarted ? "Stop Stream" : "Start Stream"}
        </button>
    )
};