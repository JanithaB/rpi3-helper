#!/bin/bash

import RPi.GPIO as GPIO
import subprocess
import time

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

# ------------------------
# GPIO setup
# ------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

print("AP/Client mode listener started (single button, continuous LED feedback)")

# ------------------------
# Helper function
# ------------------------
def blink_led(times, interval=BLINK_INTERVAL):
    """Blink LED a number of times in one cycle."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(interval)

# ------------------------
# Main loop
# ------------------------
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            press_start = time.time()
            blink_count = 0
            print("Button pressed - counting blinks...")

            # Blink while button is held
            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                # One blink cycle = 1 second
                GPIO.output(LED_PIN, GPIO.HIGH)
                time.sleep(BLINK_INTERVAL)
                GPIO.output(LED_PIN, GPIO.LOW)
                time.sleep(BLINK_INTERVAL)
                blink_count += 1
                print(f"Blink {blink_count} ({blink_count}s)")

            # Button released: determine action based on blink count
            GPIO.output(LED_PIN, GPIO.LOW)
            print(f"Button released after {blink_count} blinks")

            if blink_count >= REBOOT_BLINKS:
                print(f"{blink_count} blinks → Rebooting")
                subprocess.run(["sudo", "reboot"])
            elif blink_count >= AP_MODE_BLINKS:
                print(f"{blink_count} blinks → Switching to AP mode")
                subprocess.run(["/usr/local/bin/switch-to-ap.sh"])
            elif blink_count >= CLIENT_MODE_BLINKS:
                print(f"{blink_count} blinks → Switching to Client mode")
                subprocess.run(["/usr/local/bin/switch-to-client.sh"])
            else:
                print(f"{blink_count} blinks → No action (minimum 5 blinks required)")

            # Cooldown
            print(f"Cooldown {COOLDOWN_SECONDS}s")
            time.sleep(COOLDOWN_SECONDS)

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nExiting program...")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up")
