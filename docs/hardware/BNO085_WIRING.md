# BNO085 IMU Wiring (Pi 5 + Adafruit #4754 Breakout)

UART-RVC at 100 Hz on `/dev/serial0`. **Do not switch to I2C** — there's a documented Pi 5 + BNO085 clock-stretching incompatibility (chip ACKs at 0x4a, then library hangs on `i2c.readinto`). UART-RVC works and ships.

## Row convention warning

In this project's physical convention, "top row" means the row closer to the PCB center — the **even-numbered** Pi pins (2, 4, 6, 8, 10...). "Bottom row" is the outer row — the **odd-numbered** pins (1, 3, 5, 7, 9...). This is inverted from Pi documentation. **Verify with a multimeter before any wiring change**: pin 2 reads 5 V, pin 1 reads 3.3 V, both at the same end of the header.

## Working wiring

| Chip pin | Physical position      | Real Pi pin | Function           |
|----------|------------------------|-------------|--------------------|
| VIN      | top row, 2nd from L    | pin 4       | 5 V                |
| GND      | top row, 3rd from L    | pin 6       | GND                |
| SDA      | top row, 5th from L    | pin 10      | GPIO15 / UART RXD  |
| P0       | bottom row, 1st from L | pin 1       | 3.3 V (mode select)|

All other chip pins (SCL, P1, RST, INT, BT, DI, CS) are unconnected.

## Why P0 to 3.3 V?

P0 selects the chip's interface mode at power-up. Floating low (default) = I2C. Pulled high at boot = UART-RVC. The chip only samples this pin at power-up, so it must be wired before the chip sees power.

## Verify

```python
import serial
from adafruit_bno08x_rvc import BNO08x_RVC
uart = serial.Serial("/dev/serial0", 115200)
rvc = BNO08x_RVC(uart)
print(rvc.heading)  # (yaw, pitch, roll, ax, ay, az)
```

Sign conventions (chip body frame, empirically verified):

- `+pitch` → chip +Y tilts up
- `+roll`  → chip +X tilts down
- `yaw`    → about chip +Z; CW/CCW sign TBD until mounted

## Pi config

Working `config.txt` snapshot at `docs/hardware/config.txt.working`. Critical: `enable_uart=1`, `dtparam=i2c_arm=on`. Serial console must NOT be on UART (`cmdline.txt` should say `console=tty1`, not `console=serial0`), and `serial-getty@ttyAMA0.service` must be disabled.
