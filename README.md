# SENNA

Assistive smart glasses for blind and visually impaired users. SENNA combines indoor wayfinding (world-anchored spatial audio tone-following), scene description, and voice interaction in a wearable Raspberry Pi 5 + Hailo NPU platform.

## Team

- **Afin** — hardware integration, Pi runtime, state machine, pathfinding, `senna_audio` package
- **Noman** — iOS LiDAR scanner app (produces `.senna` venue files, uploads to Supabase)
- **Asdaq** — `senna_vision` package (YOLO on Hailo-8L, MiDaS depth estimation, ORB visual anchoring)

## Hardware

- Raspberry Pi 5 8GB + AI HAT+ (Hailo-8L NPU on PCIe)
- IMX500 AI Camera
- BNO085 9-DOF IMU (UART-RVC mode on `/dev/serial0`)
- weariQ-01 Bluetooth audio glasses (HSP/HFP — for TTS prompts only)
- USB-C audio DAC + wired stereo headphones (required for HRTF spatial audio)

## Repository Layout
## Getting Started

### Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS Bookworm (64-bit)
- Python 3.13 in a virtual environment
- All hardware listed above connected

### Clone and Set Up

```bash
git clone git@github.com:afinanees24/senna.git
cd senna

# Create Python virtual environment
python3 -m venv ~/bno-test
source ~/bno-test/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Download ML models (Piper TTS + Vosk speech recognition, ~110MB total)
./scripts/setup_models.sh
```

### Pi Configuration

Ensure `/boot/firmware/config.txt` contains:
**Do NOT add `dtoverlay=disable-bt`** — it disables onboard Bluetooth (which is needed for audio output via Bluetooth glasses).

### BNO085 Wiring (UART-RVC mode)

The IMU must be wired for UART-RVC mode (P0 pulled high at power-up):

| BNO085 pin | Pi pin | Function |
|---|---|---|
| VIN | Pin 4 | 5V |
| GND | Pin 6 | GND |
| SDA | Pin 10 | GPIO15 / UART RX |
| P0 | Pin 1 | 3.3V (mode select) |

I2C is not supported on this chip + Pi 5 combination due to clock-stretching incompatibility.

## Usage

### Verify IMU streaming

```bash
source ~/bno-test/bin/activate
python3 -c "
import serial, time
uart = serial.Serial('/dev/serial0', 115200, timeout=0.5)
start = time.time(); total = 0
while time.time() - start < 3:
    chunk = uart.read(64)
    if chunk: total += len(chunk)
print(f'Got {total} bytes in 3 sec (expect ~5760)')
"
```

### Run end-to-end audio system demo

```bash
source ~/bno-test/bin/activate
python3 << 'PY'
import sys
sys.path.insert(0, "src")
from senna_audio import AudioSystem

audio = AudioSystem(audio_sink="bluez_output.41_42_FF_F3_6D_74.1")
audio.start()
audio.speak_prompt("Welcome to SENNA. Where would you like to go?")
dest = audio.listen_for_destination(timeout_s=10.0)
audio.speak_prompt(f"Going to {dest}")
audio.stop()
PY
```

### Venue identification from WiFi fingerprint

```bash
sudo python3 src/senna_audio/venue_detector.py
```

## File Format: `.senna`

Venue files are ZIP archives containing:

- `manifest.json` — venue name, grid dimensions, resolution
- `grid.npz` — 2D occupancy grid (0=free, 1=wall, 2=unknown)
- `destinations.json` — name → (x, z) coordinate dict
- `visual_anchors.bin` — ORB feature descriptors (48-byte records)
- `wifi_fingerprint.json` — BSSID → average RSSI

Coordinate convention: x = right, z = forward, y = up. Grid indexed `grid[y, x]`.

## Project Status

- ✅ BNO085 IMU streaming (100 Hz UART-RVC, hardware-soldered, permanent)
- ✅ senna_audio MVP (HeadTracker, TTS via Piper, Voice via Vosk, AudioSystem facade)
- ✅ WiFi venue fingerprinting (cosine similarity matching)
- ✅ Bluetooth audio output to weariQ-01 glasses
- 🔄 A* pathfinding (in progress)
- 🔄 senna_vision integration (Asdaq)
- ⏳ HRTF spatial audio (blocked on USB DAC arrival)
- ⏳ GPS integration (Adafruit Mini GPS PA1010D ordered)
- ⏳ Brain orchestration
- ⏳ First real walk in a scanned venue (Phase 17 milestone)

## License

Private — UT Dallas SENNA project.
