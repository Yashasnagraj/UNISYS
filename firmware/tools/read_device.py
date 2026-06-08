"""
ResoScan device serial reader.

Auto-detects the CP2102 USB-to-UART bridge (ignores Bluetooth COM ports),
opens it at 115200 baud, and streams whatever the firmware prints.

Usage:
    python read_device.py            # auto-detect port, 115200 baud
    python read_device.py COM5       # force a port
    python read_device.py COM5 9600  # force port + baud

Ctrl+C to stop.
"""
import sys
import time
import serial
from serial.tools import list_ports

DEFAULT_BAUD = 115200


def find_device_port():
    """Return the COM port of the CP210x bridge, or None.

    Silicon Labs CP2102 = VID 0x10C4, PID 0xEA60. We match on that so we
    never accidentally grab a Bluetooth 'Standard Serial over Bluetooth' port.
    """
    candidates = []
    for p in list_ports.comports():
        vidpid = ((p.vid or 0), (p.pid or 0))
        desc = (p.description or "").lower()
        if vidpid == (0x10C4, 0xEA60) or "cp210" in desc or "uart bridge" in desc:
            candidates.append(p.device)
    return candidates[0] if candidates else None


def list_all_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("  (no serial ports found at all)")
        return
    for p in ports:
        vid = f"{p.vid:04X}" if p.vid else "----"
        pid = f"{p.pid:04X}" if p.pid else "----"
        print(f"  {p.device:6}  VID:{vid} PID:{pid}  {p.description}")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD

    if port is None:
        port = find_device_port()
        if port is None:
            print("[!] ResoScan device (CP2102) not found.")
            print("    Available serial ports:")
            list_all_ports()
            print("\n    If you see NOTHING from Silicon Labs / CP210x above,")
            print("    the CP210x driver is not installed yet. Install it first.")
            sys.exit(1)
        print(f"[+] Auto-detected ResoScan device on {port}")

    print(f"[+] Opening {port} @ {baud} baud ... (Ctrl+C to stop)\n")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=1)
    except serial.SerialException as e:
        print(f"[!] Could not open {port}: {e}")
        sys.exit(1)

    ser.reset_input_buffer()
    last_data = time.time()
    try:
        while True:
            line = ser.readline()
            if line:
                text = line.decode("utf-8", errors="ignore").rstrip()
                if text:
                    print(text)
                    last_data = time.time()
            elif time.time() - last_data > 5:
                print("[..] no data for 5 s (device idle or wrong baud?)")
                last_data = time.time()
    except KeyboardInterrupt:
        print("\n[+] Stopped by user.")
    finally:
        if ser.is_open:
            ser.close()
            print("[+] Port closed.")


if __name__ == "__main__":
    main()
