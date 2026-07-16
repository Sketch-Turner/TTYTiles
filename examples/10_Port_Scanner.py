from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import time
import random

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ttytiles.ttytiles import TerminalTiler

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
                open_ports.update(f"{port:5}\n        {banner}")
            else:
                open_ports.update(f"{port:5}")

        else:
            closed_ports.update(f"{port:5}")

    except Exception:
        pass

    finally:
        sock.close()

    return port

if __name__ == "__main__":
    # Initialize TerminalTiler.
    tt = TerminalTiler()

    # Create a non-focusable information panel.
    info = tt.addDisplayTile(
        x=1,
        y=1,
        width=tt.cols,
        height=5,
        canFocus=False
    )

    # Create display tile for open ports.
    open_ports = tt.addDisplayTile(
        x=1,
        y=9,
        width=tt.cols // 2,
        height=tt.rows // 2,
        sizeMode=TerminalTiler.Style.Size.SCROLLING,
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        headerLines=1,
        headerTextJust=TerminalTiler.Style.Justify.CENTERED
    )

    # Create display tile for closed ports.
    closed_ports = tt.addDisplayTile(
        x=tt.cols // 2 + 1,
        y=9,
        width=tt.cols // 2 - 1,
        height=tt.rows // 2,
        sizeMode=TerminalTiler.Style.Size.SCROLLING,
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        headerLines=1,
        headerTextJust=TerminalTiler.Style.Justify.CENTERED
    )

    # Create a status display at the bottom of the interface.
    status = tt.addDisplayTile(
        x=1,
        y=open_ports.y + open_ports.height + 2,
        width=tt.cols,
        height=3,
        canFocus=False
    )

    # Create a progress bar for tracking completed port scans.
    progress = tt.addProgressBar(
        max=len(PORTS),
        barChar='=',
        textRight="] {VALUE}/{MAX}",
        textOverlay="{PERCENT:.2f}%",
        x=1,
        y=7,
        width=open_ports.width + closed_ports.width
    )

    # Display scan configuration information.
    info.update(f"Target  : {TARGET}")
    info.update(f"Ports   : {len(PORTS)}")
    info.update(f"Timeout : {TIMEOUT} seconds")
    info.update(f"Jitter  : {JITTER_MIN} - {JITTER_MAX} seconds")
    info.update(f"Threads : {THREADS}")

    # Configure port result panels.
    open_ports.header.set("Open")
    open_ports.setColor({"BORDER_FG_F": (52, 152, 219)})

    closed_ports.header.set("Closed")
    closed_ports.setColor({"BORDER_FG_F": (52, 152, 219)})

    # Display the progress bar.
    progress.show()

    # Run port scans concurrently using a thread pool.
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(
                scan_port,
                TARGET,
                port,
                open_ports,
                closed_ports
            )
            for port in PORTS
        ]

        # Update progress as each scan completes.
        for future in as_completed(futures):
            result = future.result()

            # Show the most recently completed port.
            progress.textLeft = f"Scanning Port: {result:5} ["
            progress.update(1)

    # Display completion message.
    status.setColor({"TEXT_FG": (46, 204, 113)})
    status.set(
        "Scan Complete!\n"
        "Press TAB to select Display.\n"
        "Press ESC to exit."
    )

    # Wait for user confirmation before closing.
    tt.waitForKey(TerminalTiler.Keyboard.KEY_ESCAPE)

    # Shutdown TerminalTiler cleanly.
    tt.close()