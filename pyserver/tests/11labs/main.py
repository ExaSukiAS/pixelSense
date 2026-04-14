import json
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

with open("apiKey.json", "r") as f:
    apiKey = json.load(f)["apiKey"]


elevenlabs = ElevenLabs(
  api_key=apiKey
)

def payAudio():
    audio = elevenlabs.text_to_speech.convert(
        text="A rainy day, marked by dark clouds and continuous drizzle or heavy rainfall, transforms the usual dull scenery into a fresh and lively landscape. Each droplet seems to carry a quiet calm, washing the streets clean and painting the world in muted, reflective tones.. The air is cool and smells of damp earth, a welcome relief from the recent heat. Inside, the rhythmic patter against the roof creates a soothing soundtrack.  Children splash in the water with joy and create paper boats, while others find comfort indoors with a warm drink and a book.  Outside, puddles form, mirroring the grey sky, and the trees glisten, their leaves freshly washed. Farmers especially welcome rainy days as the rain supports crop growth, irrigates fields, and increases agricultural productivity; without rain, crops like rice would not grow well. Just like the thunder strikes a sense of fear, the rain also brings hardships for many, especially for those without proper shelter. For the poor, a rainy day can mean flooded homes, leaking roofs, and cold, sleepless nights. Streets become muddy and slippery, making it difficult for people to move around or earn a living. Despite the struggles, a rainy day often paints the world in its own quiet beauty that inspires poets and stirs memories deep within the heart.",
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # "George" - browse voices at elevenlabs.io/app/voice-library
        model_id="eleven_flash_v2_5",
        output_format="mp3_44100_128",
    )
    play(audio)