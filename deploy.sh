#!/usr/bin/env bash
# VPS deployment script — run as root: sudo bash deploy.sh
set -e

APP_DIR="/opt/userbot"
SERVICE_USER="${SUDO_USER:-ubuntu}"

echo "╔══════════════════════════════════════════╗"
echo "║   Nasimxon's Userbot — VPS Deployment    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. System packages ───────────────────────────────────────────────────────
echo "▶ [1/5] Tizim paketlari o'rnatilmoqda..."
apt-get update -qq
apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    ffmpeg gcc git curl \
    > /dev/null 2>&1
echo "  ✓ ffmpeg, python3, gcc"

# ── 2. App directory ─────────────────────────────────────────────────────────
echo "▶ [2/5] Ilova katalogi: $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --exclude='.git' --exclude='venv' --exclude='*.session' \
    ./ "$APP_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# ── 3. Python venv + packages ────────────────────────────────────────────────
echo "▶ [3/5] Python virtual environment va paketlar..."
sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip -q
echo "  Paketlar o'rnatilmoqda (torch yuklab olinishi 5-10 daqiqa olishi mumkin)..."
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
echo "  ✓ Barcha paketlar o'rnatildi"

# ── 4. .env file ─────────────────────────────────────────────────────────────
echo "▶ [4/5] Konfiguratsiya..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.template" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "  ⚠️  .env yaratildi — API kalitlarini kiriting:"
    echo "     sudo nano $APP_DIR/.env"
else
    echo "  ✓ .env allaqachon mavjud"
fi

# ── 5. Systemd service ───────────────────────────────────────────────────────
echo "▶ [5/5] Systemd servisi o'rnatilmoqda..."
sed "s/User=ubuntu/User=$SERVICE_USER/g" "$APP_DIR/userbot.service" \
    > /etc/systemd/system/userbot.service
systemctl daemon-reload
systemctl enable userbot
echo "  ✓ userbot.service yoqildi"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║            KEYINGI QADAMLAR              ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  1. API kalitlarini kiriting:            ║"
echo "║     sudo nano $APP_DIR/.env"
echo "║                                          ║"
echo "║  2. Telegram autentifikatsiya (1 MARTA): ║"
echo "║     cd $APP_DIR"
echo "║     sudo -u $SERVICE_USER \\"
echo "║       ./venv/bin/python setup_auth.py    ║"
echo "║                                          ║"
echo "║  3. Serverni ishga tushiring:            ║"
echo "║     sudo systemctl start userbot         ║"
echo "║     sudo systemctl status userbot        ║"
echo "║                                          ║"
echo "║  4. Loglarni kuzating:                   ║"
echo "║     journalctl -u userbot -f             ║"
echo "║     tail -f $APP_DIR/userbot.log"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
