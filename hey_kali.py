import os as _os_lock, sys as _sys_lock, signal as _sig_lock, time as _time_lock
_LOCK_FILE = "/tmp/hey_kali.pid"
if _os_lock.path.exists(_LOCK_FILE):
    try:
        _old_pid = int(open(_LOCK_FILE).read().strip())
        if _old_pid != _os_lock.getpid():
            _os_lock.kill(_old_pid, _sig_lock.SIGTERM)
            _time_lock.sleep(0.3)
    except Exception:
        pass
open(_LOCK_FILE, "w").write(str(_os_lock.getpid()))

try:
    import os as _os_ext, sys as _sys_ext; _sys_ext.path.insert(0, _os_ext.path.dirname(_os_ext.path.abspath(__file__)))
    from extras import handle_extra
except Exception as _ext_err:
    print(f'[extras import error] {_ext_err}', flush=True)
    handle_extra = lambda q: False

import urllib.request
import extras
import glob, json, os, re, shutil, subprocess, time
import numpy as np, pyaudio, speech_recognition as sr
from vosk import Model, KaldiRecognizer
from faster_whisper import WhisperModel

GUI_ENV = os.environ.copy()
GUI_ENV.setdefault("DISPLAY", ":0")
GUI_ENV.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
GUI_ENV.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")

HOME = os.path.expanduser("~")
_APP_DIR = os.path.dirname(os.path.abspath(globals().get('__file__') or 'hey_kali.py'))
CODE_FILE, CMD_FILE = os.path.join(_APP_DIR, "last_code.txt"), os.path.join(_APP_DIR, "last_command.txt")

vosk_model = Model(model_name="vosk-model-small-en-us-0.15")
wake_rec = KaldiRecognizer(vosk_model, 16000, '["hey kali", "[unk]"]')
fast_cmd_rec = KaldiRecognizer(
    vosk_model,
    16000,
    '["open terminal", "open firefox", "open browser", "open files", "open wireshark", "open medusa", "open nmap", "open metasploit", "volume up", "volume down", "mute", "unmute", "take screenshot", "take a screenshot", "lock screen", "display code", "show code", "display command", "show command", "delete code", "delete command", "list wifi", "scan wifi", "list bluetooth", "scan bluetooth", "close everything", "close all", "close all windows", "run system check", "system check", "check system health", "pause", "resume", "play next", "check yourself", "self check", "run diagnostics", "who do you belong to", "who owns you", "who made you", "who created you", "what is my ip", "check vpn", "hacker mode", "recon mode", "backtrack mode", "revert mode", "chill mode", "focus mode", "change voice", "switch voice", "[unk]"]'
)
whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
google_rec = sr.Recognizer()

FORMAT, CHANNELS, RATE, CHUNK = pyaudio.paInt16, 1, 16000, 1024
audio = pyaudio.PyAudio()
mic_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

stop_rec = KaldiRecognizer(vosk_model, 16000, '["stop", "hey kali", "kali", "[unk]"]')
VOICE_PROFILES = [
    {"id": "en_GB-alan-low", "path": os.path.join(_APP_DIR, "voices", "en_GB-alan-low.onnx"), "speed": 0.82, "label": "default voice"},
    {"id": "en_US-lessac-medium", "path": os.path.join(_APP_DIR, "voices", "en_US-lessac-medium.onnx"), "speed": 1.02, "label": "smooth natural human voice"},
]
_ACTIVE_VOICE_IDX = 0
_VOICE_SPEED = VOICE_PROFILES[0]["speed"]
PIPER_MODEL = VOICE_PROFILES[0]["path"]

piper_voice = None
try:
    from piper.voice import PiperVoice
    if os.path.exists(PIPER_MODEL):
        piper_voice = PiperVoice.load(PIPER_MODEL)
        print("Loaded Piper neural voice into RAM!", flush=True)
except Exception as e:
    print(f"Piper preload note: {e}", flush=True)

