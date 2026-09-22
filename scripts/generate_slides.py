"""
Generate production presentation deck for Averis x Monash Hackathon 2026.
Produces:
1. docs/SLIDES.html - Self-contained interactive 16:9 dark-mode slide presentation
2. docs/SLIDES.md   - Markdown companion for slide decks & Google Slides import
"""

import base64
import os

REPO_DIR = r"C:\Users\Admin\Documents\GitHub\Averis-X-Monash26"
ARTIFACT_DIR = r"C:\Users\Admin\.gemini\antigravity\brain\a0f44b19-7b67-4554-9bfe-52281baf001a"

ASSETS_DIR = os.path.join(REPO_DIR, "docs", "assets")
with open(os.path.join(ASSETS_DIR, "logo_wide.jpg"), "rb") as f:
    LOGO_WIDE = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")
with open(os.path.join(ASSETS_DIR, "logo_square.jpg"), "rb") as f:
    LOGO_SQUARE = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")

print(f"Loaded logo assets successfully.")
