import asyncio
import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
from telegram import LinkPreviewOptions, Update
from telegram.ext import CommandHandler, ContextTypes

# ---------- IMPOSTAZIONI -------------------
FEED = {
    "ANSA": "https://www.ansa.it/sito/ansait_rss.xml",
    "Il Post": "https://www.ilpost.it/feed/",
    "Hacker News": "https://news.ycombinator.com/rss",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
}
NOTIZIE_PER_FONTE = 3
ORA_NEWS = datetime.time(18, 0, tzinfo=ZoneInfo("Europe/Rome"))
# ----------------------------------------------------

VISTI = Path(__file__).parent / "news_visti.json"
SENZA_ANTEPRIMA = LinkPreviewOptions(is_disabled=True)


def carica_visti():
    try:
        return json.loads(VISTI.read_text())
    except (FileNotFoundError, ValueError):
        return []


def costruisci_news():
    visti = carica_visti()
    blocchi = []
    for fonte, url in FEED.items():
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        righe = []
        for e in feed.entries:
            link = e.get("link")
            if not link or link in visti:
                continue
            titolo = e.get("title", "(senza titolo)").strip()
            righe.append(f"• {titolo}\n{link}")
            visti.append(link)
            if len(righe) >= NOTIZIE_PER_FONTE:
                break
        if righe:
            blocchi.append(f"📰 {fonte}\n" + "\n".join(righe))
    VISTI.write_text(json.dumps(visti[-1000:]))
    return "\n\n".join(blocchi) or "Nessuna notizia nuova."


async def comando_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(os.environ["CHAT_ID"]):
        return
    testo = await asyncio.to_thread(costruisci_news)
    await update.message.reply_text(testo[:4000], link_preview_options=SENZA_ANTEPRIMA)


async def news_sera(context: ContextTypes.DEFAULT_TYPE):
    testo = await asyncio.to_thread(costruisci_news)
    await context.bot.send_message(
        int(os.environ["CHAT_ID"]),
        "🗞 Notizie della sera\n\n" + testo[:3900],
        link_preview_options=SENZA_ANTEPRIMA,
    )


def registra(app):
    app.add_handler(CommandHandler("news", comando_news))
    app.job_queue.run_daily(news_sera, time=ORA_NEWS)
