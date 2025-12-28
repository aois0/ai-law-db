#!/usr/bin/env python3
"""2020年判決PDFダウンロード"""
import requests
import time
from pathlib import Path

BASE_URL = "https://www.nta.go.jp/about/organization/ntc/soshoshiryo/kazei/2020/pdf"
OUTPUT_DIR = Path("/home/user/ai-law-db/data/hanketsu/2020/pdf")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 13361-13502
for num in range(13361, 13503):
    pdf_path = OUTPUT_DIR / f"{num}.pdf"
    if pdf_path.exists():
        print(f"Skip: {num}.pdf (exists)")
        continue

    url = f"{BASE_URL}/{num}.pdf"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            pdf_path.write_bytes(r.content)
            print(f"OK: {num}.pdf ({len(r.content)//1024}KB)")
        else:
            print(f"FAIL: {num}.pdf (HTTP {r.status_code})")
    except Exception as e:
        print(f"ERROR: {num}.pdf ({e})")
    time.sleep(0.3)

print(f"\nTotal: {len(list(OUTPUT_DIR.glob('*.pdf')))} files")
