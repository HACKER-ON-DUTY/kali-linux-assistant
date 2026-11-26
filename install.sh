#!/usr/bin/env bash
set -e
APP_DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
cd "$APP_DIR"

echo "[1/6] Installing Kali Linux system dependencies (Audio, X11, Bluetooth, Recon)..."
sudo apt update && sudo apt install -y \
  python3-venv python3-pip python3-pyaudio portaudio19-dev \
  xdotool xclip blueman bluez-obexd obexftp wmctrl playerctl \
  pulseaudio-utils libnotify-bin zenity ffmpeg espeak-ng \
  nmap whatweb avahi-utils samba-common-bin curl unzip \
  alsa-utils brightnessctl tesseract-ocr poppler-utils

echo "[2/6] Setting up Python virtual environment & packages..."
mkdir -p voices && python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "[3/6] Downloading offline Vosk English speech model (zero manual download)..."
if [ ! -d "vosk-model-small-en-us-0.15" ] && [ ! -d "model" ]; then
  _VOSK_URL="https://""alphacephei.com""/vosk/models/vosk-model-small-en-us-0.15.zip"
  curl -L --fail "$_VOSK_URL" -o /tmp/vosk-model.zip
  unzip -q /tmp/vosk-model.zip -d "$APP_DIR"
  rm -f /tmp/vosk-model.zip
fi

echo "[4/6] Downloading Piper neural voices (Default + Smooth Male Human Voice)..."
./venv/bin/python3 -m piper.download_voices --download-dir voices en_GB-alan-low en_US-ryan-medium en_GB-northern_english_male-medium

echo "[5/6] Configuring local Ollama AI (gemma3:1b) & passwordless ARP recon..."
if ! command -v ollama >/dev/null 2>&1; then
  sudo apt install -y ollama || curl -fsSL https://ollama.com | sh || true
fi
if command -v ollama >/dev/null 2>&1; then
  systemctl is-active --quiet ollama || sudo systemctl enable --now ollama || true
  ollama pull gemma3:1b || true
fi

echo "${SUDO_USER:-$USER} ALL=(ALL) NOPASSWD: /usr/bin/nmap" | sudo tee /etc/sudoers.d/hey-kali-net >/dev/null && sudo chmod 440 /etc/sudoers.d/hey-kali-net || true

echo "[6/6] Configuring systemd user service for automatic startup & crash recovery..."
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/hey-kali.service" <<UNIT
[Unit]
Description=Hey Kali Offline-First AI Voice Assistant
After=sound.target pulseaudio.service pipewire.service graphical-session.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStartPre=/bin/sleep 5
ExecStart=$APP_DIR/venv/bin/python3 $APP_DIR/hey_kali.py
Restart=always
RestartSec=3
Environment=DISPLAY=:0
Environment=XAUTHORITY=$HOME/.Xauthority
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now hey-kali.service
if command -v xfconf-query >/dev/null 2>&1; then
  xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Alt>k" -n -t string -s "touch /tmp/kali_stop_now" 2>/dev/null || xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Alt>k" -s "touch /tmp/kali_stop_now" 2>/dev/null || true
fi

echo "[+] Hey Kali is 100% installed, running in the background, and ready! Say 'Hey Kali'..."
