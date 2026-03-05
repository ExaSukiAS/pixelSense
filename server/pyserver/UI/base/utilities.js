export const colors = {
  "darkGrey": "#131314",
  "paragraphColor": "#dfdfdf",
  "grey": "#2c2c2c",
  "lightGrey": "#424242",

  "placeholderColor": "#747474",
  "headingColor": "#FFFFFF",

  "blue": "#4e83ef",
  "lightBlue": "#80aaff",
  "darkBlue": "#283143",
  "violet": "#9872cc",
  "pink": "#c36990",
  "red": "#d82f48",
  "green": "#4ddb99"
}

export function toggleStatusPill(element, status) {
    if (!element) return;

    const span = element.querySelector("span");
    const svg = element.querySelector("svg");

    const color = status ? colors.green : colors.red;

    // Border color
    element.style.borderColor = color;

    // Text color
    if (span) {
        span.style.color = color;
    }

    // SVG fill color
    if (svg) {
        svg.style.fill = color;
    }
}

export function featureRunningIndication(element, status){
    if (!element) return;
    element.classList.toggle("feature-running", status);
}

export function setLoader(taskLoader, taskPercentageSpan, levelInnerDiv, targetValue){
    let currentValue = parseInt(taskPercentageSpan.textContent);
    // smooth transition
    if (targetValue > currentValue){
        for (let i = currentValue; i <= targetValue; i++) {
            setTimeout(() => {
                taskPercentageSpan.innerHTML = i + '%';
            }, 10 * (i - currentValue)); 
        }
    } else {
        for (let i = currentValue; i >= targetValue; i--) {
            setTimeout(() => {
                taskPercentageSpan.innerHTML = i + '%';
            }, 10 * (currentValue - i)); 
        }
    }

    levelInnerDiv.style.width = targetValue+'%';

    if(targetValue == 0){
        taskPercentageSpan.style.opacity = '0';
        taskLoader.style.opacity = "0";
    } else {
        taskPercentageSpan.style.opacity = '1';
        taskLoader.style.opacity = "1";
    }
}

// draws bounding boxes
// box data format: [{"x":xVal, "y":yVal, "width":width, "height":height, "label":label}, ...]
export function drawConnectedBoundingBoxes(boxData, imageContainer, image, systemLog, flushExisting = true) {
    if (boxData.length === 0 || boxData.length > 2) return;

    // remove existing boxes if needed
    if (flushExisting) {
        document.querySelectorAll('.bounding_box').forEach(element => element.remove());
        document.querySelectorAll('.diagonal-line').forEach(element => element.remove());
    }

    let boxMids = []; // store midpoints of boxes

    // draw the boxes and calculate midpoints of each box
    boxData.forEach(box => {
        if(box.x == 0 && box.y == 0 && box.width == 0 && box.height == 0){
            if(box.label == "Hand"){
                message.innerHTML = "Hand out of frame";
            } else {
                message.innerHTML = "Object out of frame";
            }
            return;
        }
        // convert normalized(0 - 1000 scale) to pixel values
        console.log(image.width)
        console.log(image.height)
        box.x = (box.x/1000) * image.width;
        box.y = (box.y/1000) * image.height;
        box.width = (box.width/1000) * image.width;
        box.height = (box.height/1000) * image.height;

        const bboxDiv = document.createElement('div');
        bboxDiv.classList.add('bounding_box');
        bboxDiv.style.top = `${box.y}px`;
        bboxDiv.style.left = `${box.x}px`;
        bboxDiv.style.width = `${box.width}px`;
        bboxDiv.style.height = `${box.height}px`;

        const labelDiv = document.createElement('div');
        labelDiv.classList.add('bounding_box-label');
        labelDiv.textContent = box.label;
        bboxDiv.appendChild(labelDiv);

        imageContainer.appendChild(bboxDiv);

        boxMids.push({"midX": box.x + box.width / 2, "midY": box.y + box.height / 2});
    });

    // draw lines between boxes
    const diagonalDiv = document.createElement('div');
    diagonalDiv.classList.add('diagonal-line');

    const length = Math.sqrt((boxMids[1].midX - boxMids[0].midX) ** 2 + (boxMids[1].midY - boxMids[0].midY) ** 2);
    const angle = Math.atan2(boxMids[1].midY - boxMids[0].midY, boxMids[1].midX - boxMids[0].midX) * (180 / Math.PI);

    diagonalDiv.style.width = `${length}px`;
    diagonalDiv.style.transform = `rotate(${angle}deg)`;
    diagonalDiv.style.left = `${boxMids[0].midX}px`;
    diagonalDiv.style.top = `${boxMids[0].midY}px`;

    imageContainer.appendChild(diagonalDiv);

    // determine direction to reach box0 from box1 through words (left-right or up-down or here)

    const xErrorRange = 60; // two points within xErrorRange pixels in x-axis are considered aligned
    const yErrorRange = 60; // two points within yErrorRange pixels in y-axis are considered aligned
    let direction = ""; // direction to reach box0 from box1

    let xError = boxMids[1].midX - boxMids[0].midX;
    let yError = boxMids[1].midY - boxMids[0].midY;

    if(xError > xErrorRange){
        direction = "left ";
    } else if (xError < -xErrorRange){
        direction = "right ";
    } else if (yError > yErrorRange){
        direction = "up";
    } else if (yError < -yErrorRange){
        direction = "down";
    } else {
        direction = "here";
    }
    systemLog.innerHTML = direction;
}