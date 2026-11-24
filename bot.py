import datetime
import os
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from news import registra
from pihole import registra_pihole
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- IMPOSTAZIONI --------------
SOGLIA_TEMP = 60            # °C: oltre questa temperatura arriva un avviso
SOGLIA_DISCO = 80           # %: oltre questa percentuale di disco pieno arriva un avviso
INTERVALLO_CONTROLLO = 300  # secondi tra un controllo e l'altro (300 = 5 minuti)
ORA_REPORT = datetime.time(8, 0, tzinfo=ZoneInfo("Europe/Rome"))
CONTAINER_IGNORATI = set()  # nomi di container da non controllare, es. {"prova"}
# ---------------------------------------------------


def carica_env():
    for riga in (Path(__file__).parent / ".env").read_text().splitlines():
        if "=" in riga and not riga.startswith("#"):
            chiave, valore = riga.split("=", 1)
            os.environ[chiave.strip()] = valore.strip()


carica_env()
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])


def temperatura():
    return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000


def ram():
    info = {}
    for riga in Path("/proc/meminfo").read_text().splitlines():
        chiave, valore = riga.split(":")
        info[chiave] = int(valore.split()[0])
    totale = info["MemTotal"] / 1024
    usata = (info["MemTotal"] - info["MemAvailable"]) / 1024
    return usata, totale


def disco(percorso):
    try:
        u = shutil.disk_usage(percorso)
    except FileNotFoundError:
        return None
    return u.used / 1e9, u.total / 1e9, u.used / u.total * 100


def uptime():
    s = int(float(Path("/proc/uptime").read_text().split()[0]))
    return f"{s // 86400} g {s % 86400 // 3600} h"


def container():
    r = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
        capture_output=True, text=True, timeout=10,
    )
    risultato = []
    for riga in r.stdout.strip().splitlines():
        nome, stato = riga.split("|", 1)
        if nome not in CONTAINER_IGNORATI:
            risultato.append((nome, stato))
    return risultato


def riga_disco(etichetta, percorso):
    d = disco(percorso)
    if d is None:
        return f"{etichetta}: non trovato"
    return f"{etichetta}: {d[0]:.0f} / {d[1]:.0f} GB ({d[2]:.0f}%)"


# ---------- IL MESSAGGIO (cambialo come vuoi) ----------
def costruisci_messaggio(titolo):
    usata, totale = ram()
    righe_container = "\n".join(
        f"{'🟢' if st.startswith('Up') else '🔴'} {nome}: {st}"
        for nome, st in container()
    ) or "nessuno"
    return (
        f"{titolo}\n\n"
        f"🌡 Temperatura: {temperatura():.1f} °C\n"
        f"🧠 RAM: {usata:.0f} / {totale:.0f} MB\n"
        f"💾 {riga_disco('Disco sistema', '/')}\n"
        f"☁️ {riga_disco('Disco cloud', '/mnt/cloud')}\n"
        f"⏱ Acceso da: {uptime()}\n\n"
        f"Container:\n{righe_container}"
    )
# --------------------------------------------------------


def trova_problemi():
    problemi = {}
    t = temperatura()
    if t >= SOGLIA_TEMP:
        problemi["temp"] = f"Temperatura alta: {t:.1f} °C"
    for chiave, etichetta, percorso in [
        ("disco_sistema", "Disco sistema", "/"),
        ("disco_cloud", "Disco cloud", "/mnt/cloud"),
    ]:
        d = disco(percorso)
        if d and d[2] >= SOGLIA_DISCO:
            problemi[chiave] = f"{etichetta} quasi pieno: {d[2]:.0f}%"
    for nome, st in container():
        if not st.startswith("Up"):
            problemi["c_" + nome] = f"Container {nome} non attivo ({st})"
    return problemi


async def stato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    await update.message.reply_text(costruisci_messaggio("📊 Stato del server"))


async def controlla(context: ContextTypes.DEFAULT_TYPE):
    precedenti = context.bot_data.get("problemi", {})
    attuali = trova_problemi()
    for chiave, testo in attuali.items():
        if chiave not in precedenti:
            await context.bot.send_message(CHAT_ID, f"⚠️ {testo}")
    for chiave, testo in precedenti.items():
        if chiave not in attuali:
            await context.bot.send_message(CHAT_ID, f"✅ Risolto: {testo}")
    context.bot_data["problemi"] = attuali


async def report_mattina(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(CHAT_ID, costruisci_messaggio("☀️ Buongiorno, ecco il server"))


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("stato", stato))
    app.job_queue.run_repeating(controlla, interval=INTERVALLO_CONTROLLO, first=20)
    app.job_queue.run_daily(report_mattina, time=ORA_REPORT)
    registra(app)
    registra_pihole(app)
    app.run_polling()


if __name__ == "__main__":
    main()
