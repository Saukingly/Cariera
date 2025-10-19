# apps/services.py

from django.conf import settings
import requests
import os
import subprocess
import tempfile
import certifi

def transcribe_audio_rest(webm_audio_data: bytes) -> str:
    """
    Transcribes audio data from webm format to text using Azure Speech Service.
    It uses ffmpeg to convert the audio to the required WAV format.
    """
    temp_webm_path, temp_wav_path = None, None
    try:
        # Create a temporary file to store the received webm audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_webm:
            temp_webm.write(webm_audio_data)
            temp_webm_path = temp_webm.name

        # Define the path for the output wav file
        temp_wav_path = temp_webm_path + '.wav'

        # Use ffmpeg to convert webm to wav (16kHz, 16-bit PCM, mono)
        command = [
            'ffmpeg',
            '-i', temp_webm_path,
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            temp_wav_path
        ]
        print(f"--- Running ffmpeg command: {' '.join(command)} ---")
        subprocess.run(command, check=True, capture_output=True)

        # Read the converted wav file data
        with open(temp_wav_path, 'rb') as wav_file:
            wav_audio_data = wav_file.read()

        # Prepare the request to Azure Speech to Text API
        url = f"https://{settings.AZURE_SPEECH_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-US"
        headers = {
            'Ocp-Apim-Subscription-Key': settings.AZURE_SPEECH_KEY,
            'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000'
        }

        # Send the audio data for transcription with a 15-second timeout
        response = requests.post(url, headers=headers, data=wav_audio_data, verify=certifi.where(), timeout=15)
        response.raise_for_status()
        result = response.json()

        # Process the result
        if result.get('RecognitionStatus') == 'Success':
            transcribed_text = result.get('DisplayText', '')
            print(f"--- Successfully transcribed audio: '{transcribed_text}' ---")
            return transcribed_text
        else:
            print(f"--- Azure Speech recognition failed: {result.get('RecognitionStatus')} ---")
            return ""

    except FileNotFoundError:
        print("!!! FATAL ERROR: `ffmpeg` is not installed or not in your system's PATH. !!!")
        return "Server configuration error: ffmpeg is missing."
    except subprocess.CalledProcessError as e:
        print(f"!!! ERROR during ffmpeg conversion: {e.stderr.decode()} ---")
        return "Audio processing failed on the server."
    except requests.exceptions.Timeout:
        print(f"!!! TIMEOUT ERROR during transcription. The request to Azure took too long. !!!")
        return "The transcription service took too long to respond."
    except Exception as e:
        print(f"!!! An unexpected error occurred in transcribe_audio_rest: {e} !!!")
        return "An unexpected server error occurred."
    finally:
        # Clean up the temporary files
        if temp_webm_path and os.path.exists(temp_webm_path):
            os.remove(temp_webm_path)
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)
