import asyncio
import json
import subprocess
import time
import urllib.request
import base64
import os
import shutil
import websockets

PDF_DEST = r"C:\Users\Admin\Downloads\SDOC_Pitch_Deck.pdf"
HTML_URL = "file:///C:/Users/Admin/Documents/GitHub/Averis-X-Monash26/docs/SLIDES.html"
USER_DATA = r"C:\Users\Admin\AppData\Local\Temp\edge_pdf_profile"
PORT = 9444

async def export_pdf():
    # 1. Clean temp profile
    if os.path.exists(USER_DATA):
        shutil.rmtree(USER_DATA, ignore_errors=True)
    os.makedirs(USER_DATA, exist_ok=True)

    # 2. Start Edge with isolated profile & unique port
    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    proc = subprocess.Popen([
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={USER_DATA}",
        f"--remote-debugging-port={PORT}",
        "--window-size=1920,1080"
    ])
    await asyncio.sleep(2.5)

    try:
        # 3. Get page target webSocketDebuggerUrl
        req = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")
        targets = json.loads(req.read().decode("utf-8"))
        page_targets = [t for t in targets if t.get("type") == "page"]
        if not page_targets:
            page_targets = targets
        ws_url = page_targets[0]["webSocketDebuggerUrl"]
        print(f"Connected to page target: {page_targets[0].get('title')} ({ws_url})")

        # 4. Connect via WebSocket
        async with websockets.connect(ws_url, max_size=100*1024*1024) as ws:
            # Enable Page
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await ws.recv()

            # Navigate to SLIDES.html
            await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": HTML_URL}}))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == 2:
                    break
            
            # Wait for DOM and images
            await asyncio.sleep(2.5)

            # Print to PDF with landscape 16:9
            print_opts = {
                "id": 3,
                "method": "Page.printToPDF",
                "params": {
                    "landscape": True,
                    "paperWidth": 16.0,
                    "paperHeight": 9.0,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                    "printBackground": True,
                    "preferCSSPageSize": False
                }
            }
            await ws.send(json.dumps(print_opts))
            
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == 3:
                    if "error" in resp:
                        print("Page.printToPDF error:", resp["error"])
                        break
                    pdf_b64 = resp["result"]["data"]
                    pdf_bytes = base64.b64decode(pdf_b64)
                    with open(PDF_DEST, "wb") as f:
                        f.write(pdf_bytes)
                    print(f"Successfully exported PDF to: {PDF_DEST}")
                    print(f"PDF Size: {len(pdf_bytes)} bytes")
                    break

    finally:
        proc.terminate()
        time.sleep(1)
        shutil.rmtree(USER_DATA, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(export_pdf())
