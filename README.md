[![GitHub Stars](https://img.shields.io/github/stars/HACKER-ON-DUTY/kali-linux-assistant)](https://github.com/HACKER-ON-DUTY/kali-linux-assistant) ![Kali Linux](https://img.shields.io/badge/Kali_Linux-Supported-red)

# Kali Linux Assistant (Hey Kali) — Offline-First Hybrid AI Voice Assistant for Kali Linux

**Hey Kali** is a low-latency, privacy-focused voice assistant engineered for **Kali Linux (XFCE)**. It combines an instant offline Vosk wake-word and grammar engine, Whisper + Google STT transcription, Piper neural text-to-speech, and local `gemma3:1b` AI reasoning with 113 built-in system, security, desktop, Bluetooth, and OSINT automation commands.

## Key Features
- **3-Tier Speech Engine**: Offline **Vosk** wake-word (`"Hey Kali"`) & constrained command grammar (0.0s trigger) + **Faster-Whisper (`tiny.en`)** & **Google STT** fallback + **Piper** neural TTS loaded in RAM.
- **BackTrack 3 Hacker Mode & Revert Mode**:
  - `"Hey Kali, hacker mode"` — Activates **BackTrack 3** red-and-black theme (`Kali-Red-Dark`, `Flat-Remix-Red-Dark`, custom BackTrack 3 wallpaper), opens Terminal & Wireshark, sets volume to 65%, and launches Phonk music.
  - `"Hey Kali, revert mode"` — Restores default `Kali-Dark` desktop theme, icons, wallpaper slideshow, windows, and audio levels.
- **Ordinal Bluetooth Control & OBEX File Transfer**:
  - `"Hey Kali, connect to first/second/third bluetooth device"`
  - `"Hey Kali, send <filename> to my phone"` / `"send <filename> to first/second/third bluetooth"`
- **Cursor Dictation (`write` / `andika`)**:
  - `"Hey Kali, write <text>"` or `"Hey Kali, write <text> and press enter"` types directly at your active X11 cursor via `xdotool`.
- **Smart Multi-Action `"and"` Chaining**:
  - Chain commands naturally: `"Hey Kali, open terminal and play music"` or `"Hey Kali, turn on bluetooth and connect to first bluetooth device"`.
- **Background OSINT Worker (`osint_worker.py`)**:
  - `"Hey Kali, run osint on <target>"` generates and opens a structured desktop OSINT report.
- **Built-in 113-Command Self-Diagnostic**:
  - `"Hey Kali, self check"` tests all 113 command modules automatically.

## System Requirements (Kali Linux / Debian)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pyaudio portaudio19-dev xdotool xclip obexftp wmctrl playerctl pulseaudio-utils libnotify-bin zenity
```

## Installation & Setup
```bash
git clone https://github.com/HACKER-ON-DUTY/kali-linux-assistant.git
cd kali-linux-assistant
python3 -m venv venv
bash install.sh
```
Download a Piper voice model (e.g. `en_GB-alan-low.onnx` + `.onnx.json`) into `voices/`, install Ollama (`ollama pull gemma3:1b`) for local LLM queries, and start the assistant:
```bash
./venv/bin/python3 hey_kali.py
```

## Disclaimer & Rules of Use
This tool is intended strictly for **authorized security administration, educational labs, and personal desktop automation**. Users are solely responsible for complying with applicable local laws when using network scanning or OSINT modules.
