import socket
import time

UDP_PORT = 4210
IDLE_LIMIT = 5     # stop after 5s of silence when NO device is sending
SWEEP_GRACE = 9    # during a sweep the ESP32 is silent ~5s while capturing — don't cut it off

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT))
sock.settimeout(1.0)   # check once a second

print(f"Listening on port {UDP_PORT}...")
print("Waiting for ResoScan data (auto-stops after 5s of silence)...\n")

last_data = time.time()
sweep_active = False
count = 0

with open("resoscan_data.csv", "w") as f:
    f.write("N,Z\n")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            last_data = time.time()
            text = data.decode("utf-8", errors="ignore")
            print(text, end="")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # track whether we're mid-sweep (device goes silent while capturing)
                if any(m in line for m in ("MEASUREMENT START", "starting chirp", "Chirp:", "Duration:")):
                    sweep_active = True
                elif "Samples:" in line or "[DONE]" in line:
                    sweep_active = False
                # save real data lines (N,Z format)
                elif "," in line and line[0].isdigit():
                    f.write(line + "\n")
                    f.flush()
                    count += 1
        except socket.timeout:
            limit = SWEEP_GRACE if sweep_active else IDLE_LIMIT
            if time.time() - last_data > limit:
                print(f"\nNo data for {limit}s — stopping. {count} samples saved to resoscan_data.csv")
                break
        except KeyboardInterrupt:
            print(f"\nStopped. {count} samples saved to resoscan_data.csv")
            break
