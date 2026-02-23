from twilio.rest import Client
from src.backend.config import TWILIO_XML_URL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, OPENAI_API_KEY
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
import requests
from flask import Flask, jsonify
import os

app = Flask(__name__)
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

@app.route('/make-call')
def make_call():
    call = client.calls.create(
        to="5135809384",
        from_="+16572988370",
        url=TWILIO_XML_URL,
        method='GET',
        record=True
    )

    print(f"Call SID: {call.sid}")

    return jsonify({"message": "Call Successful!"}), 200

def get_most_recent_recording():
    recordings = client.recordings.list(limit=1)
    path = os.path.join(os.getcwd(), "twilio_outputs\\raw_recordings\\")

    for rec in recordings:
        recording_url = f"https://api.twilio.com{rec.uri.replace('.json', '.wav')}"
        response = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

        with open(f"{path}{rec.sid}.wav", "wb") as f:
            f.write(response.content)

        # Transcribe using Whisper
        with open(f"{path}{rec.sid}.wav", "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        return {'recording_id': rec.sid, 'transcript': transcript.text}

@app.route('/post-call-action', methods=['GET'])
def call_trainscript_gen():
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Step 1: Get the recording from Twilio
        future_recording = executor.submit(get_most_recent_recording)
        recording_transcript = future_recording.result()  # waits until done

        with open(os.path.join(os.getcwd(), f'twilio_outputs\\transcripts\\output{recording_transcript.get('recording_id')}.txt'), 'w+') as f:
            f.write(recording_transcript.get('recording_id'))
            f.write(recording_transcript.get('transcript'))

    return recording_transcript

if __name__ == "__main__":
    app.run(debug=True, port=5000)