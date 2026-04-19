export const ViewControlCard  = ({status, onClick}) => {
    return(
        <div className="viewPills">
            <div className={`viewPill ${status.left ? "active" : ""}`} onClick={() => onClick("left")}><span>Left View</span></div>
            <div className={`viewPill ${status.right ? "active" : ""}`} onClick={() => onClick("right")}><span>Right View</span></div>
            <div className={`viewPill ${status.depth ? "active" : ""}`} onClick={() => onClick("depth")}><span>Depth View</span></div>
        </div>
    );
};