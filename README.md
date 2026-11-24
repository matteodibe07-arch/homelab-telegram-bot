# Homelab Telegram Bot

A small Telegram bot that watches a Raspberry Pi homelab (Docker + Pi-hole) and sends status reports and alerts straight to your phone.

## Features

- `/stato`: on-demand status (CPU temperature, RAM, disk usage, uptime, Docker containers)
- Daily morning report (08:00, Europe/Rome)
- Automatic alerts for high temperature, nearly full disks and stopped containers, plus a "resolved" message when the problem goes away (no repeated spam)
- `/news` and an evening digest (18:00) from RSS feeds, never repeating an article
- `/pihole` and a nightly summary (21:00) from the Pi-hole v6 API
- Answers only to your own Telegram chat ID

Command names and messages are in Italian; they are easy to change in the code.

## Requirements

- Raspberry Pi (or any Linux machine) with Python 3.10+
- Docker, with your user in the `docker` group
- Pi-hole v6 (optional), web interface reachable at `localhost:8080`

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and keep the token private.
2. Send any message to your new bot, then find your chat ID:

        curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"

3. Install:

        git clone https://github.com/YOUR_USER/homelab-telegram-bot.git
        cd homelab-telegram-bot
        python3 -m venv venv
        ./venv/bin/pip install -r requirements.txt

4. Create your `.env` file and protect it:

        cp .env.example .env
        nano .env
        chmod 600 .env

5. Run it:

        ./venv/bin/python bot.py

## Run at boot (systemd)

Create `/etc/systemd/system/bot-homelab.service`:

        [Unit]
        Description=Homelab Telegram bot
        After=network-online.target docker.service
        Wants=network-online.target

        [Service]
        User=YOUR_USER
        WorkingDirectory=/home/YOUR_USER/homelab-telegram-bot
        ExecStart=/home/YOUR_USER/homelab-telegram-bot/venv/bin/python bot.py
        Restart=always
        RestartSec=10

        [Install]
        WantedBy=multi-user.target

Then enable it:

        sudo systemctl daemon-reload
        sudo systemctl enable --now bot-homelab

## Configuration

- `bot.py`: alert thresholds, check interval, report time, monitored disk paths (e.g. `/mnt/cloud`)
- `news.py`: RSS feeds, number of items per source, digest time
- `pihole.py`: Pi-hole API address and summary time

## Security notes

- Never commit `.env`: it contains your bot token and Pi-hole password.
- The bot ignores every chat except the one in `CHAT_ID`.
- Do not expose the Pi-hole web interface or API to the internet.

## Credits

Designed, configured and tested by the author. The code was written with the help of Claude (Anthropic).
