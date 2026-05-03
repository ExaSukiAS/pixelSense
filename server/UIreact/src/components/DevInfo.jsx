const ResourceSection = ({ title, usage, maxVal, unit, showPercentage }) => {
    return (
        <div className="resource">
            <div className="card-label">{title}</div>
            <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${(usage/maxVal*100).toFixed(0)}%` }}/>
            </div>
            <div className="card-stats">
                <span>{usage}{unit}/{maxVal}{unit}</span>
                <span>{(usage/maxVal*100).toFixed(0)}%</span>
            </div>
        </div>
    );
};

export const DevInfo = ({resources, info, heading}) => {
    const resTitles = Object.keys(resources); 
    const infoTitles = Object.keys(info); 
    return (
        <div className="devInfo">
            <span className="heading">{heading}</span>
            {resTitles.map((title) => {
                const data = resources[title];
                return (
                    <ResourceSection
                        key={title}
                        title={title}
                        maxVal={data.max}
                        usage={data.usage}
                        unit={data.unit}
                    />
                );
            })}
            <div className="telemetry-list">
                {infoTitles.map((title) => {
                    const data = info[title];
                    return(
                        <div className="telemetry-item" key={title}>
                            <span className="label">{title}</span>
                            <span className="value primary">{`${data.value}${data.unit}`}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};