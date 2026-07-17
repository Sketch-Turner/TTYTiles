from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ttytiles.ttytiles import TerminalTiler

import time
import random
import threading
from math import sin, pi

# Global
tt = None

task = None
task_state = 0
task_stats = [(15, 100), (13, 32), (200, 500), (10, 500)]
progress = None

password = None
password_state = 0
password_user = ""
password_pass = ""
password_hash = ""

scan = None
scan_state = 0

tunnel = None
tunnel_state = 0

status = None
status_state = 0

code = None
code_state = 0

# Data
usernames = ["root","admin","administrator","sysadmin","system","superuser","operator","guest","user","test","backup","service","svc_account","daemon","support","manager","maint","devops","deploy","postgres","ubuntu","kali","oracle","mysql","www-data","nginx","apache","nobody","mail","ftp","Administrator","DefaultAccount","Guest","WDAGUtilityAccount","HelpDesk","ITSupport","BackupAdmin"]
passwords = ["password","123456","admin","admin123","root","toor","qwerty","letmein","welcome","guest123","P@ssw0rd!2024","AdminPortal#2025","Winter2026!Secure","RootAccess_99!","CompanyBackup#1","DatabaseAdmin!42","ServerMaintenance2026","SuperUser@Home77","NetworkManager#88","TempAccount_12345","BackupOperator!2026","ServiceAccount$99","ProductionRoot#2025","DevOpsDeploy!321","CloudAdmin_77!","InternalSystem42#","HelpDeskSupport2026!","SecureLogin#8844","AuditUser_2025!","EmergencyAccess$01","SystemAdmin2025!","DefaultPass#7788","ChangeMeNow!456","RemoteAccess2026$","LinuxRoot@123","WindowsAdmin!99","DatabaseRoot#2026","TestAccount_2025","ServiceUser!88","BackupServer$2024"]

vulnerabilities = [("Heartbleed","CVE-2014-0160"),("Shellshock","CVE-2014-6271"),("POODLE","CVE-2014-3566"),("Dirty COW","CVE-2016-5195"),("ImageTragick","CVE-2016-3714"),("EternalBlue","CVE-2017-0144"),("Apache Struts RCE","CVE-2017-5638"),("WannaCry SMB","CVE-2017-0144"),("KRACK","CVE-2017-13077"),("Office Equation Editor","CVE-2017-11882"),("BlueKeep","CVE-2019-0708"),("Citrix ADC Path Traversal","CVE-2019-19781"),("Zerologon","CVE-2020-1472"),("SolarWinds Orion","CVE-2020-10148"),("ProxyLogon","CVE-2021-26855"),("ProxyShell","CVE-2021-34473"),("PrintNightmare","CVE-2021-34527"),("Log4Shell","CVE-2021-44228"),("Log4j DoS","CVE-2021-45105"),("Spring4Shell","CVE-2022-22965"),("Follina","CVE-2022-30190"),("MOVEit Transfer","CVE-2023-34362"),("Citrix Bleed","CVE-2023-4966"),("Ivanti Connect Secure","CVE-2023-46805"),("ScreenConnect","CVE-2024-1709"),("PAN-OS","CVE-2024-3400"),("XZ Utils Backdoor","CVE-2024-3094"),("PHP CGI Argument Injection","CVE-2024-4577"),("regreSSHion","CVE-2024-6387"),("FortiManager","CVE-2024-47575")]

logo = ["████████╗████████╗","╚══██╔══╝╚══██╔══╝","   ██║      ██║   ","   ██║      ██║   ","   ╚═╝      ╚═╝   ","     TTYTILES"]

