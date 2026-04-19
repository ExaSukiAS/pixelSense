export const BatteryIndicator = ({voltage}) => {
    return(
        <div className="battery-container">
            <span className="material-symbols-outlined icon">electric_bolt</span>
            <span className="batteryVoltage">{voltage}v</span>
        </div>
    )
};