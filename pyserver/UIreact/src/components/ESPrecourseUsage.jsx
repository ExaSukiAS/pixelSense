const ResourceSection = ({ title, usage, maxVal, unit }) => {
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

/* Example Resources JSON:
   {
       "ESP32 CPU Usage": { "max": 240, "usage": 50, "unit": "MHz" },
       "RAM Usage": { "max": 520, "usage": 30, "unit": "KB" }
   }
*/
export const ESPresourceUsage = ({resources}) => {
    const titles = Object.keys(resources); // get the keys (titles)
    return (
        <div className="resource-card">
            {titles.map((title) => {
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
        </div>
    );
};