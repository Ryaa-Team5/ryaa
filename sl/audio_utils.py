# audio_helpers.py
import os
import numpy as np
import pyaudio
import soundfile as sf
from openai import OpenAI
from io import BytesIO
from typing import IO
from pydub import AudioSegment
from pydub.playback import play as pydub_play
import streamlit as st


# from arklex.utils.model_config import TRANSCRIPTION_MODEL

from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings, stream, play
import logging

logger = logging.getLogger(__name__)


def transcribe_audio(audio_input):
    """
    transcription using OpenAI, and return the transcription.
    """
    # # Convert the raw bytes to a numpy array
    # audio_data = b"".join(frames)
    # audio_array = np.frombuffer(audio_data, dtype=np.int16)

    # Optional: Transcription test using OpenAI's API
    try:
        client = OpenAI()
        model = "whisper-1"

        transcription = client.audio.transcriptions.create(
            model=model, file=audio_input, response_format="text"
        )

        print(f"Transcribed: '{transcription}'")
        # FIXME: take result and pass it into the message queue
    except Exception as e:
        print(f"Transcription error: {e}")

    return transcription


def tts_conversion(text: str) -> IO[bytes]:
    # Get API key from environment
    elevenlabs_api_key = st.secrets["api_keys"]["ELEVENLABS_API_KEY"]
    if not elevenlabs_api_key:
        logger.warning(
            "ElevenLabs API key not found. Voice functionality will be limited."
        )

    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=elevenlabs_api_key)

    # Default voice settings
    default_voice_id = st.secrets["api_keys"]["DEFAULT_VOICE_ID"]

    default_voice_settings = {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
    }

    try:
        logger.debug("Starting TTS conversion.")
        response = client.text_to_speech.convert(
            text=text,
            voice_id=default_voice_id,
            model_id="eleven_multilingual_v1",
            output_format="mp3_22050_32",
            voice_settings=VoiceSettings(
                stability=default_voice_settings["stability"],
                similarity_boost=default_voice_settings["similarity_boost"],
                style=default_voice_settings["style"],
                use_speaker_boost=default_voice_settings["use_speaker_boost"],
            ),
        )

        audio_stream = BytesIO()

        for chunk in response:
            if chunk:
                audio_stream.write(chunk)

        audio_stream.seek(0)
        return audio_stream
    except Exception as e:
        logger.error(f"TTS conversion failed.{e}")


# def combined_audio(audio_chunks, audio_format="mp3"):
#     """
#     Combine a list of audio chunk events into one continuous audio stream and play it.

#     Each item in audio_chunks should be a dict containing:
#       - "event": a key, expected to be "audio" for audio chunks.
#       - "audio_chunk": the audio data as bytes.

#     The default format is assumed to be MP3.
#     """
#     combined_data = b"".join(
#         chunk.get("audio_chunk")
#         for chunk in audio_chunks
#         if chunk.get("event") == "audio"
#     )

#     if not combined_data:
#         print("No audio data to play.")
#         return

#     audio_stream = BytesIO(combined_data)
#     try:
#         sound = AudioSegment.from_file(audio_stream, format=audio_format)
#         # print("Playing combined audio...")
#         # pydub_play(sound)
#         return sound
#     except Exception as e:
#         print("Error during combined audio playback:", e)
