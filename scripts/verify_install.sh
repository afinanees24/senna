#!/bin/bash
# Verify SENNA Pi installation

echo "=== SENNA Pi Install Verification ==="

FAILED=0

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo "  [OK]  $1"
    else
        echo "  [FAIL] $1"
        FAILED=1
    fi
}

check "Pi 5 detected" "grep -q 'Raspberry Pi 5' /proc/device-tree/model"
check "I2C enabled" "ls /dev/i2c-* 2>/dev/null | grep -q i2c"
check "SPI enabled" "ls /dev/spidev* 2>/dev/null | grep -q spi"
check "UART enabled (/dev/ttyAMA0)" "ls /dev/ttyAMA0"
check "Hailo runtime detected" "hailortcli fw-control identify"
check "AI Camera detected" "rpicam-hello --list-cameras 2>&1 | grep -qi imx500"
check "I2S audio device present" "aplay -l 2>&1 | grep -qi 'googlevoicehat\|bcm2835'"
check "Python venv exists" "[ -d /home/pi/senna-env ]"
check "SENNA project tree exists" "[ -d /home/pi/senna/src ]"
check "Vosk model downloaded" "[ -d /home/pi/senna/models/vosk-en-small ]"
check "WiFi power save disabled" "iw dev wlan0 get power_save | grep -qi 'off'"

echo ""
if [ $FAILED -eq 0 ]; then
    echo "All checks passed. SENNA Pi is ready for Step 2."
    exit 0
else
    echo "Some checks failed. Review above before proceeding."
    echo "Note: Hailo and IMX500 will FAIL until the AI HAT and camera are wired"
    echo "      and the Pi has been rebooted after running setup."
    exit 1
fi
