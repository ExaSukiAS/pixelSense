const { ipcRenderer } = require('electron');
import { marked } from 'https://cdn.jsdelivr.net/npm/marked@4.0.10/lib/marked.esm.js';

// get all UI elements
const dynamic_island = document.querySelector('.dynamic_island');
        
const ai_chat = document.querySelector('.ai_chat');
const freeform = document.querySelector('.freeform');
const obj_dtc = document.querySelector('.obj_dtc');
const txt_rec = document.querySelector('.txt_rec');
const img_des = document.querySelector('.img_des');
const coord = document.querySelector('.coord');

const stop_btn = document.querySelector('.stop');
const camera_btn = document.querySelector('.camera');
const un_mute_btn = document.querySelector('.un_mute');
const interrupt_btn = document.querySelector('.interrupt');

const level = document.querySelector('.level');
const level_text = document.querySelector('.level_text');

const message = document.querySelector('.message');
const image_show = document.querySelector('.image_show');
const imageContainer = document.querySelector('.img_container');

const audio_icon = document.getElementById('audio_icon');
const glass_connect = document.querySelector('.glass_connect span');

const alignImageSpan = document.querySelector('.alignImage span');

ipcRenderer.on("audio", (event, arg) => {   // check if audio feature is turned on
    if (arg == 1) {
        // indicate audio is on
        audio_icon.style.color = 'rgba(148, 255, 180, 0.8)';audio_icon.style.textShadow = '0 0px 4px rgba(148, 255, 180, 0.8)';

        // show any message from main process
        ipcRenderer.on("back_msg", (event, arg) => {
            message.innerHTML = marked(arg);
        })
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
        // act on bluetooth trigger function from esp32
        ipcRenderer.on("ble_trigger", (event, arg) => {
            reset_style();
            document.querySelector(arg).click();
        })
        // termiates voice and all UI activity
        ipcRenderer.on("terminate", (event, arg) => {
            terminate_task();
        })
        // update the image on its change
        ipcRenderer.on("update_img", (event, arg) => {
            image_show.setAttribute('src', "data:image/png;base64,"+arg);
            image_show.style.opacity = '1';
        })

        var isFreeform = 0;
        
        // for smooth transition of dynamic island's percentage text
        function increaseNumbers(start, end) {
            for (let i = start; i <= end; i++) {
                setTimeout(() => {
                    level_text.innerHTML = i + '%';
                }, 15 * (i - start)); 
            }
        }
        
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
        
        // check for any button click and animate accordingly
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
        
        // draws bounding boxes
        // box data format: [{"x":xVal, "y":yVal, "width":width, "height":height, "label":label}, ...]
        function drawConnectedBoundingBoxes(boxData, flushExisting = true) {
            if (boxData.length === 0 || boxData.length > 2) return;

            // remove existing boxes if needed
            if (flushExisting) {
                document.querySelectorAll('.bounding_box').forEach(element => element.remove());
                document.querySelectorAll('.diagonal-line').forEach(element => element.remove());
            }

            let boxMids = []; // store midpoints of boxes

            // draw the boxes and calculate midpoints of each box
            boxData.forEach(box => {
                // convert normalized to pixel values
                box.x = box.x * image_show.width;
                box.y = box.y * image_show.height;
                box.width = box.width * image_show.width;
                box.height = box.height * image_show.height;

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
            message.innerHTML = direction;
        }
                
        // for processing coordination data
        ipcRenderer.on("drawBoxAndLine", (event, arg) => {
            drawConnectedBoundingBoxes(arg);
        })

        // remove all boxes
        ipcRenderer.on("remove_boxes", (event, arg) => {
            document.querySelectorAll('.bounding_box, .diagonal-line').forEach(element => element.remove());
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
        
        const functions = [terminate_task, interrupt_fn, redofn, btn_click, camerafn, aichatfn, freeformfn, alignImagefn];
        
        functions.forEach(func => {
            window[func.name] = func;
        });
    }
});


