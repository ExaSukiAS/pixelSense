const speakButton = document.getElementById('enableAudioButton');

const synth = window.speechSynthesis;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const textQueue = [];

// print all the available voices with their indices
function loadVoices() {
  const voices = synth.getVoices();

  voices.forEach((voice, index) => {
    console.log(
      `${index}: ${voice.name} | ${voice.lang} | local=${voice.localService}`
    );
  });
}

// some browsers load voices async
if (speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = loadVoices;
}

// also call once in case they're already loaded
loadVoices();

speakButton.addEventListener('click', () => {
  const socket = new WebSocket('ws://localhost:8080'); // websocket connection

  // utters a specefic text chunk
  async function speakNextChunk() {
    console.log(textQueue.length);

    // select the specific chunk of text to be uttered
    if (textQueue.length === 0) {
      return;
    }
    const nextChunk = textQueue.shift();

    const utterance = new SpeechSynthesisUtterance(nextChunk);

    // voice configuration
    utterance.voice = synth.getVoices()[6]; 
    utterance.rate = 1.2; 
    utterance.pitch = 1; 

    // detect end of textQueue array
    utterance.onend = () => {
      if(textQueue.length === 0){
        console.log("terminated");
      }
      speakNextChunk();
    };

    synth.speak(utterance);
    console.log("speaking:", nextChunk);
  }

  console.log("Sound Enabled");
  socket.addEventListener('message', event => {
    console.log(event.data);
    if (event.data == 'stt'){ // received speech-to-text conversion initiation command
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
    } else if (event.data == 'tts_stop'){ // received text-to-speech termination command
      synth.cancel();
    } else { // received text-to-speech conversion (no initiation command is required, the message itself determines the text-chunk to be uttered)
      const chunkText = event.data;
      console.log(chunkText);
      textQueue.push(chunkText);
      console.log("length: ",textQueue.length);
      speakNextChunk(); 
    }
  });
});

