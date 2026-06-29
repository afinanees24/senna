"""Offline voice recognition for SENNA destination input."""

import json
import queue
import time
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceRecognition:
    """Wraps Vosk for offline speech-to-text."""

    def __init__(self, model_path=None, sample_rate=16000):
        if model_path is None:
            model_path = Path(__file__).parent / "models" / "vosk" / "vosk-model-small-en-us-0.15"
        self._model = Model(str(model_path))
        self.sample_rate = sample_rate

    def listen(self, timeout_s=10.0):
        """Block until speech detected or timeout. Returns transcribed text (lowercase)."""
        rec = KaldiRecognizer(self._model, self.sample_rate)
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=callback,
        ):
            start = time.time()
            while time.time() - start < timeout_s:
                try:
                    data = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if result.get('text'):
                        return result['text'].lower().strip()
            # Final partial result if timeout hit
            result = json.loads(rec.FinalResult())
            return result.get('text', '').lower().strip()
