"""Capture pixel-perfect 1440x900 screenshots of VoxLab for README documentation."""

import os
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.abspath("docs/assets/screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# 1. Acquire Auth Token
print("Acquiring demo auth token...")
data = json.dumps({"email": "demo@voxlab.dev", "password": "demo123"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8001/api/auth/login", data=data, headers={"Content-Type": "application/json"})
res = urllib.request.urlopen(req)
token = json.loads(res.read().decode("utf-8"))["access_token"]
print("Auth token acquired.")

PAGES = [
    ("dashboard.png", "http://localhost:3000/dashboard", 2500),
    ("agent-registry.png", "http://localhost:3000/agents", 2000),
    ("voice-playground.png", "http://localhost:3000/playground", 2500),
    ("scenario-runner.png", "http://localhost:3000/scenarios", 2000),
    ("observability.png", "http://localhost:3000/traces/831", 2500),
    ("benchmark-reports.png", "http://localhost:3000/reports/30", 2500),
    ("darwin-dashboard.png", "http://localhost:3000/darwin", 2500),
    ("darwin-failure-analysis.png", "http://localhost:3000/darwin/66", 2500),
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=1,
    )
    page = context.new_page()

    # Pre-seed localStorage with auth token
    page.goto("http://localhost:3000/register")
    page.wait_for_load_state("domcontentloaded")
    page.evaluate(f"localStorage.setItem('voxlab_token', '{token}')")

    for filename, url, wait_ms in PAGES:
        dest_path = os.path.join(SCREENSHOTS_DIR, filename)
        print(f"Capturing {filename} from {url}...")
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(url)
        time.sleep(wait_ms / 1000.0)
        
        # If voice playground, send a message to show conversation interaction
        if filename == "voice-playground.png":
            try:
                # Type a realistic message
                input_el = page.locator("input[placeholder*='type'], input[placeholder*='message'], textarea").first
                if input_el.count() > 0:
                    input_el.fill("Check order status for ORD-4821")
                    send_btn = page.locator("button:has-text('Send')").first
                    if send_btn.count() > 0:
                        send_btn.click()
                        time.sleep(1.5)
            except Exception as e:
                print(f"Note on playground interaction: {e}")

        page.screenshot(path=dest_path, full_page=False)
        print(f"Saved: {dest_path} ({os.path.getsize(dest_path)} bytes)")

    browser.close()

print("All screenshots successfully captured!")
