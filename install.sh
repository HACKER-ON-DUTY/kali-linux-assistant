#!/usr/bin/env bash
set -e
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

sudo apt update && sudo apt install -y python3-venv python3-pip python3-pyaudio portaudio19-dev xdotool xclip blueman bluez-obexd wmctrl playerctl pulseaudio-utils libnotify-bin zenity curl
mkdir -p voices && python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx" -o voices/en_GB-alan-low.onnx
curl -sL "https://huggingface.co" -o voices/en_GB-alan-low.onnx.json

# Configure auto-start on boot (XDG Desktop Autostart for XFCE/GNOME/KDE)
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/hey-kali.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Hey Kali Assistant
Comment=Offline Voice-Activated AI Assistant for Kali Linux
Exec=$APP_DIR/venv/bin/python3 $APP_DIR/hey_kali.py
Path=$APP_DIR
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "[+] Hey Kali installed and configured to auto-start on boot!"
./venv/bin/python3 "$APP_DIR/hey_kali.py"
