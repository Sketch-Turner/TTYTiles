from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import time
import random

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ttytiles import *

TARGET = "scanme.nmap.org"
PORTS = [21, 22, 23, 25, 53, 80, 110, 111, 135, 137,
        138, 139, 143, 161, 389, 443, 445, 465, 500, 512,
        513, 514, 515, 587, 593, 631, 636, 873, 990, 993,
        995, 1080, 1194, 1352, 1433, 1434, 1521, 1723, 1883, 2049,
        2181, 2375, 2376, 2483, 2484, 2638, 27017, 3000, 3001, 3005,
        3030, 3050, 3128, 3260, 3306, 3389, 3690, 3724, 4369, 4444,
        4500, 4567, 4786, 5000, 5001, 5060, 5080, 5222, 5223, 5432,
        5433, 5555, 5601, 5631, 5800, 5900, 5938, 5984, 6000, 6001,
        6379, 6443, 6667, 6881, 7001, 7002, 7077, 7080, 7180, 7547,
        8000, 8008, 8080, 8081, 8443, 8888, 9000, 9042, 9090, 9200,
        9300, 9929, 10000, 11211, 15672, 27015, 27036, 31337]
TIMEOUT = 2
JITTER_MIN = 0.5
JITTER_MAX = 1.5
THREADS = 10

def grab_banner(host, port):
    try:
        # FTP
        if port == 21:
            s = socket.socket()
            s.settimeout(1)
            s.connect((host, port))
            return s.recv(1024).decode(errors="ignore").strip()

        # SSH
        if port == 22:
            s = socket.socket()
            s.settimeout(1)
            s.connect((host, port))
            return s.recv(1024).decode(errors="ignore").strip()

        # SMTP
        if port in (25, 587):
            s = socket.socket()
            s.settimeout(1)
            s.connect((host, port))
            return s.recv(1024).decode(errors="ignore").strip()

        # HTTP
        if port in (80, 8000, 8080):
            s = socket.socket()
            s.settimeout(1)
            s.connect((host, port))

            req = f"HEAD / HTTP/1.0\r\nHost: {host}\r\n\r\n"
            s.sendall(req.encode())
            response = s.recv(1024).decode(errors="ignore").strip().split('\r\n')
            if len(response) > 2:
                return "\n        ".join([response[0].strip(), "".join(response[2].strip().split()[1:])])

    except Exception:
        return None

def scan_port(host, port, open_ports, closed_ports):
    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    time.sleep(jitter)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)

        result = sock.connect_ex((host, port))

        if result == 0:
            banner = grab_banner(host, port)
            if banner:
                open_ports.update(f"{port:5} : open\n        {banner}")
            else:
                open_ports.update(f"{port:5} : open")

        else:
            closed_ports.update(f"{port:5} : closed")

    except Exception:
        pass

    finally:
        sock.close()

    return port

if __name__ == "__main__":
    tt = TerminalTiler()
    info = tt.addDisplayTile(x=1,
                             y=1,
                             width=tt.cols,
                             height=5,
                             canFocus=False)

    open_ports = tt.addDisplayTile(x=1,
                                   y=9,
                                   width=tt.cols // 2,
                                   height=tt.rows // 2,
                                   sizeMode=DisplayTile.SIZE_SCROLLING,
                                   borderStyle=Border.HEAVY_BOX,
                                   headerBorder=True,
                                   headerLines=1)

    closed_ports = tt.addDisplayTile(x=tt.cols // 2 + 1,
                                     y=9,
                                     width=tt.cols // 2 - 1,
                                     height=tt.rows // 2,
                                     sizeMode=DisplayTile.SIZE_SCROLLING,
                                     borderStyle=Border.HEAVY_BOX,
                                     headerBorder=True,
                                     headerLines=1)

    status = tt.addDisplayTile(x=1,
                               y=open_ports.y + open_ports.height + 2,
                               width=tt.cols,
                               height=1,
                               canFocus=False)

    progress = tt.addProgressBar(max=len(PORTS),
                                 barChar='=',
                                 barLeft="[",
                                 barRight="]",
                                 x=1,
                                 y=7,
                                 width=open_ports.width + closed_ports.width)

    progress.colors["TEXT_FG"] = (255, 0, 0)
    progress.textOverlay = "{PERCENT:.2f}%"
    progress.textRight = " {VALUE}/{MAX}"


    tt.stdout_FDI.default_target = info.update
    print(f"Target  : {TARGET}")
    print(f"Ports   : {len(PORTS)}")
    print(f"Timeout : {TIMEOUT} seconds")
    print(f"Jitter  : {JITTER_MIN} - {JITTER_MAX} seconds")
    print(f"Threads : {THREADS}")

    open_ports.updateHeader("Open")
    open_ports.colors["BORDER_FG_F"] = (52, 152, 219)
    closed_ports.updateHeader("Closed")
    closed_ports.colors["BORDER_FG_F"] = (52, 152, 219)

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(scan_port, TARGET, port, open_ports, closed_ports) for port in PORTS]

        for future in as_completed(futures):
            progress.textLeft = f"Scanning: {future.result():5} "
            progress.update(1)

    status.colors["TEXT_FG"] = (46, 204, 113)
    status.update("Scan Complete - Press Ctrl+X to exit.")

    tt.waitForKey(Keyboard.KEY_CTRL_X)