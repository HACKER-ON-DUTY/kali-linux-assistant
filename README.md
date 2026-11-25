[![GitHub Stars](https://img.shields.io/github/stars/TECH-ON-DUTY/kali-linux-assistant)](https://github.com/TECH-ON-DUTY/kali-linux-assistant) ![Kali Linux](https://img.shields.io/badge/Kali_Linux-Supported-red)

# Kali Linux Assistant (Hey Kali) — Offline-First Hybrid AI Voice Assistant for Kali Linux

**Hey Kali** is a low-latency, privacy-focused voice assistant engineered for **Kali Linux (XFCE)**. It combines an instant offline Vosk wake-word and grammar engine, Whisper + Google STT transcription, Piper neural text-to-speech, and local `gemma3:1b` AI reasoning with 119 built-in system, security, desktop, Bluetooth, and OSINT automation commands.

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
- **Voice Web & Subdomain Recon (`whatweb` + `crt.sh`)**:
  - `"Hey Kali, web recon <domain>"` / `"enumerate <domain>"` — Fingerprints web server technologies via `whatweb`, enumerates subdomains, speaks a summary, and saves a Desktop report.
- **Hands-Free Voice Recon & Port Scanner**:
  - `"Hey Kali, scan <target>"` / `"scan my network"` — Runs a fast background `nmap` scan, announces open ports via TTS, and opens a Desktop recon report.
- **Instant Voice Switcher**:
  - `"Hey Kali, change voice"` — Toggles between the default voice and a smooth natural male neural voice (`en_US-ryan-medium`).
- **Background OSINT Worker (`osint_worker.py`)**:
  - `"Hey Kali, run osint on <target>"` generates and opens a structured desktop OSINT report.
- **Built-in 119-Command Self-Diagnostic**:
  - `"Hey Kali, self check"` tests all 119 command modules automatically.

## System Requirements (Kali Linux / Debian)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pyaudio portaudio19-dev xdotool xclip blueman bluez-obexd wmctrl playerctl pulseaudio-utils libnotify-bin zenity
```

## Installation & Setup
```bash
git clone https://github.com/TECH-ON-DUTY/kali-linux-assistant.git
cd kali-linux-assistant
bash install.sh
```
Download a Piper voice model (e.g. `en_GB-alan-low.onnx` + `.onnx.json`) into `voices/`, install Ollama (`ollama pull gemma3:1b`) for local LLM queries, and start the assistant:
```bash
./venv/bin/python3 hey_kali.py
```

## Use Cases & Related Search Keywords

Looking for a **Kali Linux Assistant**, **Kali Linux Jarvis**, or **offline Linux voice assistant in Python**? This project covers:
- **Kali Linux & Jarvis Voice Control**: `kali linux assistant`, `kali linux voice assistant`, `kali linux ai assistant`, `hey kali`, `hey kali assistant`, `hey kali voice assistant`, `kali linux jarvis`, `jarvis for kali linux`, `ai assistant for kali linux`, `voice control kali linux`, `offline voice assistant kali linux`, `kali linux desktop automation`
- **Offline Speech & Local LLM**: `offline linux voice assistant python`, `vosk whisper piper voice assistant`, `vosk wake word linux`, `piper tts voice assistant linux`, `ollama voice assistant linux`, `gemma voice assistant python`, `local ai voice assistant linux`, `privacy focused voice assistant linux`, `hands free linux control python`, `xfce voice assistant`, `debian voice assistant python`, `python speech recognition linux automation`
- **Cybersecurity, Pentesting & OSINT**: `ai pentesting assistant kali`, `voice controlled osint tool`, `kali linux osint automation`, `voice activated nmap wireshark`, `cybersecurity voice assistant`, `ethical hacking ai assistant`, `hacker voice assistant python`, `kali linux workflow automation`, `automated osint report generator python`, `kali linux recon mode`, `kali linux hacker mode`, `hands free pentesting kali`
- **BackTrack 3 Theme & Desktop Ricing**: `backtrack 3 theme kali linux`, `kali linux backtrack mode`, `kali red dark theme switcher`, `xfce theme switcher script`, `kali linux hacker theme automation`, `backtrack wallpaper kali linux`, `kali linux focus mode script`, `kali linux chill mode`, `xfce workspace profile switcher`, `kali linux desktop ricing automation`
- **Bluetooth OBEX, X11 Dictation & Linux Utilities**: `linux voice bluetooth file transfer`, `send file to phone via bluetooth linux cli`, `blueman bluez-obexd python automation`, `bluetoothctl python voice control`, `connect bluetooth device by voice linux`, `linux voice dictation xdotool`, `voice typing x11 linux python`, `swahili english voice dictation linux`, `andika voice typing linux`, `multi command voice chaining python`, `linux clipboard error fixer ai`, `voice controlled terminal commands linux`, `systemd user voice assistant service`, `HACKER-ON-DUTY kali-linux-assistant`

## Disclaimer & Rules of Use
This tool is intended strictly for **authorized security administration, educational labs, and personal desktop automation**. Users are solely responsible for complying with applicable local laws when using network scanning or OSINT modules.
