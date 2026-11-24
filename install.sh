#!/usr/bin/env bash
set -e
sudo apt update && sudo apt install -y python3-venv python3-pip python3-pyaudio portaudio19-dev xdotool xclip obexftp wmctrl playerctl pulseaudio-utils libnotify-bin zenity curl
mkdir -p voices && python3 -m venv venv
./venv/bin/pip install -r requirements.txt
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx" -o voices/en_GB-alan-low.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx.json" -o voices/en_GB-alan-low.onnx.json
./venv/bin/python3 hey_kali.py

# Configure automatic startup on login/reboot
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
cat << INNER_EOF > "$INSTALL_DIR/start_kali.sh"
#!/usr/bin/env bash
sleep 5
cd "$INSTALL_DIR"
exec "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/hey_kali.py" >> "$INSTALL_DIR/hey_kali.log" 2>&1
INNER_EOF
chmod +x "$INSTALL_DIR/start_kali.sh"

mkdir -p "$HOME/.config/autostart"
cat << INNER_EOF > "$HOME/.config/autostart/hey-kali.desktop"
[Desktop Entry]
Type=Application
Name=Hey Kali Assistant
Comment=Offline AI Voice Assistant for Kali Linux
Exec=$INSTALL_DIR/start_kali.sh
Terminal=false
X-GNOME-Autostart-enabled=true
INNER_EOF
echo "Auto-start on reboot configured!"
