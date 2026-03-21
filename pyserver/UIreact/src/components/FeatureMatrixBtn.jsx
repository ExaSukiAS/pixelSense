const Button = ({icon, text, isActive, onClick}) =>{
    return(
        <button className={`matrix-btn ${isActive ? "active" : ""}`} onClick={() => onClick(text)}>
            <span className="material-symbols-outlined">{icon}</span>
            <span>{text}</span>
        </button>
    )
};

/*
Example featureButtons JSON:
    {
        "Button Name":{Buttonicon: "Button icon", isActive: false},
        "Freeform":{icon: "draw", isActive: true}
    }
*/
export const FeatureMatrix = ({featureButtons, onClick}) =>{
    const titles = Object.keys(featureButtons); // get the keys (titles)
    return(
        <div className="button-grid">
            {titles.map((title) => {
                const button = featureButtons[title];
                return(<Button icon={button.icon} text={title} isActive={button.isActive} onClick={onClick} key={button.title}></Button>)
            })}
        </div>
    )
};