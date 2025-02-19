const { ipcRenderer } = require('electron');
import { marked } from 'https://cdn.jsdelivr.net/npm/marked@4.0.10/lib/marked.esm.js';

// get all UI elements
let dynamic_island = document.querySelector('.dynamic_island');
        
let ai_chat = document.querySelector('.ai_chat');
let freeform = document.querySelector('.freeform');
let obj_dtc = document.querySelector('.obj_dtc');
let txt_rec = document.querySelector('.txt_rec');
let img_des = document.querySelector('.img_des');
let coord = document.querySelector('.coord');
let camera = document.querySelector('.camera');

let stop_btn = document.querySelector('.stop');
let camera_btn = document.querySelector('.camera');
let un_mute_btn = document.querySelector('.un_mute');
let interrupt_btn = document.querySelector('.interrupt');


let level = document.querySelector('.level');
let level_text = document.querySelector('.level_text');

let message = document.querySelector('.message');
let image_show = document.querySelector('.image_show');
let imageContainer = document.querySelector('.img_container');

let audio_icon = document.getElementById('audio_icon');
let glass_connect = document.querySelector('.glass_connect span');
let voltage  = document.querySelector('.voltage');

let alignImageSpan = document.querySelector('.alignImage span');

ipcRenderer.on("audio", (event, arg) => {   // check if audio feature is turned on
    if (arg == 1) {
        // event listener for keyboard shortcut events
        document.addEventListener("keydown", function(event) {
            var keyCode = event.keyCode;
            console.log(keyCode);
        
            switch(keyCode) {
                case 87:
                    ai_chat.click();
                  break;
                case 83:
                    obj_dtc.click();
                  break;
                case 68:
                    img_des.click();
                break;
                case 65:
                    txt_rec.click();
                break;
                case 71:
                    freeform.click();
                break;
                case 72:
                    camera.click();
                break;
                case 70:
                    coord.click();
                break;
                case 75:
                    terminate_task();
                break;
                case 76:
                    ipcRenderer.send("msg", 'restart_app');
                break;
                default:
              }
          });
    

        // act of voltage change of esp32
        ipcRenderer.on("voltage_change", (event, arg) => {
            let has_comma = arg.includes(",");
            if(has_comma){
                let formatted_V = arg.split(",");
                voltage.innerHTML = formatted_V[2] + "V";
            } else{
                voltage.innerHTML = arg + "V";
            }
        });

        // change UI according to esp32's connection status
        ipcRenderer.on("esp_connect", (event, arg) => {
            if(arg == 1){
                glass_connect.style.color = 'rgba(148, 255, 180, 0.8)';
                glass_connect.style.textShadow = '0 0px 4px rgba(148, 255, 180, 0.8)';
            } else if (arg == 0){
                glass_connect.style.color = '#e83345';
                glass_connect.style.textShadow = '0 0px 4px #e83345';
            }
        })

        // act on bluetooth trigger from esp32
        ipcRenderer.on("ble_trigger", (event, arg) => {
            reset_style();
            document.querySelector(arg).click();
        })
        // termiate voice
        ipcRenderer.on("terminate", (event, arg) => {
            terminate_task();
        })
    
        audio_icon.style.color = 'rgba(148, 255, 180, 0.8)';
        audio_icon.style.textShadow = '0 0px 4px rgba(148, 255, 180, 0.8)';
        
        var isFreeform = 0;
        
        // for smooth transition of dynamic island's percentage text
        function increaseNumbers(start, end) {
            for (let i = start; i <= end; i++) {
                setTimeout(() => {
                    level_text.innerHTML = i + '%';
                }, 15 * (i - start)); 
            }
        }
        
        // show any message from main process
        ipcRenderer.on("back_msg", (event, arg) => {
            message.innerHTML = marked(arg);
        })
        
        // update the image on its change
        ipcRenderer.on("update_img", (event, arg) => {
            const timestamp = new Date().getTime();
            const imageUrl = `../user.jpg?${timestamp}`;
            image_show.setAttribute('src', imageUrl);
        })
        
        // for smooth transition of dynamic island's loading bar
        var y = 0;
        ipcRenderer.on("level_indicate", (event, arg) => {
            if (isFreeform == 0){
                level.style.width = 0.7*arg + 'vw';
                increaseNumbers(y, arg);
                y = arg;
            } else {
                level.style.width = 0.7*arg + 'vw';
                increaseNumbers(y, arg);
                y = arg;
            }
        })
        
        // check for any button click
        function btn_click(element){
            isFreeform = 0; // not in freeform mode
            setTimeout(() => {
                ipcRenderer.send("msg", element);   // notify main process for button click
                document.querySelector(element).style.animation = 'shadowAnimation 3s infinite alternate';
                document.querySelector(element).style.backgroundColor = '#2c2e37';
                document.querySelector(element).style.color = 'white';
                document.querySelector(element).style.transform = 'scale(1.1)';
                dynamic_island.style.top = '20px';
                dynamic_island.style.width = '90vw';
                dynamic_island.style.borderRadius = '500px';
                setTimeout(() => {
                    level.style.opacity = '1';
                    level_text.style.opacity = '1';
                    stop_btn.style.opacity = '1';
                    un_mute_btn.style.opacity = '0';
                    interrupt_btn.style.opacity = '0';
                }, 400);
            }, 100);
        }
        
        function aichatfn(){
            isFreeform = 0; // not in freeform mode
            setTimeout(() => {
                ipcRenderer.send("msg", '.ai_chat');
                document.querySelector('.ai_chat').style.animation = 'shadowAnimation 3s infinite alternate';
                document.querySelector('.ai_chat').style.backgroundColor = '#2c2e37';
                document.querySelector('.ai_chat').style.color = 'white';
                document.querySelector('.ai_chat').style.transform = 'scale(1.1)';
                dynamic_island.style.top = '20px';
                dynamic_island.style.width = '90vw';
                dynamic_island.style.borderRadius = '500px';
                setTimeout(() => {
                    level.style.opacity = '0';
                    level_text.style.opacity = '0';
                    stop_btn.style.opacity = '1';
                    un_mute_btn.style.opacity = '1';
                    interrupt_btn.style.opacity = '1';
        
                    stop_btn.style.width = '80px';
                    stop_btn.style.height = '80px';
                    stop_btn.style.top = '10px';
                    stop_btn.style.right = '200px';
                    document.querySelector('.stop span').style.fontSize = '45px';
                }, 400);
            }, 100);
        }
        
        function freeformfn(){
            isFreeform = 1; // not in freeform mode
            setTimeout(() => {
                ipcRenderer.send("msg", '.freeform');
                document.querySelector('.freeform').style.animation = 'shadowAnimation 3s infinite alternate';
                document.querySelector('.freeform').style.backgroundColor = '#2c2e37';
                document.querySelector('.freeform').style.color = 'white';
                document.querySelector('.freeform').style.transform = 'scale(1.1)';
                dynamic_island.style.top = '20px';
                dynamic_island.style.width = '90vw';
                dynamic_island.style.borderRadius = '500px';

                setTimeout(() => {
                    level.style.opacity = '1';
                    level_text.style.opacity = '1';
                    stop_btn.style.opacity = '1';
                    camera_btn.style.opacity = '1';
                }, 400);
            }, 100);
        }
        
        function camerafn(){
            ipcRenderer.send("msg", '.freeform');
        }

        class BoundingBoxDrawer {
            constructor(jsonData, filter) {
                this.jsonData = jsonData;
                this.boxes = [];
                this.filter = filter;
            }
        
            drawBoxAndLine() {
                let cleanJsonString = this.jsonData;
                if(this.filter){
                    cleanJsonString = this.jsonData.replace(/^```json\n/, '').replace(/```$/, '');
                }
                let boundingBoxesData = JSON.parse(cleanJsonString);
                const imageHeight = image_show.height;
                const imageWidth = image_show.width;
        
                boundingBoxesData.box_2d.forEach(boxData => {
                    const { ymin, ymax, xmin, xmax, label } = boxData;
        
                    const top = (ymin / 1000) * imageHeight;
                    const left = (xmin / 1000) * imageWidth;
                    const height = ((ymax - ymin) / 1000) * imageHeight;
                    const width = ((xmax - xmin) / 1000) * imageWidth;
        
                    const midX = left + width / 2;
                    const midY = top + height / 2;
                    this.boxes.push({ midX, midY });
        
                    const bboxDiv = document.createElement('div');
                    bboxDiv.classList.add('bounding_box');
                    bboxDiv.style.top = `${top}px`;
                    bboxDiv.style.left = `${left}px`;
                    bboxDiv.style.width = `${width}px`;
                    bboxDiv.style.height = `${height}px`;
        
                    const labelDiv = document.createElement('div');
                    labelDiv.classList.add('bounding_box-label');
                    labelDiv.textContent = label;
                    bboxDiv.appendChild(labelDiv);
        
                    imageContainer.appendChild(bboxDiv);
                });
        
                for (let i = 0; i < this.boxes.length - 1; i++) {
                    this.drawPath(this.boxes[i], this.boxes[i + 1]);
                    this.drawDiagonal(this.boxes[i], this.boxes[i + 1]);
                }
            }
        
            drawDiagonal(box1, box2) {
                const { midX: x1, midY: y1 } = box1;
                const { midX: x2, midY: y2 } = box2;
        
                const diagonalDiv = document.createElement('div');
                diagonalDiv.classList.add('diagonal-line');
        
                const length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
                const angle = Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);
        
                diagonalDiv.style.width = `${length}px`;
                diagonalDiv.style.transform = `rotate(${angle}deg)`;
                diagonalDiv.style.left = `${x1}px`;
                diagonalDiv.style.top = `${y1}px`;
        
                imageContainer.appendChild(diagonalDiv);
            }
        
            drawPath(box1, box2) {
                const { midX: x1, midY: y1 } = box1;
                const { midX: x2, midY: y2 } = box2;
        
                if (Math.abs(x1 - x2) > Math.abs(y1 - y2)) {
                    this.drawLine(x1, y1, x2, y1);
                    this.drawLine(x2, y1, x2, y2);
                } else {
                    this.drawLine(x1, y1, x1, y2);
                    this.drawLine(x1, y2, x2, y2);
                }
            }
        
            drawLine(xStart, yStart, xEnd, yEnd) {
                const lineDiv = document.createElement('div');
                lineDiv.classList.add('line');
        
                const width = Math.abs(xEnd - xStart);
                const height = Math.abs(yEnd - yStart);
        
                lineDiv.style.left = `${Math.min(xStart, xEnd)}px`;
                lineDiv.style.top = `${Math.min(yStart, yEnd)}px`;
        
                if (width > height) {
                    lineDiv.style.width = `${width}px`;
                    lineDiv.style.height = `2px`;
                } else {
                    lineDiv.style.width = `2px`;
                    lineDiv.style.height = `${height}px`;
                }
        
                imageContainer.appendChild(lineDiv);
            }
        }   
        
        let jsonStringUsed = '';
          
        // for processing coordination data
        ipcRenderer.on("coord_process", (event, arg) => {
            jsonStringUsed = arg;
            const drawer = new BoundingBoxDrawer(arg, true);
            drawer.drawBoxAndLine();
        })

        let minimized = true;
        // function to change teh size of the image 
        function changeSizeOfImage(){
            if (minimized){
                image_show.style.height = '100vh';
                imageContainer.style.top = '0';
                imageContainer.style.left = '0';
                document.querySelectorAll('.bounding_box, .line, .diagonal-line').forEach(element => element.remove());
                const drawer = new BoundingBoxDrawer(jsonStringUsed, true);
                drawer.drawBoxAndLine();
                minimized = false;
            } else {
                image_show.style.height = '50vh';
                imageContainer.style.top = '13vh';
                imageContainer.style.left = '4vw';
                document.querySelectorAll('.bounding_box, .line, .diagonal-line').forEach(element => element.remove());
                const drawer = new BoundingBoxDrawer(jsonStringUsed, true);
                drawer.drawBoxAndLine();
                minimized = true;
            }
        }

        // remove all boxes
        ipcRenderer.on("remove_boxes", (event, arg) => {
            document.querySelectorAll('.bounding_box, .line, .diagonal-line').forEach(element => element.remove());
        })

        let alignImageCount = 0;
        // function for aligning teh paper
        function alignImagefn(){
            alignImageCount += 1;
            if (alignImageCount > 0){
                if (alignImageCount % 2 == 0){
                    alignImageSpan.style.color = "#a3a3a3";
                    ipcRenderer.send("msg", 'stabelize_off');
                } else {
                    alignImageSpan.style.color = "white";
                    ipcRenderer.send("msg", 'stabelize_on');
                }
            }
        }
        
        var un_mute_count = 0;
        un_mute_btn.addEventListener("click", function() {
            un_mute_count += 1;
            if (un_mute_count != 0 && un_mute_count % 2 != 0){
                document.querySelector('.un_mute span').innerHTML = 'mic';
                ipcRenderer.send("msg_aichat", 'unmute');
            } else if (un_mute_count != 0 && un_mute_count % 2 == 0){
                document.querySelector('.un_mute span').innerHTML = 'mic_off';
                ipcRenderer.send("msg_aichat", 'mute');
            }
        });
        interrupt_btn.addEventListener("click", function() {
            ipcRenderer.send("msg_aichat", 'interrupt');
        });
        
        function terminate_task(){
            ipcRenderer.send("msg", 'stop_speech');
            isFreeform = 0;
            y = 0;
            setTimeout(() => {
                dynamic_island.style.top = '-70px';
                dynamic_island.style.width = '20vw';
                dynamic_island.style.borderRadius = '20px';
            }, 400);
        
            level.style.opacity = '0';
            level_text.style.opacity = '0';
            stop_btn.style.opacity = '0';
            un_mute_btn.style.opacity = '0';
            interrupt_btn.style.opacity = '0';
        
            ai_chat.style.animation = '';
            ai_chat.style.backgroundColor = '';
            ai_chat.style.color = '';
            ai_chat.style.transform = '';
        
            freeform.style.animation = '';
            freeform.style.backgroundColor = '';
            freeform.style.color = '';
            freeform.style.transform = '';
        
            obj_dtc.style.animation = '';
            obj_dtc.style.backgroundColor = '';
            obj_dtc.style.color = '';
            obj_dtc.style.transform = '';
        
            txt_rec.style.animation = '';
            txt_rec.style.backgroundColor = '';
            txt_rec.style.color = '';
            txt_rec.style.transform = '';
        
            img_des.style.animation = '';
            img_des.style.backgroundColor = '';
            img_des.style.color = '';
            img_des.style.transform = '';

            coord.style.animation = '';
            coord.style.backgroundColor = '';
            coord.style.color = '';
            coord.style.transform = '';
        
            camera_btn.style.opacity = '0';
        }

        function reset_style(){
            y = 0;
            ai_chat.style.animation = '';
            ai_chat.style.backgroundColor = '';
            ai_chat.style.color = '';
            ai_chat.style.transform = '';
        
            freeform.style.animation = '';
            freeform.style.backgroundColor = '';
            freeform.style.color = '';
            freeform.style.transform = '';
        
            obj_dtc.style.animation = '';
            obj_dtc.style.backgroundColor = '';
            obj_dtc.style.color = '';
            obj_dtc.style.transform = '';
        
            txt_rec.style.animation = '';
            txt_rec.style.backgroundColor = '';
            txt_rec.style.color = '';
            txt_rec.style.transform = '';
        
            img_des.style.animation = '';
            img_des.style.backgroundColor = '';
            img_des.style.color = '';
            img_des.style.transform = '';

            coord.style.animation = '';
            coord.style.backgroundColor = '';
            coord.style.color = '';
            coord.style.transform = '';
        }
        
        function interrupt_fn(){
            ipcRenderer.send("msg_aichat", 'interrupt');
        }
        
        function redofn(){
            ipcRenderer.send("msg_freeform", 1);
        }
        
        const functions = [terminate_task, interrupt_fn, redofn, btn_click, camerafn, aichatfn, freeformfn, alignImagefn, changeSizeOfImage];
        
        functions.forEach(func => {
            window[func.name] = func;
        });
    }
});


