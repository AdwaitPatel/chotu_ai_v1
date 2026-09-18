from sarvamai import SarvamAI
from sarvamai.play import save

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("SARVAM_API")

client = SarvamAI(
    api_subscription_key=api_key,
)

llm_output = """
छोटू... २ किलो आटा, और ५ किलो... मैदा गोदाम में दाल दे।
"""


try:
    audio = client.text_to_speech.convert(
        text=llm_output,
        language_code="hi-IN",
        model="bulbul:v3",
        speaker="simran",
    )
    save(audio, "output.wav")
except Exception as e:
    print(f"Error: {e}")



