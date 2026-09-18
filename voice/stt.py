from sarvamai import SarvamAI
from sarvamai.play import save

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("SARVAM_API")

client = SarvamAI(
    api_subscription_key=api_key,
)

try:
    response = client.speech_to_text.transcribe(
        file=open("output.wav", "rb"),
        model="saaras:v4",
        mode="translate"
    )
    print(response.transcript)
except Exception as e:
    print(f"Error: {e}")