def toggle_voice():
    global _ACTIVE_VOICE_IDX, _VOICE_SPEED, PIPER_MODEL, piper_voice, YES_PCM, YES_RATE, yes_out_stream
    from piper.voice import PiperVoice
    next_idx = (_ACTIVE_VOICE_IDX + 1) % len(VOICE_PROFILES)
    prof = VOICE_PROFILES[next_idx]
    v_dir = os.path.dirname(prof["path"])
    os.makedirs(v_dir, exist_ok=True)
    if not os.path.exists(prof["path"]):
        subprocess.run([os.path.join(_APP_DIR, "venv", "bin", "python3"), "-m", "piper.download_voices", "--download-dir", v_dir, prof["id"]], check=True)
    new_v = PiperVoice.load(prof["path"])
    _ACTIVE_VOICE_IDX = next_idx
    _VOICE_SPEED = prof["speed"]
    PIPER_MODEL = prof["path"]
    piper_voice = new_v
    YES_RATE = piper_voice.config.sample_rate
    YES_PCM = piper_to_pcm("Yes?", length_scale=_VOICE_SPEED)
    try:
        if yes_out_stream is not None:
            yes_out_stream.close()
        yes_out_stream = audio.open(format=pyaudio.paInt16, channels=1, rate=YES_RATE, output=True)
    except Exception:
        yes_out_stream = None
    return prof["label"]

def piper_to_pcm(text, length_scale=None):
    if length_scale is None:
        length_scale = _VOICE_SPEED
    if piper_voice is None:
        return b""
    # Support both newer piper-tts (synthesize -> AudioChunk.audio_int16_bytes) and older versions
    if hasattr(piper_voice, "synthesize"):
        try:
            from piper.config import SynthesisConfig
            chunks = piper_voice.synthesize(text, syn_config=SynthesisConfig(length_scale=length_scale))
        except Exception:
            chunks = piper_voice.synthesize(text)
        out = []
        for ch in chunks:
            if hasattr(ch, "audio_int16_bytes"):
                out.append(ch.audio_int16_bytes)
            elif isinstance(ch, (bytes, bytearray)):
                out.append(bytes(ch))
        return b"".join(out)
    if hasattr(piper_voice, "synthesize_stream_raw"):
        return b"".join(piper_voice.synthesize_stream_raw(text))
    return b""

# Pre-synthesize "Yes?" with the exact same sample rate & length_scale (0.82) as speak()
YES_PCM = b""
YES_RATE = piper_voice.config.sample_rate if piper_voice is not None else 22050
try:
    if piper_voice is not None:
        YES_PCM = piper_to_pcm("Yes?", length_scale=_VOICE_SPEED)
except Exception as e:
    print(f"YES_PCM preload note: {e}", flush=True)

yes_out_stream = None
if YES_PCM:
    try:
        yes_out_stream = audio.open(format=pyaudio.paInt16, channels=1, rate=YES_RATE, output=True)
    except Exception:
        yes_out_stream = None

# Voice-Synced Caps Lock & Status LED Pulse
import glob, threading

KBD_BRIGHT_FILES = sorted(glob.glob("/sys/class/leds/input*::capslock/brightness")) + ["/sys/class/leds/hp::hddprotect/brightness", "/sys/class/leds/hda::mute/brightness"]

def set_kbd_level(level):
    val = "1" if int(level) > 0 else "0"
    led_files = sorted(glob.glob("/sys/class/leds/input*::capslock/brightness")) + ["/sys/class/leds/hp::hddprotect/brightness", "/sys/class/leds/hda::mute/brightness"]
    for bf in led_files:
        try:
            with open(bf, "w") as f:
                f.write(val)
        except Exception:
            pass
    try:
        flag = "led" if val == "1" else "-led"
        subprocess.Popen(["xset", flag, "named", "Caps Lock"], env={"DISPLAY": ":0", "XAUTHORITY": f"{os.path.expanduser('~')}/.Xauthority"})
    except Exception:
        pass