code_eratosthenes = ['global _start', '', '%define MAX 100', '', 'section .bss', 'sieve   resb MAX + 1', '', 'section .text', '', '_start:', '    mov rcx, MAX + 1', '    lea rdi, [rel sieve]', '.init:', '    mov byte [rdi], 1', '    inc rdi', '    loop .init', '', '    mov byte [sieve], 0', '    mov byte [sieve + 1], 0', '', '    mov rbx, 2', '', '.outer:', '    mov rax, rbx', '    imul rax, rbx', '    cmp rax, MAX', '    jg .done', '', '    cmp byte [sieve + rbx], 0', '    je .next_i', '', '    mov rsi, rax', '', '.inner:', '    cmp rsi, MAX', '    jg .next_i', '', '    mov byte [sieve + rsi], 0', '', '    add rsi, rbx', '    jmp .inner', '', '.next_i:', '    inc rbx', '    jmp .outer', '', '.done:', '    mov eax, 60', '    xor edi, edi', '    syscall']
code_euler = ['global _start', '', '%define MAX 100', '', 'section .bss', 'composite resb MAX + 1', 'primes    resq MAX', 'count     resq 1', '', 'section .text', '', '_start:', '    xor rbx, rbx', '', '.loop_i:', '    inc rbx', '    cmp rbx, MAX', '    jg .done', '', '    cmp byte [composite + rbx], 0', '    jne .skip_prime', '', '    mov rax, [count]', '    mov [primes + rax*8], rbx', '    inc rax', '    mov [count], rax', '', '.skip_prime:', '', '    xor rcx, rcx', '', '.loop_primes:', '    mov rax, [count]', '    cmp rcx, rax', '    jge .loop_i', '', '    mov rdx, [primes + rcx*8]', '', '    mov rax, rbx', '    imul rax, rdx', '', '    cmp rax, MAX', '    jg .loop_i', '', '    mov byte [composite + rax], 1', '', '    mov rax, rbx', '    xor rdx, rdx', '    div rdx', '', '    inc rcx', '    jmp .loop_primes', '', '.done:', '    mov eax, 60', '    xor edi, edi', '    syscall']
code_asm = code_eratosthenes + code_euler

tasks = (("TA0043", "Reconnaissance"), ("TA0042", "Resource Development"), ("TA0001", "Initial Access"), ("TA0002", "Execution"), ("TA0003", "Persistence"), ("TA0004", "Privilege Escalation"), ("TA0005", "Defense Evasion"), ("TA0006", "Credential Access"), ("TA0007", "Discovery"), ("TA0008", "Lateral Movement"), ("TA0009", "Collection"), ("TA0011", "Command and Control"), ("TA0010", "Exfiltration"), ("TA0040", "Impact"))

diagram = ['┌─────────┐       ┌─────────┐       ┌─────────┐','│         │-│#1       │       │         │','│     #1│-│#2=│#3      │','│     #1│=#2│-│         │','└─────────┘       └─────────┘       └─────────┘','    OPS              PIVOT              TGT    ']
phases = ['CONNECTING TO PIVOT','BUILDING EXPLOIT TUNNEL','BUILDING CALLBACK TUNNEL','SENDING EXPLOIT','LISTENING FOR CALLBACK','EXPLOITATION SUCCESSFUL']


