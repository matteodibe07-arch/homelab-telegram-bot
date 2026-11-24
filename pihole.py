import asyncio
import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

# ---------- IMPOSTAZIONI (modificale qui) ----------
BASE = "http://localhost:8080/api"
ORA_PIHOLE = datetime.time(21, 0, tzinfo=ZoneInfo("Europe/Rome"))
DOMINI_IN_CLASSIFICA = 5
# ----------------------------------------------------


def leggi_env():
    for riga in (Path(__file__).parent / ".env").read_text().splitlines():
        if "=" in riga and not riga.startswith("#"):
            chiave, valore = riga.split("=", 1)
            os.environ[chiave.strip()] = valore.strip()


leggi_env()


def chiama(metodo, percorso, sid=None, dati=None):
    req = urllib.request.Request(BASE + percorso, method=metodo)
    if dati is not None:
        req.data = json.dumps(dati).encode()
        req.add_header("Content-Type", "application/json")
    if sid:
        req.add_header("sid", sid)
    with urllib.request.urlopen(req, timeout=10) as r:
        corpo = r.read()
    return json.loads(corpo) if corpo else {}


def n(numero):
    return f"{int(numero):,}".replace(",", ".")


def costruisci_pihole():
    try:
        sessione = chiama(
            "POST", "/auth", dati={"password": os.environ["PIHOLE_PASSWORD"]}
        )["session"]
        if not sessione.get("valid"):
            return "Pi-hole: password non accettata."
        sid = sessione["sid"]
        try:
            riepilogo = chiama("GET", "/stats/summary", sid)
            top = chiama(
                "GET", f"/stats/top_domains?blocked=true&count={DOMINI_IN_CLASSIFICA}", sid
            )
        finally:
            try:
                chiama("DELETE", "/auth", sid)
            except Exception:
                pass
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Pi-hole: password non accettata (o è attiva la verifica a due fattori)."
        return f"Pi-hole: errore {e.code} dalle API."
    except Exception as e:
        return f"Pi-hole: non riesco a leggere i dati ({type(e).__name__})."

    q = riepilogo.get("queries", {})
    righe_top = "\n".join(
        f"{i}. {d.get('domain', '?')} ({n(d.get('count', 0))})"
        for i, d in enumerate(top.get("domains", []), start=1)
    ) or "nessuno"
    return (
        "🕳 Pi-hole, ultime 24 ore\n\n"
        f"Richieste: {n(q.get('total', 0))}\n"
        f"Bloccate: {n(q.get('blocked', 0))} ({q.get('percent_blocked', 0):.1f}%)\n"
        f"Client attivi: {riepilogo.get('clients', {}).get('active', '?')}\n"
        f"Domini in blocklist: {n(riepilogo.get('gravity', {}).get('domains_being_blocked', 0))}\n\n"
        f"Domini più bloccati:\n{righe_top}"
    )


async def comando_pihole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != int(os.environ["CHAT_ID"]):
        return
    await update.message.reply_text(await asyncio.to_thread(costruisci_pihole))


async def pihole_sera(context: ContextTypes.DEFAULT_TYPE):
    testo = await asyncio.to_thread(costruisci_pihole)
    await context.bot.send_message(int(os.environ["CHAT_ID"]), testo)


def registra_pihole(app):
    app.add_handler(CommandHandler("pihole", comando_pihole))
    app.job_queue.run_daily(pihole_sera, time=ORA_PIHOLE)


if __name__ == "__main__":
    print(costruisci_pihole())
