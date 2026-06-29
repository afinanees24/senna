#!/bin/bash
# Downloads ML models for senna_audio (Piper TTS + Vosk speech recognition).
# Models are excluded from git due to size. Run this once after cloning.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="${SCRIPT_DIR}/../src/senna_audio/models"

echo "==> Downloading Piper TTS voice (en_US-lessac-medium)..."
mkdir -p "${MODELS_DIR}/piper"
cd "${MODELS_DIR}/piper"
if [ ! -f "en_US-lessac-medium.onnx" ]; then
    wget -q --show-progress \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    wget -q --show-progress \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
fi

echo "==> Downloading Vosk speech recognition model (small-en-us-0.15)..."
mkdir -p "${MODELS_DIR}/vosk"
cd "${MODELS_DIR}/vosk"
if [ ! -d "vosk-model-small-en-us-0.15" ]; then
    wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
fi

echo "==> Done. Models in ${MODELS_DIR}"
