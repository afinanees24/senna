"""Offline text-to-speech for SENNA navigation prompts."""

import wave
from pathlib import Path
from piper import PiperVoice


class TextToSpeech:
    """Wraps Piper TTS for navigation prompt synthesis."""

    def __init__(self, model_path=None):
        if model_path is None:
            model_path = Path(__file__).parent / "models" / "piper" / "en_US-lessac-medium.onnx"
        self._voice = PiperVoice.load(str(model_path))
        self.sample_rate = self._voice.config.sample_rate

    def synthesize_to_file(self, text, output_path):
        """Save synthesis as a WAV file. Handles multiple Piper API versions."""
        # Newest API: synthesize_wav writes directly to a wave file
        if hasattr(self._voice, 'synthesize_wav'):
            with wave.open(str(output_path), "wb") as wav:
                self._voice.synthesize_wav(text, wav)
            return

        # Newer API: synthesize() returns iterator of AudioChunk objects
        chunks = list(self._voice.synthesize(text))
        if not chunks:
            raise RuntimeError("Piper returned no audio chunks")
        first = chunks[0]

        with wave.open(str(output_path), "wb") as wav:
            if hasattr(first, 'audio_int16_bytes'):
                # AudioChunk objects
                wav.setnchannels(first.sample_channels)
                wav.setsampwidth(first.sample_width)
                wav.setframerate(first.sample_rate)
                for c in chunks:
                    wav.writeframes(c.audio_int16_bytes)
            elif isinstance(first, bytes):
                # Raw bytes chunks
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                for c in chunks:
                    wav.writeframes(c)
            else:
                raise RuntimeError(f"Unknown Piper chunk type: {type(first)}")
