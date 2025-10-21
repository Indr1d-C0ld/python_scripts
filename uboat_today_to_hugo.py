#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, subprocess, sys
from datetime import datetime
from typing import List
import requests
from bs4 import BeautifulSoup

# --- Config base (adatta se serve) ---
BLOG_PATH   = "/home/pi/blog"
POSTS_DIR   = os.path.join(BLOG_PATH, "content/posts")
BASE_URL    = "https://timrouter.dns.army/blog/posts"  # coerente con index.html
POST_SLUG   = "uboat-events"
REQUEST_TIMEOUT = 15

# Telegram come nel tuo rss_daily_digest.py
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# Opzionale: traduzione via deep_translator
# - LibreTranslate: esporta LIBRETRANSLATE_URL (es. http://localhost:5000)
# - DeepL: esporta DEEPL_API_KEY
TRANSLATE = True
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

def now_rome():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now()

def fetch_today_html():
    url = "https://uboat.net/today.html"
    r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent":"uboat-events/1.0"})
    r.raise_for_status()
    return r.text

def extract_general_events(html: str, today_dt: datetime) -> List[str]:
    """
    Ritorna lista di paragrafi/righe Markdown-ready della sezione 'General Events on <Day Month>'.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Esempio visibile oggi: '## General Events on 21 October'
    day_label = today_dt.strftime("%-d %B") if sys.platform != "win32" else today_dt.strftime("%#d %B")
    # la pagina usa mese in inglese; assicuriamoci in inglese:
    day_label_en = today_dt.strftime("%-d %B").replace("à", "a") if sys.platform != "win32" else today_dt.strftime("%#d %B")

    target_h2_text = f"General Events on {day_label_en}"
    # trova header h2 esatto
    h2 = None
    for tag in soup.find_all(["h2"]):
        if tag.get_text(strip=True) == target_h2_text:
            h2 = tag
            break
    if not h2:
        # fallback: cerca "General Events on " e contiene mese corrente
        for tag in soup.find_all(["h2"]):
            t = tag.get_text(" ", strip=True)
            if t.startswith("General Events on "):
                h2 = tag
                break
    if not h2:
        return []

    # raccogli fino al prossimo h2 (o fine)
    collected = []
    for sib in h2.next_siblings:
        if getattr(sib, "name", None) == "h2":
            break
        if isinstance(sib, str):
            txt = sib.strip()
            if txt:
                collected.append(txt)
            continue
        # stop esplicito se appare "Add more events!"
        if sib.get_text(strip=True).startswith("Add more events!"):
            break
        # mantieni headings minori e paragrafi
        if sib.name in ("h3","h4"):
            collected.append(f"### {sib.get_text(strip=True)}")
        elif sib.name in ("p","li","div"):
            t = sib.get_text(" ", strip=True)
            if t:
                collected.append(t)
        elif sib.name == "ul":
            for li in sib.find_all("li", recursive=False):
                t = li.get_text(" ", strip=True)
                if t:
                    collected.append(f"- {t}")
    # ripulisci righe vuote multiple
    out = []
    for line in collected:
        line = re.sub(r"\s+", " ", line).strip()
        if not out or line or out[-1] != "":
            out.append(line)
    return out

def try_translate_to_it(text: str) -> str:
    if not TRANSLATE or not text.strip():
        return text
    try:
        from deep_translator import LibreTranslator, DeeplTranslator
        if DEEPL_API_KEY:
            return DeeplTranslator(api_key=DEEPL_API_KEY, source="en", target="it").translate(text)
        if LIBRETRANSLATE_URL:
            return LibreTranslator(source="en", target="it", base_url=LIBRETRANSLATE_URL).translate(text)
    except Exception:
        pass
    return text  # fallback: nessuna traduzione se non configurata

def build_tags_it(lines_en: List[str]) -> List[str]:
    # tag fissi + dinamici da pattern U-boat e luoghi semplici
    tags = {"uboat","eventi","seconda-guerra-mondiale","storia","marina"}
    ids = set(re.findall(r"\bU-\d{1,4}\b", " ".join(lines_en)))
    tags.update({i.lower() for i in ids})
    # Anni presenti
    years = set(re.findall(r"\b(19[1-5]\d|1940|1941|1942|1943|1944|1945)\b", " ".join(lines_en)))
    tags.update(years)
    return sorted(tags)

def front_matter(title: str, dt_local: datetime, tags: List[str]) -> str:
    iso_ts = dt_local.isoformat(timespec="seconds")
    tags_yaml = "[" + ",".join(f"\"{t}\"" for t in tags) + "]"
    return f"""---
title: "{title}"
date: {iso_ts}
tags: {tags_yaml}
---
"""

def write_post(dt_local: datetime, slug: str, body_md: str):
    pub_date = dt_local.strftime("%Y-%m-%d")
    year = pub_date[:4]
    post_dir = os.path.join(POSTS_DIR, year)
    os.makedirs(post_dir, exist_ok=True)
    filename = f"{pub_date}-{slug}.md"
    path = os.path.join(post_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body_md)
    return path, filename, year

def run_hugo_and_publish(year: str, filename: str):
    # build
    subprocess.run(["hugo", "-s", BLOG_PATH], check=True)
    # post su Telegram con anteprima
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        post_url = f"{BASE_URL}/{year}/{filename.replace('.md','')}/"
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": post_url, "disable_web_page_preview": False},
                timeout=10
            )
        except Exception:
            pass
    return True

def main():
    dt_local = now_rome()
    html = fetch_today_html()
    lines_en = extract_general_events(html, dt_local)
    if not lines_en:
        print("[WARN] Nessun contenuto 'General Events' trovato per oggi.")
        return

    # blocco originale in inglese
    block_en = "\n\n".join(lines_en)

    # traduzione se disponibile
    block_it = try_translate_to_it(block_en)

    # titolo e front matter
    title = f"U-Boat – Eventi del giorno {dt_local.strftime('%d.%m.%y')}"
    tags = build_tags_it(lines_en)
    fm = front_matter(title, dt_local, tags)

    # corpo: mostra prima versione IT se diversa, poi link a sorgente
    hdr = f"### Sorgente\n\n[uboat.net – Events on this day](https://uboat.net/today.html)\n"
    body_md = [fm, hdr]

    if block_it.strip() != block_en.strip():
        body_md.append("## Eventi generali (traduzione IT)\n")
        body_md.append(block_it)
        body_md.append("\n---\n")
        body_md.append("## General Events (testo originale)\n")
        body_md.append(block_en)
    else:
        body_md.append("## General Events\n")
        body_md.append(block_en)

    md = "\n\n".join(body_md).rstrip() + "\n"

    path, filename, year = write_post(dt_local, POST_SLUG, md)
    print(path)
    run_hugo_and_publish(year, filename)

if __name__ == "__main__":
    main()
