#!/usr/bin/env python3

import RPi.GPIO as GPIO
import subprocess
import time
import threading
import logging
import sys

# Configure logging for systemd/journalctl
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ------------------------
# Pin configuration
# ------------------------
BUTTON_PIN = 10   # BCM GPIO10 → physical pin 19
LED_PIN = 12       # BCM GPIO5  → physical pin 29

# Thresholds (blinks = seconds)
CLIENT_MODE_BLINKS = 5      # 5 blinks = 5 seconds
AP_MODE_BLINKS = 10         # 10 blinks = 10 seconds
REBOOT_BLINKS = 15          # 15+ blinks = 15+ seconds

COOLDOWN_SECONDS = 2
BLINK_INTERVAL = 0.5        # Each blink on/off = 0.5s, so 1 second per complete blink cycle

# WiFi status blinking
WIFI_CHECK_INTERVAL = 3     # Check WiFi status every 3 seconds
WIFI_BLINK_DURATION = 0.2   # Quick blink duration for WiFi status
WIFI_BLINK_INTERVAL = 5     # Blink every 5 seconds
WIFI_DISCONNECTED_BLINK_INTERVAL = 0.1  # Gap between double blinks for disconnected state

# ------------------------
# GPIO setup
# ------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

# Global flag to pause WiFi blinking during button operations
button_active = threading.Lock()

logger.info("AP/Client mode listener started (single button, continuous LED feedback)")

# ------------------------
# Helper functions
# ------------------------
def blink_led(times, interval=BLINK_INTERVAL):
    """Blink LED a number of times in one cycle."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(interval)

def is_wifi_connected():
    """Check if device is connected to a WiFi network."""
    # Method 1: Check using nmcli device status (list all devices)
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "STATE,DEVICE", "device", "status"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':wlan0' in line or line.endswith(':wlan0'):
                    parts = line.split(':')
                    if len(parts) >= 2:
                        state = parts[0]
                        device = parts[-1]
                        if device == 'wlan0':
                            logger.info(f"WiFi state check: {state}")
                            if "connected" in state.lower():
                                return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
        logger.info(f"nmcli method failed: {e}")
    
    # Method 2: Check if wlan0 has an IP address (more reliable)
    try:
        result = subprocess.run(
            ["ip", "addr", "show", "wlan0"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        if result.returncode == 0:
            # Check for inet address (not inet6/localhost)
            has_ip = "inet " in result.stdout and "127.0.0.1" not in result.stdout
            if has_ip:
                logger.info("WiFi connected (has IP address)")
                return True
            else:
                logger.info("WiFi disconnected (no IP address)")
    except Exception as e:
        logger.info(f"ip command failed: {e}")
    
    return False

def wifi_status_blinker():
    """Background thread that blinks LED to indicate WiFi connection status."""
    last_blink_time = 0
    logger.info("WiFi status blinker thread started")
    
    # Initial test
    initial_status = is_wifi_connected()
    logger.info(f"Initial WiFi status: {'connected' if initial_status else 'disconnected'}")
    
    while True:
        try:
            current_time = time.time()
            # Check WiFi status regularly
            wifi_connected = is_wifi_connected()
            
            # Only blink if button is not active and enough time has passed
            if button_active.acquire(blocking=False):
                try:
                    if current_time - last_blink_time >= WIFI_BLINK_INTERVAL:
                        if wifi_connected:
                            # Single quick blink to indicate WiFi connected
                            GPIO.output(LED_PIN, GPIO.HIGH)
                            time.sleep(WIFI_BLINK_DURATION)
                            GPIO.output(LED_PIN, GPIO.LOW)
                            last_blink_time = current_time
                            logger.info("WiFi connected - LED blinked")
                        else:
                            # Double blink to indicate WiFi disconnected
                            GPIO.output(LED_PIN, GPIO.HIGH)
                            time.sleep(WIFI_BLINK_DURATION)
                            GPIO.output(LED_PIN, GPIO.LOW)
                            time.sleep(WIFI_DISCONNECTED_BLINK_INTERVAL)
                            GPIO.output(LED_PIN, GPIO.HIGH)
                            time.sleep(WIFI_BLINK_DURATION)
                            GPIO.output(LED_PIN, GPIO.LOW)
                            last_blink_time = current_time
                            logger.info("WiFi disconnected - LED double blinked")
                finally:
                    button_active.release()
            
            time.sleep(WIFI_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error in WiFi status blinker: {e}", exc_info=True)
            time.sleep(WIFI_CHECK_INTERVAL)

# ------------------------
# Start WiFi status monitoring thread
# ------------------------
wifi_thread = threading.Thread(target=wifi_status_blinker, daemon=True)
wifi_thread.start()
logger.info("WiFi status monitoring started")

# ------------------------
# Main loop
# ------------------------
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            # Acquire lock to prevent WiFi blinking during button operation
            button_active.acquire()
            try:
                press_start = time.time()
                blink_count = 0
                logger.info("Button pressed - counting blinks...")

                # Blink while button is held
                while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                    # One blink cycle = 1 second
                    GPIO.output(LED_PIN, GPIO.HIGH)
                    time.sleep(BLINK_INTERVAL)
                    GPIO.output(LED_PIN, GPIO.LOW)
                    time.sleep(BLINK_INTERVAL)
                    blink_count += 1
                    logger.info(f"Blink {blink_count} ({blink_count}s)")

                # Button released: determine action based on blink count
                GPIO.output(LED_PIN, GPIO.LOW)
                logger.info(f"Button released after {blink_count} blinks")

                if blink_count >= REBOOT_BLINKS:
                    logger.info(f"{blink_count} blinks → Rebooting")
                    subprocess.run(["sudo", "reboot"])
                elif blink_count >= AP_MODE_BLINKS:
                    logger.info(f"{blink_count} blinks → Switching to AP mode")
                    subprocess.run(["/usr/local/bin/switch-to-ap.sh"])
                elif blink_count >= CLIENT_MODE_BLINKS:
                    logger.info(f"{blink_count} blinks → Switching to Client mode")
                    subprocess.run(["/usr/local/bin/switch-to-client.sh"])
                else:
                    logger.info(f"{blink_count} blinks → No action (minimum 5 blinks required)")

                # Cooldown
                logger.info(f"Cooldown {COOLDOWN_SECONDS}s")
                time.sleep(COOLDOWN_SECONDS)
            finally:
                # Release lock to allow WiFi blinking to resume
                button_active.release()

        time.sleep(0.1)

except KeyboardInterrupt:
    logger.info("\nExiting program...")

finally:
    GPIO.cleanup()
    logger.info("GPIO cleaned up")