def pulse_kbd_to_pcm(pcm_bytes, sample_rate, stop_event):
    if not pcm_bytes:
        return
    step_sec = 0.045
    samples_per_step = int(sample_rate * step_sec)
    bytes_per_step = samples_per_step * 2
    try:
        for offset in range(0, len(pcm_bytes), bytes_per_step):
            if stop_event.is_set():
                break
            chunk = pcm_bytes[offset:offset + bytes_per_step]
            if not chunk:
                break
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
            set_kbd_level(1 if rms > 450 else 0)
            time.sleep(step_sec)
    finally:
        set_kbd_level(0)

def instant_yes():
    print("Kali: Yes?", flush=True)
    if yes_out_stream is not None and YES_PCM:
        try:
            ev = threading.Event()
            threading.Thread(target=pulse_kbd_to_pcm, args=(YES_PCM, YES_RATE, ev), daemon=True).start()
            yes_out_stream.write(YES_PCM)
            ev.set()
            return
        except Exception:
            pass
    if os.path.exists(os.path.join(_APP_DIR, "yes.wav")) and shutil.which("aplay"):
        subprocess.run(["aplay", "-q", os.path.join(_APP_DIR, "yes.wav")])
    else:
        subprocess.run(["espeak-ng", "-s", "210", "-a", "95", "Yes?"])

