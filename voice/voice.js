let speakButton = document.getElementById('speakButton');

const synth = window.speechSynthesis;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const textQueue = [];

speakButton.addEventListener('click', () => {
  const socket = new WebSocket('ws://localhost:8080');

  async function speakNextChunk() {
    console.log(textQueue.length);
    if (textQueue.length === 0) {
      return;
    }
    const nextChunk = textQueue.shift();
    const utterance = new SpeechSynthesisUtterance(nextChunk);

    utterance.voice = synth.getVoices()[16]; 
    utterance.rate = 1.2; 
    utterance.pitch = 1; 

    utterance.onend = () => {
      if(textQueue.length === 0){
        console.log("terminated");
        //socket.send();
      }
      speakNextChunk();
    };

    synth.speak(utterance);
  }

  console.log("Sound Enabled");
  socket.addEventListener('message', event => {
    if (event.data == 'stt'){
      console.log("speech recognition started");
      let output_text_array = [];
      const recognition = new SpeechRecognition();
      recognition.interimResults = true;
      recognition.start();
      recognition.addEventListener('result', (event) => {
          const transcript = Array.from(event.results)
              .map(result => result[0])
              .map(result => result.transcript)
              .join('');
          output_text_array.push(transcript);
      });
      recognition.addEventListener('end', () => {
          console.log("speech recognition ended");
          console.log(output_text_array[output_text_array.length - 1]);
          socket.send(output_text_array[output_text_array.length - 1]);
      });
    } else if (event.data == 'tts_stop'){
      synth.cancel();
    } else {
      const chunkText = event.data;
      console.log(chunkText);
      textQueue.push(chunkText);
      console.log("length:",textQueue.length);
      speakNextChunk(); 
    }
  });
});

