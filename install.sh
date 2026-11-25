#!/usr/bin/env bash
set -e
APP_DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
cd "$APP_DIR"

echo "[1/5] Installing Kali Linux system dependencies..."
sudo apt update && sudo apt install -y \
  python3-venv python3-pip python3-pyaudio portaudio19-dev \
  xdotool xclip blueman bluez-obexd wmctrl playerctl \
  pulseaudio-utils libnotify-bin zenity ffmpeg espeak-ng curl

echo "[2/5] Setting up Python virtual environment & packages..."
mkdir -p voices && python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "[3/5] Downloading Piper neural voices (Default + Smooth Male Human Voice)..."
./venv/bin/python3 -m piper.download_voices --download-dir voices en_GB-alan-low en_US-ryan-medium

echo "[4/5] Checking local Ollama AI (gemma3:1b)..."
if ! command -v ollama >/dev/null 2>&1; then
  sudo apt install -y ollama || true
fi
if command -v ollama >/dev/null 2>&1; then
  systemctl is-active --quiet ollama || sudo systemctl enable --now ollama || true
  ollama pull gemma3:1b || true
fi

echo "[5/5] Configuring auto-start on boot..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/hey-kali.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hey Kali Assistant
Comment=Offline Voice-Activated AI Assistant for Kali Linux
Exec=$APP_DIR/venv/bin/python3 $APP_DIR/hey_kali.py
Path=$APP_DIR
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

echo "[+] Hey Kali installed and configured to auto-start on boot!"
./venv/bin/python3 "$APP_DIR/hey_kali.py"
