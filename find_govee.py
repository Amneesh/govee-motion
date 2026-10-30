import socket
import json
import time

MCAST_ADDR = "239.255.255.250"
SCAN_PORT = 4001
LISTEN_PORT = 4002

msg = {
    "msg": {
        "cmd": "scan",
        "data": {
            "account_topic": "reserve"
        }
    }
}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", LISTEN_PORT))
sock.settimeout(5)

sock.sendto(
    json.dumps(msg).encode(),
    (MCAST_ADDR, SCAN_PORT)
)

print("Scanning for Govee devices...")

end = time.time() + 5

while time.time() < end:
    try:
        data, addr = sock.recvfrom(4096)
        print(data.decode())
    except socket.timeout:
        break
