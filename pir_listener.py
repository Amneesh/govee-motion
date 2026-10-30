import sys
import time
import json
import os
import threading
import uuid
import urllib.request
import urllib.error

# Tuya Local Key container helpers
sys.path.insert(0, "/app")

from tuya_devices import load_session, build_manager, qr_login, save_session
from tuya_sharing import SharingDeviceListener


# =========================================================
# CONFIG
# =========================================================

SESSION_FILE = "/data/session.json"

# Energizer PIR
SENSOR_ID = "eb2726d9123791da84suus"

# Govee - Living room arc lamp
GOVEE_SKU = "H6008"
GOVEE_DEVICE = "06:82:5C:E7:53:64:91:06"

# Govee key MUST come from environment variable
GOVEE_API_KEY = os.environ.get("GOVEE_API_KEY")

# 2 minutes after last motion
OFF_DELAY = 10

GOVEE_URL = "https://openapi.api.govee.com/router/api/v1/device/control"

off_timer = None
light_assumed_on = False
timer_lock = threading.Lock()


# =========================================================
# GOVEE CLOUD API
# =========================================================

def set_govee_power(value):
    global light_assumed_on

    if not GOVEE_API_KEY:
        print("❌ GOVEE_API_KEY is missing", flush=True)
        return False

    payload = {
        "requestId": str(uuid.uuid4()),
        "payload": {
            "sku": GOVEE_SKU,
            "device": GOVEE_DEVICE,
            "capability": {
                "type": "devices.capabilities.on_off",
                "instance": "powerSwitch",
                "value": value
            }
        }
    }

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        GOVEE_URL,
        data=body,
        method="POST",
        headers={
            "Govee-API-Key": GOVEE_API_KEY,
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = response.read().decode("utf-8")

        print(f"Govee response: {result}", flush=True)

        light_assumed_on = value == 1

        return True

    except urllib.error.HTTPError as error:
        print(
            f"❌ Govee HTTP error {error.code}: "
            f"{error.read().decode('utf-8')}",
            flush=True
        )

    except Exception as error:
        print(f"❌ Govee API error: {error}", flush=True)

    return False


def turn_govee_on():
    global light_assumed_on

    # Don't repeatedly send ON commands for every PIR update
    if light_assumed_on:
        print("💡 Light already ON", flush=True)
        return

    print("💡 Turning Govee ON...", flush=True)

    if set_govee_power(1):
        print("✅ GOVEE BULB ON", flush=True)


def turn_govee_off():
    global light_assumed_on

    print("🌙 2 minutes without new motion", flush=True)
    print("💡 Turning Govee OFF...", flush=True)

    if set_govee_power(0):
        print("✅ GOVEE BULB OFF", flush=True)


# =========================================================
# AUTO-OFF TIMER
# =========================================================

def reset_off_timer():
    global off_timer

    with timer_lock:

        if off_timer is not None:
            off_timer.cancel()

        off_timer = threading.Timer(
            OFF_DELAY,
            turn_govee_off
        )

        off_timer.daemon = True
        off_timer.start()

    print(
        f"⏱️ OFF timer reset to {OFF_DELAY} seconds",
        flush=True
    )


# =========================================================
# TUYA MOTION LISTENER
# =========================================================

class MotionListener(SharingDeviceListener):

    def update_device(self, device, *args):

        if device.id != SENSOR_ID:
            return

        pir = device.status.get("pir")

        print(f"PIR: {pir}", flush=True)

        if pir == "pir":

            print("🚨 MOTION DETECTED", flush=True)

            turn_govee_on()

            # Every motion resets countdown
            reset_off_timer()

        elif pir == "none":

            print("✅ No motion", flush=True)


    def add_device(self, device):
        pass


    def remove_device(self, device_id):
        pass


# =========================================================
# TUYA CONNECTION
# =========================================================

def connect_tuya():

    session = load_session(SESSION_FILE)

    if session:

        try:

            manager = build_manager(
                session,
                SESSION_FILE
            )

            manager.update_device_cache()

            return manager

        except Exception as error:

            print(
                f"Saved Tuya session invalid: {error}",
                flush=True
            )

            print(
                "Tuya QR authentication required.",
                flush=True
            )


    session = qr_login(
        None,
        "smartlife",
        "/work/tuya-login-qr.png"
    )

    save_session(
        SESSION_FILE,
        session
    )

    manager = build_manager(
        session,
        SESSION_FILE
    )

    manager.update_device_cache()

    return manager


# =========================================================
# START
# =========================================================

print("Starting Energizer → Govee automation...\n")

manager = connect_tuya()

sensor = manager.device_map.get(SENSOR_ID)

if not sensor:
    raise SystemExit(
        "❌ Energizer Motion Sensor not found"
    )

print(
    f"✅ Sensor found: {sensor.name}",
    flush=True
)

print(
    f"Current PIR status: {sensor.status}",
    flush=True
)


# Required for Tuya MQTT updates
for device in manager.device_map.values():
    device.set_up = True


listener = MotionListener()

manager.add_device_listener(listener)

manager.refresh_mq()


print("\n🟢 AUTOMATION RUNNING")
print("Motion → Govee Cloud → Light ON")
print(f"No new motion for {OFF_DELAY} seconds → Light OFF\n")


# =========================================================
# KEEP RUNNING
# =========================================================

try:

    while True:
        time.sleep(60)


except KeyboardInterrupt:

    print("\n🛑 Stopping automation...", flush=True)

    if off_timer is not None:
        off_timer.cancel()

    if manager.mq:
        manager.mq.stop()