def build():
    global tt
    global task
    global progress
    global password
    global scan
    global tunnel
    global status
    global code

    task = tt.addDisplayTile(
        x=1,
        y=1,
        width=tt.cols // 3,
        height=tt.rows // 2 - 2,
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        colorFG=(255,200,0),
        borderFG=(255,100,0)

    )

    progress = tt.addProgressBar(
        x=1,
        y=task.y + task.height - 1,
        width=task.width,
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        max=100,
        barChar="█",
        textOverlay="{PERCENT:.0f}%",
        colorFG=(255,200,0),
        borderFG=(255,100,0)
    )

    password = tt.addDisplayTile(
        x=task.x + task.width,
        y=1,
        width=tt.cols // 3,
        height=tt.rows // 2,
        borderStyle=TerminalTiler.Border.HEAVY_BOX
    )

    code = tt.addDisplayTile(
        x=password.x + password.width,
        y=1,
        width=(tt.cols + 1) - (password.x + password.width),
        height=tt.rows // 2,
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        colorFG=(0,220,255),
        borderFG=(0,120,255)
    )

    tunnel = tt.addDisplayTile(
        x=1,
        y=progress.y + progress.height,
        width=2 * tt.cols // 5,
        height=tt.rows - (progress.y + progress.height),
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        textJust=TerminalTiler.Style.Justify.CENTERED,
        colorFG=(255,0,0)
    )

    status = tt.addDisplayTile(
        x=tunnel.x + tunnel.width,
        y=password.y + password.height,
        width=tt.cols // 5,
        height=tt.rows - (password.y + password.height),
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
    )
    status.set(('\n' * ((status.rows - len(logo)) // 2)) + '\n'.join([(' ' * ((status.cols - max(map(len, [s for s in logo]))) // 2)) + line  for line in logo]))

    scan = tt.addTable(
        x=status.x + status.width,
        y=code.y + code.height,
        width=(tt.cols + 1) - (status.x + status.width),
        height=tt.rows - (code.y + code.height),
        borderStyle=TerminalTiler.Border.HEAVY_BOX,
        textJust=TerminalTiler.Style.Justify.CENTERED
    )

def animate(target, min, max):
    global tt
    while tt.isAlive():
        target()
        time.sleep(random.uniform(min, max))

def update_password():
    global password

    global usernames
    global passwords
    global password_state
    global password_user
    global password_pass
    global password_hash

    if password_state == 0:
        # setup
        password_user = random.choice(usernames)
        password_pass = random.choice(passwords + [password_user])
        password_hash = ''.join(random.choices('0123456789ABCDEF', k=32))

    password.set("\n\n".join([
        "CRACKING PASSWORDS",
        f"USER     : {password_user}",
        f"HASH     : {password_hash}",
        f"STATUS   : Working{'.' * (password_state % 6)}",
        f"PASSWORD : {password_pass[:password_state]}{chr(random.randint(32, 126))}",
        f"           {' '*password_state}^",
    ]))

    if password_state == len(password_pass):
        # reset
        password_state = 0
        password.setColor({
            "TEXT_FG": (0,200,0),
            "HEADER_FG": (0,200,0),
            "BORDER_FG": (0,200,0)
        })
        password.set("\n\n".join([
            "CRACKING PASSWORDS",
            f"USER     : {password_user}",
            f"HASH     : {password_hash}",
            f"STATUS   : <Cracked>",
            f"PASSWORD : {password_pass}"
        ]))
        time.sleep(1.5)
        password.setColor()
    else:
        if random.randint(1,4) == 4 or password_state == 0:
            password_state += 1

def update_scan():
    global scan
    global vulnerabilities
    global scan_state

    # setup
    if scan_state == 0:
        rows = max((scan.height - 4) // 2, 0)
        cols = max((scan.width - 17) // 11, 1)
        ips = [f"{random.choice([i for i in range(1,224) if i not in (10,127,172,192)])}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(rows)]
        scan.load([["TARGET"] + ['\n'.join(code.split('-', 1)) for _, code in random.choices(vulnerabilities, k=cols)]] + [[ip] for ip in ips])

        scan.col_list[0].size = 15
        remaining_width = scan.width - scan.col_list[0].size - (len(scan.col_list) - 1) - 1
        cols = len(scan.col_list) - 1

        for i, col in enumerate(scan.col_list[1:]):
            col.size = remaining_width // cols

        scan.setColor()
        scan.show()

    cols = scan.table_cols - 1
    rows = scan.table_rows - 1

    if scan_state < rows * cols:
        c = (scan_state // rows) + 1
        r = (scan_state % rows) + 1

        if random.randint(1, 10) == 10:
            scan.cells[r][c].setColor({"TEXT_FG":(0,0,255) if "2017-0144" in scan.cells[0][c].text else (0,255,0)})
            scan.set(c, r, "<3" if "2014-0160" in scan.cells[0][c].text else "VULNERABLE")
        else:
            scan.cells[r][c].setColor({"TEXT_FG":(255,50,0)})
            scan.set(c, r, "FAILED")

    if scan_state >= rows * cols:
        scan_state = 0
    else:
        scan_state += 1

def update_status():
    global status
    global logo
    global status_state

    t = status_state * 0.02

    r = int(((sin(t) + 1) / 2) * 255)
    g = int(((sin(t + 2*pi/3) + 1) / 2) * 255)
    b = int(((sin(t + 4*pi/3) + 1) / 2) * 255)

    status.setColor({"TEXT_FG": (r, g, b)})

    status_state += 1

def update_code():
    global code
    global code_state
    global code_asm

    code.update((code_eratosthenes + code_euler)[code_state])

    code_state += 1
    code_state %= len(code_asm)

def update_task():
    global task
    global tasks
    global task_state
    global task_stats
    global progress

    # setup
    if task_state % 100 == 0:
        progress.reset()
        progress.show()

    progress.update()
    code, name = tasks[task_state // 100]
    cpu, cpu_max = task_stats[0]
    mem, mem_max = task_stats[1]
    up, up_max = task_stats[2]
    down, down_max = task_stats[3]
    cpu = min(cpu_max, max(0, 0.9 * cpu + 0.1 * random.randint(0, cpu_max)))
    mem = min(mem_max, max(0, 0.9 * mem + 0.1 * random.randint(0, mem_max)))
    up = min(up_max, max(0, 0.9 * up + 0.1 * random.randint(0, up_max)))
    down = min(down_max, max(0, 0.9 * down + 0.1 * random.randint(0, down_max)))
    task_stats = [(cpu, cpu_max),(mem, mem_max),(up, up_max),(down, down_max)]
    c = f"CPU:      {cpu:2.0f}%"
    m = f"MEM:      {mem:2.0f}/{mem_max:2.0f} GB ({(100*mem/mem_max):2.0f}%)"
    u = f"UPLOAD:   {up:5.2f} Kbps"
    d = f"DOWNLOAD: {down:5.2f} Kbps"
    max_len = max(map(len, [c, m, u, d]))
    w = task.cols - (max_len + 3)

    task.set("\n".join([
        f"{c}{' ' * (max_len - len(c))} |{'█' * int((w * cpu) / cpu_max)}{' ' * (w - int((w * cpu) / cpu_max))}|\n",
        f"{m}{' ' * (max_len - len(m))} |{'█' * int((w * mem) / mem_max)}{' ' * (w - int((w * mem) / mem_max))}|\n",
        f"{u}{' ' * (max_len - len(u))} |{'█' * int((w * up) / up_max)}{' ' * (w - int((w * up) / up_max))}|\n",
        f"{d}{' ' * (max_len - len(d))} |{'█' * int((w * down) / down_max)}{' ' * (w - int((w * down) / down_max))}|\n\n",
        "TASK: " + name.upper(),
        "CODE: " + code
    ]))

    task_state += 1

    # reset
    if task_state >= 100 * len(tasks):
        task_state = 0

def update_tunnel():
    global tunnel
    global tunnel_state
    global diagram
    global phases

    arrow1 = f"{(('-' * min(tunnel_state, 6)) + ('>' if tunnel_state >= 6 else ' ')):<7}"
    port1 = f"{'22' if tunnel_state >= 7 else '  '}"
    phase = 0

    port2_2 = f"{'1337' if tunnel_state >= 8 else '    '}"
    arrow2_1 = f"{(('=' * min(tunnel_state - 8, 11)) + ('>' if tunnel_state >= 20 else ' ')):<12}"
    arrow2_1 = arrow2_1[:5] + ('│' if tunnel_state < 14 else '=') + arrow2_1[5:]
    port2_3 = f"{'445' if tunnel_state >= 22 else '   '}"
    if tunnel_state >= 8:
        phase = 1

    port3_2 = f"{'4444' if tunnel_state >= 23 else '    '}"
    arrow3_1 = f"{(('<' if tunnel_state >= 35 else ' ') + ('=' * min(tunnel_state - 23, 11))):>12}"
    arrow3_1 = arrow3_1[:7] + ('│' if tunnel_state < 28 else '=') + arrow3_1[7:]
    port3_1 = f"{'4444' if tunnel_state >= 36 else '    '}"
    if tunnel_state >= 23:
        phase = 2

    port2_1 = f"{'1337' if tunnel_state >= 37 else '    '}"
    arrow2_2 = f"{(('-' * min(tunnel_state - 37, 6)) + ('>' if tunnel_state >= 43 else ' ')):<7}"
    if tunnel_state >= 37:
        phase = 3

    arrow3_2 = f"{(('<' if tunnel_state >= 50 else ' ') + ('-' * min(tunnel_state - 43, 6))):>7}"
    if tunnel_state >= 43:
        phase = 4

    if tunnel_state >= 50:
        phase = 5

    tunnel.set('\n'.join([
        "",
        diagram[0],
        diagram[1].replace('-', arrow1).replace('#1', port1),
        diagram[2].replace('=', arrow2_1).replace('-', arrow2_2).replace('#1', port2_1).replace('#2', port2_2).replace('#3', port2_3),
        diagram[3].replace('=', arrow3_1).replace('-', arrow3_2).replace('#1', port3_1).replace('#2', port3_2),
        diagram[4],
        diagram[5],
        "\n",
        phases[phase]
    ]))

    tunnel_state += 1
    tunnel_state %= 60

if __name__ == "__main__":
    tt = TerminalTiler()
    build()

    threading.Thread(target=animate, args=(update_password, 0.03, 0.08), daemon=True).start()
    threading.Thread(target=animate, args=(update_scan, 0.15, 0.45), daemon=True).start()
    threading.Thread(target=animate, args=(update_status, 0.01, 0.01), daemon=True).start()
    threading.Thread(target=animate, args=(update_code, 0.05, 0.05), daemon=True).start()
    threading.Thread(target=animate, args=(update_task, 0.05, 0.05), daemon=True).start()
    threading.Thread(target=animate, args=(update_tunnel, 0.25, 0.25), daemon=True).start()

    tt.waitForKey(tt.Keyboard.KEY_ANY)
    tt.close()