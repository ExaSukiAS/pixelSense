export const DeviceTelemetery = ({distance, frameLatency, wifiSignal}) =>{
    return(
        <div className="telemetry-card">
            <span className="material-symbols-outlined bg-icon">query_stats</span>
            <h3>Device Telemetry</h3>
            <div className="telemetry-list">
                <div className="telemetry-item">
                    <span className="label">TOF distance</span>
                    <span className="value primary">{`${distance}cm`}</span>
                </div>
                <div className="telemetry-item">
                    <span className="label">Frame Latency</span>
                    <span className="value tertiary">{`${frameLatency}ms`}</span>
                </div>
                <div className="telemetry-item">
                    <span className="label">WIFI Signal</span>
                    <span className="value primary">{`${wifiSignal}dBm`}</span>
                </div>
            </div>
        </div>
    )
}