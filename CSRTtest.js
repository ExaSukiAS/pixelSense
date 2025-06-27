const { spawn } = require('child_process');
const fs = require('fs');
const json = require('jsonfile');

const py = spawn('python', ['CSRTtracker.py']);

const imgBase64 = fs.readFileSync("./jpgs/3.jpg").toString('base64');
const rio = "523, 279, 87, 213"; // x,y,width,height
const combined = {"imgBase64": imgBase64,"rio": rio};

py.stdin.write(JSON.stringify(combined) + '\n');  // send the first frame with rio

function sendContinuousFrame(){
  for (let i = 3; i < 229; i++){
    const imgPath = `./jpgs/${i}.jpg`;
    const imgBase64 = fs.readFileSync(imgPath).toString('base64');
    const imgJSON = {"imgBase64": imgBase64};
    py.stdin.write(JSON.stringify(imgJSON) + '\n');  // send the next frames with rio
  }
}

py.stdout.on('data', (data) => {
  console.log('Python output:', data.toString());
  if(data = 'initialized'){
    sendContinuousFrame();
  }
});
py.stderr.on('data', (data) => {
  console.error('Python error:', data.toString());
});