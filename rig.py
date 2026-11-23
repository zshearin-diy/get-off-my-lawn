"""The link to the servo board. `move()` and `fire()` return once the action is done.

Wire format (see arduino/pan_tilt/pan_tilt.ino):
    host  -> board   "P090T095#7\\n"     "F#8\\n"
    board -> host    "moved 90 95 #7"    "fired #8"
The board replies only when the action has finished, so waiting for the reply
is waiting for the rig to stop. The "#<id>" lets a reply be matched to the
command that asked for it, so a late reply to an earlier command is never
mistaken for the current one.

Nothing here knows about servos: any board that speaks this protocol -- and
replies when its motors have stopped -- works unchanged.
"""

import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # the program still runs (and prints) without a board attached
    serial = None

BOARD_PORT_TAGS = ("usbmodem", "usbserial", "ttyACM", "ttyUSB")


class Rig:
    def __init__(self, port, baud, timeout):
        self._timeout = timeout
        self._next_id = 0
        self._board = serial.Serial(port, baud, timeout=0.1)
        # Opening the port resets most Arduinos; commands sent during the
        # bootloader window are lost. The sketch prints "ready" once it runs.
        if not self._wait_for(lambda line: line == "ready", timeout=3.0):
            print("[board]   no 'ready' from board, continuing anyway")
        self._board.reset_input_buffer()
        print(f"[board]   connected on {port}")

    def move(self, pan, tilt):
        print(f"[rig]     move to pan {pan:3d}  tilt {tilt:3d}")
        return self._command(f"P{pan:03d}T{tilt:03d}")

    def fire(self):
        print("[fire]    firing")
        return self._command("F")

    def close(self):
        self._board.close()

    def _command(self, text):
        """Send one command and block until the board reports it finished."""
        self._next_id += 1
        tag = f"#{self._next_id}"
        started = time.monotonic()
        self._board.write(f"{text}{tag}\n".encode())
        if self._wait_for(lambda line: line.endswith(tag), self._timeout):
            print(f"[rig]     done in {time.monotonic() - started:.2f}s")
            return True
        print(f"[rig]     no reply to {text} within {self._timeout}s, continuing")
        return False

    def _wait_for(self, matches, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._board.readline().decode(errors="replace").strip()
            if not line:
                continue  # readline timed out; check the deadline again
            if matches(line):
                return True
            if line.startswith("error"):
                print(f"[board]   {line}")
        return False


class PrintRig:
    """Stand-in when no board is attached: prints commands, finishes instantly."""

    def move(self, pan, tilt):
        print(f"[rig]     move to pan {pan:3d}  tilt {tilt:3d} (no board)")
        return True

    def fire(self):
        print("[fire]    no board, solenoid not fired")
        return True

    def close(self):
        pass


def find_port():
    """First USB serial port that looks like a microcontroller."""
    for port in list_ports.comports():
        if any(tag in port.device for tag in BOARD_PORT_TAGS):
            return port.device
    return None


def open_rig(port, baud, timeout):
    """Connect to the board, or fall back to a PrintRig so vision still runs."""
    if serial is None:
        print("[board]   pyserial not installed, printing commands only")
        return PrintRig()
    port = port or find_port()
    if port is None:
        print("[board]   no serial port found, printing commands only")
        return PrintRig()
    try:
        return Rig(port, baud, timeout)
    except OSError as error:
        print(f"[board]   cannot open {port} ({error}), printing commands only")
        return PrintRig()