def speak(text, allow_interrupt=True):
    clean = re.sub(r"[`*#_]", "", str(text)).strip()
    if not clean:
        return False
    print(f"Kali: {clean}", flush=True)

    pcm_data = piper_to_pcm(clean) if piper_voice is not None else b""
    kbd_stop = threading.Event()
    if pcm_data:
        rate = piper_voice.config.sample_rate if piper_voice is not None else 22050
        threading.Thread(target=pulse_kbd_to_pcm, args=(pcm_data, rate, kbd_stop), daemon=True).start()

    if pcm_data and shutil.which("aplay"):
        rate = piper_voice.config.sample_rate
        proc = subprocess.Popen(
            ["aplay", "-q", "-r", str(rate), "-f", "S16_LE", "-t", "raw", "-"],
            stdin=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        try:
            proc.stdin.write(pcm_data)
            proc.stdin.close()
        except Exception:
            pass
    else:
        proc = subprocess.Popen(["espeak-ng", "-s", "205", "-a", "85", clean], preexec_fn=os.setsid)

    interrupted = False
    if allow_interrupt:
        was_active = mic_stream.is_active()
        if not was_active:
            mic_stream.start_stream()
        stop_rec.Reset()
        if os.path.exists("/tmp/kali_stop_now"):
            os.remove("/tmp/kali_stop_now")
        while proc.poll() is None:
            if os.path.exists("/tmp/kali_stop_now"):
                os.remove("/tmp/kali_stop_now")
                import signal
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                interrupted = True
                print("Kali: [Stopped via hotkey — listening for new command]", flush=True)
                break
            time.sleep(0.05)
        if not was_active:
            mic_stream.stop_stream()
    else:
        proc.wait()

    kbd_stop.set()
    return interrupted

def get_terminal_cmd():
    for term in ("qterminal", "xfce4-terminal", "gnome-terminal", "mate-terminal", "konsole", "x-terminal-emulator"):
        if shutil.which(term):
            return term
    return None

def launch_gui(cmd_list):
    try:
        subprocess.Popen(cmd_list, env=GUI_ENV, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"GUI launch error: {e}", flush=True)
        return False

def open_in_terminal(command_str, title="Kali Tool"):
    term = get_terminal_cmd()
    if not term:
        speak("No terminal emulator found.")
        return False
    shell_cmd = f"echo '=== {title} ==='; {command_str}; exec bash"
    if any(t in term for t in ("xfce4-terminal", "gnome-terminal", "mate-terminal")):
        return launch_gui([term, "--title", title, "-e", f"bash -c \"{shell_cmd}\""])
    return launch_gui([term, "-e", f"bash -c \"{shell_cmd}\""])

def open_any_app(spoken_name):
    name = str(spoken_name).strip().lower()
    aliases = {
        "terminal": ("qterminal", "xfce4-terminal", "gnome-terminal", "x-terminal-emulator"),
        "browser": ("firefox", "firefox-esr", "chromium", "google-chrome"),
        "firefox": ("firefox", "firefox-esr"),
        "chrome": ("google-chrome", "chromium"),
        "files": ("thunar", "nautilus", "pcmanfm"),
        "file manager": ("thunar", "nautilus", "pcmanfm"),
        "wireshark": ("wireshark",),
        "burp": ("burpsuite",),
        "burp suite": ("burpsuite",),
        "metasploit": ("msfconsole",),
        "vs code": ("code",),
        "text editor": ("mousepad", "gedit", "pluma"),
        "settings": ("xfce4-settings-manager", "gnome-control-center"),
        "john the ripper": ("john",),
        "aircrack": ("aircrack-ng",),
        "zenmap": ("zenmap",),
        "maltego": ("maltego",),
        "ghidra": ("ghidra",),
        "autopsy": ("autopsy",),
        "zaproxy": ("zaproxy",),
        "zap": ("zaproxy",),
    }
    gui_apps = {
        "qterminal", "xfce4-terminal", "gnome-terminal", "x-terminal-emulator", "firefox", "firefox-esr",
        "chromium", "google-chrome", "thunar", "nautilus", "pcmanfm", "wireshark", "burpsuite", "code",
        "mousepad", "gedit", "pluma", "xfce4-settings-manager", "gnome-control-center", "zenmap",
        "maltego", "ghidra", "autopsy", "zaproxy", "gparted", "vlc"
    }
    candidates = aliases.get(name, (name, name.replace(" ", "-"), name.replace(" ", "")))
    for binary in candidates:
        path = shutil.which(binary)
        if path:
            ok = launch_gui([path]) if binary in gui_apps else open_in_terminal(f"{binary} --help || {binary} -h || {binary}", title=name.upper())
            speak(f"Opening {name}")
            return ok

    for desktop_file in glob.glob("/usr/share/applications/**/*.desktop", recursive=True):
        try:
            with open(desktop_file, "r", errors="ignore") as f:
                content = f.read()
            app_title, exec_cmd, needs_term = "", "", False
            for line in content.splitlines():
                if line.startswith("Name=") and not app_title:
                    _, _, val = line.partition("=")
                    app_title = val.strip().lower()
                elif line.startswith("Exec=") and not exec_cmd:
                    _, _, val = line.partition("=")
                    exec_cmd, _, _ = val.strip().partition(" ")
                elif line.startswith("Terminal=true"):
                    needs_term = True
            if name == app_title or name in app_title:
                binary_path = shutil.which(exec_cmd)
                if binary_path:
                    speak(f"Opening {app_title}")
                    if needs_term or os.path.basename(binary_path) not in gui_apps:
                        return open_in_terminal(f"{binary_path} --help || {binary_path} -h || {binary_path}", title=app_title.upper())
                    return launch_gui([binary_path])
        except Exception:
            continue
    speak(f"I could not find an app or tool named {name}")
    return False
def show_file_on_screen(filepath, title):
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        speak("Nothing has been generated yet.")
        return
    if shutil.which("zenity"):
        launch_gui(["zenity", "--text-info", f"--title={title}", f"--filename={filepath}", "--width=780", "--height=520"])
        return
    open_in_terminal(f"cat '{filepath}'", title=title)

def find_user_item(target_name):
    target = str(target_name).strip().lower()
    for folder in (f"{HOME}/Desktop", f"{HOME}/Downloads", f"{HOME}/Documents", HOME):
        if not os.path.exists(folder):
            continue
        for item in os.listdir(folder):
            item_low = item.lower()
            no_ext, _ = os.path.splitext(item_low)
            if target in (item_low, no_ext) or target.replace(" ", "_") == no_ext or (len(target) >= 3 and target in item_low):
                return os.path.join(folder, item)
    return None

def safe_delete(target_name):
    target = re.sub(r"^(file|folder|the)\s+", "", str(target_name).strip().lower())
    if target in ("code", "last code", "saved code"):
        if os.path.exists(CODE_FILE):
            os.remove(CODE_FILE)
            speak("Deleted saved code.")
        else:
            speak("No saved code to delete.")
        return
    if target in ("command", "last command", "saved command"):
        if os.path.exists(CMD_FILE):
            os.remove(CMD_FILE)
            speak("Deleted saved command.")
        else:
            speak("No saved command to delete.")
        return
    if target in {"desktop", "downloads", "documents", "hey-kali", "venv", ".config", ".ssh"}:
        speak("For safety, I cannot delete main folders.")
        return
    found_path = find_user_item(target)
    if found_path:
        import urllib.parse, datetime
        trash_files = f"{HOME}/.local/share/Trash/files"
        trash_info = f"{HOME}/.local/share/Trash/info"
        os.makedirs(trash_files, exist_ok=True)
        os.makedirs(trash_info, exist_ok=True)
        base = os.path.basename(found_path)
        trash_name = f"{int(time.time())}_{base}"
        shutil.move(found_path, os.path.join(trash_files, trash_name))
        del_date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        info_content = f"[Trash Info]\nPath={urllib.parse.quote(found_path)}\nDeletionDate={del_date}\n"
        open(os.path.join(trash_info, f"{trash_name}.trashinfo"), "w").write(info_content)
        speak(f"Moved {base} to trash.")
        return
    speak(f"I could not find {target}.")

def create_user_item(raw_text):
    low = str(raw_text).strip().lower()
    is_folder = any(w in low for w in ("folder ", "directory "))
    clean_name = re.sub(r"\b(file|folder|directory|called|named)\b", "", low).strip().replace(" ", "_")
    if not clean_name:
        speak("Please tell me the name to create.")
        return
    if is_folder:
        os.makedirs(os.path.join(f"{HOME}/Desktop", clean_name), exist_ok=True)
        speak(f"Created folder {clean_name} on Desktop.")
    else:
        if "." not in clean_name:
            clean_name += ".txt"
        open(os.path.join(f"{HOME}/Desktop", clean_name), "a").close()
        speak(f"Created file {clean_name} on Desktop.")

def move_user_item(raw_text):
    low = str(raw_text).lower()
    if " to " not in low:
        speak("Say move filename to destination folder.")
        return
    src_raw, _, dest_raw = low.partition(" to ")
    src_name = src_raw.replace("file ", "").strip()
    dest_name = dest_raw.replace("folder ", "").strip()
    dest_map = {"desktop": f"{HOME}/Desktop", "downloads": f"{HOME}/Downloads", "documents": f"{HOME}/Documents", "home": HOME}
    if dest_name not in dest_map:
        speak(f"Unknown destination {dest_name}.")
        return
    found_path = find_user_item(src_name)
    if not found_path:
        speak(f"I could not find {src_name}.")
        return
    os.makedirs(dest_map[dest_name], exist_ok=True)
    base = os.path.basename(found_path)
    shutil.move(found_path, os.path.join(dest_map[dest_name], base))
    speak(f"Moved {base} to {dest_name}.")

def record_and_transcribe():
    t0 = time.time()
    print("Listening...", flush=True)
    frames = []

    # Measure background noise for 0.12s
    noise_vals = []
    for _ in range(2):
        d = mic_stream.read(CHUNK, exception_on_overflow=False)
        frames.append(d)
        noise_vals.append(float(np.sqrt(np.mean(np.frombuffer(d, dtype=np.int16).astype(np.float32) ** 2))))
    # Higher multiplier (2.1x) prevents fan noise from keeping the mic open for 5.5s
    threshold = max(480.0, (sum(noise_vals) / len(noise_vals)) * 1.75)

    started = False
    silent_chunks = 0
    max_chunks = int(RATE / CHUNK * 5.0)    # Hard cap: 3.2s max
    silence_limit = int(RATE / CHUNK * 0.48) # Stop 0.3s after you finish speaking

    for _ in range(max_chunks):
        d = mic_stream.read(CHUNK, exception_on_overflow=False)
        frames.append(d)
        rms = float(np.sqrt(np.mean(np.frombuffer(d, dtype=np.int16).astype(np.float32) ** 2)))
        if rms > threshold:
            started = True
            silent_chunks = 0
        elif started:
            silent_chunks += 1
            if silent_chunks >= silence_limit:
                break

    rec_time = time.time() - t0
    raw_bytes = b"".join(frames)

    t1 = time.time()
    is_online = False
    try:
        import socket
        with socket.create_connection(("8.8.8.8", 53), timeout=0.25):
            is_online = True
    except Exception:
        is_online = False

    if is_online:
      try:
        text = google_rec.recognize_google(sr.AudioData(raw_bytes, RATE, 2), language="en-KE")
        if text.strip():
            print(f"[Timing] Rec: {rec_time:.2f}s | Google STT: {time.time() - t1:.2f}s", flush=True)
            return text.strip()
      except Exception:
        pass

    audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = whisper.transcribe(audio_np, beam_size=1, initial_prompt="Hey Kali Linux commands: sudo apt update, apt upgrade, turn wifi on, turn wifi off, guard my laptop, nmap, ifconfig, iwconfig, systemctl, whoami.")
    print(f"[Timing] Rec: {rec_time:.2f}s | Whisper STT: {time.time() - t1:.2f}s", flush=True)
    return " ".join([seg.text for seg in segments]).strip()

_ACTION_VERBS_RE = re.compile(
    r"^(?:open|close|write|right|type|dictate|andika|play|pause|resume|continue|next|previous|turn|switch|enable|disable|"
    r"connect|disconnect|pair|volume|increase|decrease|mute|unmute|brightness|take|screenshot|"
    r"run|osint|do\s+osint|investigate|background\s+check|scan|list|show|display|check|battery|"
    r"lock|sleep|suspend|shutdown|shut\s+down|reboot|restart|update|upgrade|set|remind|wake|"
    r"call|voice\s+call|send|create|make|move|delete|remove|guard|stop|watch|start|hash|decode|"
    r"translate|what|who|search|google|youtube|undercover|refresh|identify|fungua|funga|washa|zima)\b",
    re.I
)

def _split_chained_commands(raw_q):
    s = str(raw_q).strip()
    low = s.lower()
    # Keep single-intent search/shell/timer phrases intact
    if low.startswith(("write ", "right ", "type ", "dictate ", "andika ", "search ", "google ", "youtube ", "run sudo ", "run apt ", "remind me in ", "set a timer ")):
        return [s]
    parts = re.split(r"\s+(?:and\s+then|and|then)\s+", s, flags=re.I)
    if len(parts) <= 1:
        return [s]
    # Only split when every subsequent segment starts with a recognizable action verb
    if all(_ACTION_VERBS_RE.match(p.strip(" .!?")) for p in parts[1:]):
        return [p.strip(" .!?") for p in parts if p.strip(" .!?")]
    return [s]

def handle_query(query, _chained=False):
    if not _chained:
        sub_cmds = _split_chained_commands(query)
        if len(sub_cmds) > 1:
            for idx_c, sub_q in enumerate(sub_cmds):
                if idx_c > 0:
                    time.sleep(0.35)
                handle_query(sub_q, _chained=True)
            return
    if handle_extra(query, speak, launch_gui, GUI_ENV if 'GUI_ENV' in globals() else os.environ.copy()):
        return
    q_lower = str(query).lower().strip()
    _, _, rest = query.partition(" ")
    rest = rest.strip()

    if any(w in q_lower for w in ("goodnight", "good night", "lala salama")):
        speak("Goodnight! Shutting down now.", allow_interrupt=False)
        subprocess.run(["systemctl", "poweroff"])
        return
    if any(w in q_lower for w in ("sleep", "suspend", "sleep mode", "put laptop to sleep")):
        speak("Putting the laptop to sleep now.", allow_interrupt=False)
        subprocess.run(["systemctl", "suspend"])
        return
    if any(w in q_lower for w in ("shutdown", "shut down", "power off", "turn off computer", "turn off laptop", "zima laptop", "zima kompyuta")):
        speak("Shutting down now.")
        subprocess.run(["systemctl", "poweroff"])
        return
    if any(w in q_lower for w in ("reboot", "restart system", "restart computer", "restart laptop")):
        speak("Rebooting now.")
        subprocess.run(["systemctl", "reboot"])
        return
    if any(w in q_lower for w in ("lock screen", "lock computer", "lock desktop")):
        speak("Locking screen.")
        launch_gui(["loginctl", "lock-session"])
        return
    if any(w in q_lower for w in ("update system", "system update", "update kali", "upgrade system")):
        speak("Opening terminal to update Kali.")
        open_in_terminal("sudo apt update && sudo apt upgrade -y", title="System Update")
        return
    if any(w in q_lower for w in ("my ip", "ip address", "what is my ip")):
        ip_out = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip()
        speak(f"Your local IP is {ip_out if ip_out else 'not connected'}.")
        return
    if any(w in q_lower for w in ("display code", "show code", "open code", "view code", "display this code", "show this", "display this")):
        speak("Displaying code")
        show_file_on_screen(CODE_FILE, "Generated Code")
        return
    if any(w in q_lower for w in ("display command", "show command", "view command", "open command")):
        speak("Displaying command")
        show_file_on_screen(CMD_FILE, "Drafted Command")
        return
    if q_lower.startswith(("delete ", "remove ", "trash ")) and rest:
        safe_delete(rest)
        return
    if q_lower.startswith(("create ", "add ", "make ", "new ")) and rest and not any(w in q_lower for w in ("code", "script", "program", "function")):
        create_user_item(rest)
        return
    if q_lower.startswith("move ") and rest:
        move_user_item(rest)
        return
    if q_lower.startswith("run ") and rest:
        if len(rest.split()) == 1 and shutil.which(rest.lower()):
            open_any_app(rest)
            return
        speak("Preparing command in terminal.")
        cmd_to_run = re.sub(r"^```[a-zA-Z]*\s*|```$", "", subprocess.run(["/usr/bin/sgpt", "--shell", "--no-interaction", rest], capture_output=True, text=True).stdout.strip()).strip("`'\n ")
        if cmd_to_run:
            with open(CMD_FILE, "w") as f:
                f.write(cmd_to_run + "\n")
            safe_cmd = cmd_to_run.replace('"', '\\"')
            open_in_terminal(f"echo 'Command: {safe_cmd}'; echo 'Running in 5s (Ctrl+C to cancel)...'; sleep 5; {cmd_to_run}", title="Voice Runner")
        else:
            speak("Could not build command.")
        return
    if q_lower.startswith(("open ", "launch ", "start ")) and rest:
        open_any_app(rest)
        return
    if any(word in q_lower for word in ("code", "script", "program", "function", "write a ", "generate ", "create a ")):
        speak("Generating code, please wait.")
        generated_code = subprocess.run(["/usr/bin/sgpt", "--code", query], capture_output=True, text=True).stdout.strip()
        if generated_code:
            with open(CODE_FILE, "w") as f:
                f.write(generated_code + "\n")
            speak("Code is ready.")
            show_file_on_screen(CODE_FILE, "Generated Code")
        else:
            speak("Could not generate code.")
        return
    if q_lower.startswith(("command ", "draft ", "how do i ")):
        clean_task = rest if rest else query
        drafted_cmd = subprocess.run(["/usr/bin/sgpt", "--shell", "--no-interaction", clean_task], capture_output=True, text=True).stdout.strip()
        if drafted_cmd:
            with open(CMD_FILE, "w") as f:
                f.write(drafted_cmd + "\n")
            speak(f"Drafted command: {drafted_cmd}")
            show_file_on_screen(CMD_FILE, "Drafted Command")
        return

    # Ultra-Fast & Ultra-Accurate Live Web-Grounded Gemma3:1b Streaming Q&A
    live_facts = ""
    try:
        # Fetch live search snippets in ~0.35s so gemma3:1b has 100% real-world accuracy
        post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        s_req = urllib.request.Request(
            "https://html.duckduckgo.com/html/",
            data=post_data,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        )
        with urllib.request.urlopen(s_req, timeout=1.3) as sr_resp:
            html = sr_resp.read().decode("utf-8", errors="ignore")
        raw_snips = re.findall(r"class=.result-snippet.[^>]*>(.*?)</td>", html, flags=re.S)
        clean_snips = []
        for s in raw_snips[:3]:
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
            if len(txt) > 25:
                clean_snips.append(txt)
        if clean_snips:
            live_facts = " | ".join(clean_snips)[:650]
    except Exception:
        pass

    final_prompt = (
        f"Live search facts: {live_facts}\n\nQuestion: {query}\nAnswer accurately in 1 or 2 short spoken sentences:"
        if live_facts else
        f"Question: {query}\nAnswer accurately in 1 or 2 short spoken sentences:"
    )

    try:
        req = urllib.request.Request(
            f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate",
            data=json.dumps({
                "model": "gemma3:1b",
                "system": "You are Kali, a helpful voice assistant. Answer the user question directly and concisely in 1 or 2 short sentences. Never ask the user to provide facts.",
                "prompt": final_prompt,
                "stream": True,
                "keep_alive": -1,
                "options": {
                    "num_predict": 28,
                    "num_ctx": 512,
                    "num_thread": 2,
                    "temperature": 0.1,
                    "top_k": 15
                }
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        sentence_buf = ""
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                chunk = json.loads(raw_line.decode("utf-8"))
                token = chunk.get("response", "")
                sentence_buf += token
                if any(p in token for p in (".", "!", "?")) and len(sentence_buf.strip()) > 10:
                    if speak(sentence_buf.strip()):
                        return
                    sentence_buf = ""
                if chunk.get("done"):
                    break
        if sentence_buf.strip():
            speak(sentence_buf.strip())
    except Exception as e:
        print(f"[Gemma error] {e}", flush=True)
        speak("I could not process that right now.")

print("Ready! Say 'Hey Kali'...", flush=True)
barge_in = False

while True:
    try:
        triggered = False
        if barge_in:
            triggered = True
            barge_in = False
        else:
            data = mic_stream.read(CHUNK, exception_on_overflow=False)
            if wake_rec.AcceptWaveform(data):
                heard_wake = json.loads(wake_rec.Result()).get("text", "").strip().lower()
                if heard_wake == "hey kali":
                    triggered = True

        if triggered:
            wake_rec.Reset()
            mic_stream.stop_stream()
            instant_yes()
            mic_stream.start_stream()

            user_query = record_and_transcribe()
            if user_query:
                print(f"You: {user_query}", flush=True)
                mic_stream.stop_stream()
                try:
                    orig_speak = speak
                    interrupted_flag = {"val": False}

                    def tracked_speak(msg, allow_interrupt=True):
                        res = orig_speak(msg, allow_interrupt=allow_interrupt)
                        if res:
                            interrupted_flag["val"] = True
                        return res

                    globals()["speak"] = tracked_speak
                    handle_query(user_query)
                    globals()["speak"] = orig_speak

                    if interrupted_flag["val"]:
                        barge_in = True
                except Exception as e:
                    globals()["speak"] = orig_speak
                    print(f"Command error: {e}", flush=True)
                    orig_speak("Sorry, something went wrong with that command.", allow_interrupt=False)
                mic_stream.start_stream()

            wake_rec.Reset()
            if not barge_in:
                print("Ready! Say 'Hey Kali'...", flush=True)
    except Exception as loop_err:
        print(f"Loop error: {loop_err}", flush=True)
        time.sleep(0.5)
