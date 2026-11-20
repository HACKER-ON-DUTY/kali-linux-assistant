#!/usr/bin/env bash
set -e
sudo apt update && sudo apt install -y python3-venv python3-pip python3-pyaudio portaudio19-dev xdotool xclip obexftp wmctrl playerctl pulseaudio-utils libnotify-bin zenity curl
mkdir -p voices && python3 -m venv venv
./venv/bin/pip install -r requirements.txt
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx" -o voices/en_GB-alan-low.onnx
curl -sL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low/en_GB-alan-low.onnx.json" -o voices/en_GB-alan-low.onnx.json
./venv/bin/python3 hey_kali.py
