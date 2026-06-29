import subprocess
import tempfile
from pathlib import Path

from senna_audio.head_tracker import HeadTracker
from senna_audio.tts import TextToSpeech
from senna_audio.voice import VoiceRecognition


class AudioSystem:
    """Top-level audio facade. Brain calls into this."""

    def __init__(self, audio_sink: str | None = None):
        self.head_tracker = HeadTracker()
        self.tts = TextToSpeech()
        self.voice = VoiceRecognition()
        self._sink = audio_sink

    def start(self) -> None:
        self.head_tracker.start()

    def stop(self) -> None:
        self.head_tracker.stop()

    def speak_prompt(self, text: str) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            self.tts.synthesize_to_file(text, wav_path)
            cmd = ["paplay"]
            if self._sink:
                cmd.append(f"--device={self._sink}")
            cmd.append(wav_path)
            subprocess.run(cmd, check=True)
        finally:
            Path(wav_path).unlink(missing_ok=True)

    def listen_for_destination(self, timeout_s: float = 10.0) -> str:
        return self.voice.listen(timeout_s=timeout_s)

    @property
    def head_orientation(self) -> tuple[float, float, float]:
        return self.head_tracker.orientation
