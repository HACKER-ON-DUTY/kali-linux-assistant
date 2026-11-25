def _obex_dbus_send(mac_addr, file_path, env_bt=None):
    import re as _re, time as _time
    abs_f = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.isfile(abs_f):
        print(f"[BT D-Bus] File not found: {abs_f}", flush=True)
        return False
    e = dict(env_bt or os.environ)
    e.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
    subprocess.run(["systemctl", "--user", "start", "obex"], env=e, capture_output=True)
    subprocess.run(["bluetoothctl", "trust", mac_addr], env=e, capture_output=True)
    sess_res = subprocess.run(
        ["gdbus", "call", "--session", "--dest", "org.bluez.obex", "--object-path", "/org/bluez/obex",
         "--method", "org.bluez.obex.Client1.CreateSession", mac_addr, "{'Target': <'opp'>}"],
        env=e, capture_output=True, text=True
    )
    m = _re.search(r"(/org/bluez/obex/client/session\d+)", sess_res.stdout)
    if not m:
        print(f"[BT D-Bus] CreateSession failed: {sess_res.stderr.strip()}", flush=True)
        return False
    sess_path = m.group(1)
    try:
        send_res = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.bluez.obex", "--object-path", sess_path,
             "--method", "org.bluez.obex.ObjectPush1.SendFile", abs_f],
            env=e, capture_output=True, text=True
        )
        tm = _re.search(r"(/org/bluez/obex/client/session\d+/transfer\d+)", send_res.stdout)
        if not tm:
            print(f"[BT D-Bus] SendFile failed: {send_res.stderr.strip()}", flush=True)
            return False
        t_path = tm.group(1)
        for _ in range(300):
            _time.sleep(0.5)
            st = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.bluez.obex", "--object-path", t_path,
                 "--method", "org.freedesktop.DBus.Properties.Get", "org.bluez.obex.Transfer1", "Status"],
                env=e, capture_output=True, text=True
            ).stdout.lower()
            if "complete" in st:
                print(f"[BT D-Bus] Transfer complete: {abs_f}", flush=True)
                return True
            if "error" in st or not st.strip():
                print(f"[BT D-Bus] Transfer ended with status: {st.strip()}", flush=True)
                return False
        return False
    finally:
        subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.bluez.obex", "--object-path", "/org/bluez/obex",
             "--method", "org.bluez.obex.Client1.RemoveSession", sess_path],
            env=e, capture_output=True
        )

import datetime as _dt
import os, re, sys, json, time, glob, math, wave, base64, hashlib, shutil, signal, datetime, threading, subprocess, urllib.request, urllib.parse
import numpy as np
import os
import sys
import glob
import shutil
import signal
import hashlib
import subprocess
import urllib.parse
import threading, datetime
import time
import shlex
import urllib.request
import requests
_HTTP = requests.Session()
_HTTP.headers.update({'User-Agent': 'KaliVoiceAssistant/1.0 (https://localhost; hacker@localhost)'})
import asyncio, wave
import json, urllib.request
import base64, hashlib, shutil
import datetime, os, re, shutil, subprocess, urllib.parse

HOME = os.path.expanduser("~")

def _play_youtube_direct(search_query, launch_gui):
    def _bg_open():
        s = chr(47)
        dot = chr(46)
        yt_domain = dot.join(["www", "youtube", "com"])
        yt_host = "https:" + s + s + yt_domain
        q_enc = urllib.parse.quote_plus(search_query)
        watch_url = ""
        try:
            res = _HTTP.get(
                f"{yt_host}{s}results?search_query={q_enc}",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"},
                cookies={"CONSENT": "YES+cb"},
                timeout=4
            )
            m_vid = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', res.text)
            if m_vid:
                watch_url = f"{yt_host}{s}watch?v={m_vid.group(1)}&autoplay=1"
        except Exception as _ye:
            print(f"[YT resolver] {_ye}", flush=True)

        if not watch_url:
            watch_url = f"{yt_host}{s}results?search_query={q_enc}"

        print(f"[YT Launch] {watch_url}", flush=True)
        launch_gui(["xdg-open", watch_url])

        # Wait 3.5s for YouTube player to render in Firefox, then trigger playback automatically
        time.sleep(3.5)
        if shutil.which("playerctl"):
            subprocess.run(["playerctl", "play"])
        if shutil.which("xdotool"):
            env_x = os.environ.copy()
            env_x["DISPLAY"] = ":0"
            env_x["XAUTHORITY"] = f"{HOME}/.Xauthority"
            subprocess.run(["xdotool", "key", "k"], env=env_x)

    threading.Thread(target=_bg_open, daemon=True).start()

def handle_extra(query, speak, launch_gui, gui_env):
    q = str(query).lower().strip(" .!?")
    _rt_env = os.environ.copy()
    _rt_env["DISPLAY"] = ":0"
    _rt_env["XAUTHORITY"] = f"{HOME}/.Xauthority"
    _rt_env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    _rt_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"

    # Cursor Dictation / Typing Handler ("write <text>", "type <text>", "write <text> and press enter")
    m_write = re.match(r"^(?:write|right|type|dictate|andika)\s+(.+)$", str(query).strip(), flags=re.I)
    if m_write:
        text_to_type = m_write.group(1).strip()
        press_enter = False
        m_ent = re.search(r"\s+(?:and\s+)?(?:press|hit)\s+(?:enter|return|submit)$", text_to_type, flags=re.I)
        if m_ent:
            press_enter = True
            text_to_type = text_to_type[:m_ent.start()].strip()
        if not text_to_type:
            speak("What would you like me to write?")
            return True
        if not shutil.which("xdotool"):
            speak("xdotool is not installed for typing.")
            return True
        try:
            if text_to_type.isascii() and "\n" not in text_to_type:
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text_to_type],
                    env=_rt_env, check=False
                )
            elif shutil.which("xclip"):
                subprocess.run(["xclip", "-selection", "clipboard"], input=text_to_type, text=True, env=_rt_env)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], env=_rt_env, check=False)
            else:
                subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text_to_type],
                    env=_rt_env, check=False
                )
            if press_enter:
                time.sleep(0.08)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], env=_rt_env, check=False)
            speak("Done.")
        except Exception as _we:
            print(f"[Write error] {_we}", flush=True)
            speak("Sorry, I could not type that text.")
        return True

    # OSINT Worker Integration
    m_osint = re.match(r"^(?:run\s+osint(?:\s+on)?|osint(?:\s+on)?|do\s+osint(?:\s+on)?|investigate|background\s+check(?:\s+on)?)\s+(.+)$", q)
    if m_osint:
        target_raw = re.sub(r"^(?:run\s+osint(?:\s+on)?|osint(?:\s+on)?|do\s+osint(?:\s+on)?|investigate|background\s+check(?:\s+on)?)\s+", "", str(query).strip(" .!?"), flags=re.I).strip()
        if target_raw:
            speak(f"Running OSINT scan on {target_raw}. I will save the report to your desktop.")
            def _bg_osint(t=target_raw):
                try:
                    py_bin = f"{os.path.dirname(os.path.abspath(__file__))}/venv/bin/python3"
                    worker = f"{os.path.dirname(os.path.abspath(__file__))}/osint_worker.py"
                    res = subprocess.run([py_bin, worker, t], capture_output=True, text=True, timeout=60)
                    out = res.stdout or ""
                    m_saved = re.search(r"Saved:\s*(.+)", out)
                    if m_saved and os.path.exists(m_saved.group(1).strip()):
                        rpt = m_saved.group(1).strip()
                        speak(f"OSINT report for {t} is ready and saved on your desktop.")
                        launch_gui(["xdg-open", rpt])
                    else:
                        speak(f"OSINT scan for {t} finished, check your desktop.")
                except Exception as _oe:
                    print(f"[OSINT error] {_oe}", flush=True)
                    speak("Sorry, the OSINT scan encountered an error.")
            threading.Thread(target=_bg_osint, daemon=True).start()
            return True


    # 00-LATEST. Kiswahili, Flexible Wi-Fi, Media Controls & Universal Window Closer
    sw_map = [
        (("habari yako", "habari", "mambo", "niaje"), "hello how are you"),
        (("fungua firefox",), "open firefox"), (("fungua terminal",), "open terminal"),
        (("fungua faili",), "open files"), (("funga firefox",), "close firefox"),
        (("funga terminal",), "close terminal"), (("funga faili",), "close files"),
        (("washa wifi", "fungua wifi"), "wifi turn on"), (("zima wifi",), "wifi turn off"),
        (("washa bluetooth",), "turn bluetooth on"), (("zima bluetooth",), "turn bluetooth off"),
        (("ongeza sauti", "sauti juu"), "volume up"), (("punguza sauti", "sauti chini"), "volume down"),
        (("nyamaza", "zima sauti"), "mute"), (("rudisha sauti", "washa sauti"), "unmute"),
        (("piga skrini",), "take a screenshot"), (("piga picha",), "take a picture"),
        (("linda laptop",), "guard my laptop"), (("acha kulinda",), "stop guarding"),
        (("simamisha wimbo", "simamisha video"), "pause"), (("endelea kucheza",), "resume"),
        (("wimbo ujao", "video ijayo"), "play next"), (("saa ngapi",), "what time is it"),
    ]
    for sw_keys, en_cmd in sw_map:
        if any(k in q for k in sw_keys):
            q, query = en_cmd, en_cmd
            break

    q_w = q.replace("why five", "wifi").replace("why fi", "wifi").replace("wi fi", "wifi").replace("wi-fi", "wifi")
    if q_w in ("wifi turn on", "wifi on", "turn wifi on", "turn on wifi", "switch on wifi", "enable wifi"):
        subprocess.Popen(["nmcli", "radio", "wifi", "on"], env=_rt_env)
        speak("Wi-Fi turned on.")
        return True
    if q_w in ("wifi turn off", "wifi off", "turn wifi off", "turn off wifi", "switch off wifi", "disable wifi"):
        subprocess.Popen(["nmcli", "radio", "wifi", "off"], env=_rt_env)
        speak("Wi-Fi turned off.")
        return True

    if q in ("pause", "resume", "play", "continue") or any(p in q for p in ("pause music", "pause video", "pause song", "resume music", "resume video", "resume song", "continue playing")):
        if shutil.which("playerctl") and subprocess.run(["playerctl", "status"], env=_rt_env, capture_output=True).returncode == 0:
            subprocess.run(["playerctl", "play-pause"], env=_rt_env)
        elif shutil.which("xdotool"):
            for cls in ("firefox", "chromium", "google-chrome", "vlc"):
                wids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], env=_rt_env, capture_output=True, text=True).stdout.split()
                if wids:
                    subprocess.run(["xdotool", "windowactivate", "--sync", wids.pop(0)], env=_rt_env, capture_output=True)
                    break
            subprocess.run(["xdotool", "key", "space"], env=_rt_env)
        speak("Playback toggled.")
        return True

    if q in ("next", "skip") or any(p in q for p in ("play next", "next track", "next song", "next video", "skip song", "skip track")):
        if shutil.which("playerctl") and subprocess.run(["playerctl", "status"], env=_rt_env, capture_output=True).returncode == 0:
            subprocess.run(["playerctl", "next"], env=_rt_env)
        elif shutil.which("xdotool"):
            for cls in ("firefox", "chromium", "google-chrome"):
                wids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], env=_rt_env, capture_output=True, text=True).stdout.split()
                if wids:
                    subprocess.run(["xdotool", "windowactivate", "--sync", wids.pop(0)], env=_rt_env, capture_output=True)
                    break
            subprocess.run(["xdotool", "key", "shift+N"], env=_rt_env)
        speak("Playing next track.")
        return True

    if q.startswith(("close ", "exit ", "quit ")) and len(q.split()) >= 2:
        c_tgt = re.sub(r"^(?:close|exit|quit)\s+(?:the\s+|my\s+|app\s+|application\s+|window\s+|folder\s+|file\s+)?", "", q).strip(" .!?")
        if c_tgt in ("tab", "this tab", "current tab") and shutil.which("xdotool"):
            subprocess.run(["xdotool", "key", "ctrl+w"], env=_rt_env)
            speak("Closed tab.")
            return True
        if c_tgt in ("all", "everything", "all windows", "all apps") and shutil.which("wmctrl"):
            for w in subprocess.run(["wmctrl", "-l"], env=_rt_env, capture_output=True, text=True).stdout.splitlines():
                parts = w.split()
                if parts and "xfce4-panel" not in w.lower() and "desktop" not in w.lower():
                    subprocess.Popen(["wmctrl", "-ic", parts.pop(0)], env=_rt_env)
            speak("Closed all open windows.")
            return True
        alias_map = {"fire fox": "firefox", "browser": "firefox", "files": "thunar", "file": "thunar", "console": "qterminal", "terminal": "qterminal", "editor": "mousepad", "notepad": "mousepad", "code": "zenity", "music": "vlc", "video": "vlc"}
        s_key = alias_map.get(c_tgt, c_tgt)
        closed_any = False
        if shutil.which("wmctrl"):
            for line in subprocess.run(["wmctrl", "-lx"], env=_rt_env, capture_output=True, text=True).stdout.splitlines():
                low_l = line.lower()
                if "xfce4-panel" not in low_l and "xfdesktop" not in low_l and (s_key in low_l or c_tgt in low_l):
                    subprocess.Popen(["wmctrl", "-ic", line.split().pop(0)], env=_rt_env)
                    closed_any = True
        if not closed_any and s_key not in ("thunar", "python", "python3", "kali"):
            closed_any = (subprocess.run(["pkill", "-TERM", "-i", s_key], env=_rt_env).returncode == 0)
        speak(f"Closed {c_tgt}." if closed_any else f"No open {c_tgt} window was found.")
        return True

    # 0J. Smart Wi-Fi Channel & Auto-SSID Tuner ("set wifi to channel 6", "tune wifi to <SSID>")
    if any(p in q for p in ("set wifi to channel", "set wi-fi to channel", "switch wifi to channel", "change wifi channel to", "tune wifi to", "set wifi to ", "set wi-fi to ", "match wifi channel for", "detect channel for")):
        # 1. Auto-detect active wireless interface (prefer monitor/wlan0mon if present, else primary wlan)
        iw_devs = subprocess.run(["iw", "dev"], capture_output=True, text=True).stdout
        ifaces = re.findall(r"Interface\s+([a-zA-Z0-9_-]+)", iw_devs)
        if not ifaces:
            speak("No wireless network adapter was found.")
            return True
        mon_ifaces = [i for i in ifaces if "mon" in i.lower()]
        wlan = mon_ifaces.pop(0) if mon_ifaces else ifaces.pop(0)

        # 2. Check if user specified an explicit channel number ("set wifi to channel 6")
        word_nums = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13}
        q_norm = q
        for w_k, w_v in word_nums.items():
            q_norm = re.sub(rf"\b{w_k}\b", str(w_v), q_norm)

        m_ch = re.search(r"\bchannel\s+(\d{1,3})\b", q_norm)
        target_ch = ""
        matched_ssid = ""

        if m_ch:
            target_ch = m_ch.group(1)
        else:
            # 3. Auto-detect channel from nearby Wi-Fi scan by SSID name or ordinal ("first wifi", "second wifi")
            target_name = re.sub(r"^(?:tune wifi to|set wifi to|set wi-fi to|match wifi channel for|detect channel for)\s+(?:the\s+)?", "", q).strip()
            scan_out = subprocess.run(["nmcli", "-t", "-f", "SSID,CHAN", "dev", "wifi", "list"], capture_output=True, text=True).stdout.strip()
            networks = []
            for line in scan_out.splitlines():
                if ":" in line:
                    s_name, _, s_chan = line.rpartition(":")
                    s_name = s_name.strip()
                    s_chan = s_chan.strip()
                    if s_name and s_chan.isdigit():
                        networks.append((s_name, s_chan))

            if not networks:
                speak("Could not scan nearby Wi-Fi channels right now. Make sure Wi-Fi radio is enabled.")
                return True

            if any(w in target_name for w in ("first", "1st", "strongest", "top")):
                matched_ssid, target_ch = networks.pop(0)
            elif any(w in target_name for w in ("second", "2nd")) and len(networks) >= 2:
                matched_ssid, target_ch = networks.pop(1)
            else:
                for s_name, s_chan in networks:
                    if target_name in s_name.lower():
                        matched_ssid, target_ch = s_name, s_chan
                        break

            if not target_ch:
                speak(f"Could not find a nearby Wi-Fi network matching {target_name}.")
                return True

        # 4. Apply channel to adapter via `iw`
        res = subprocess.run(["sudo", "-n", "iw", "dev", wlan, "set", "channel", str(target_ch)], capture_output=True, text=True)
        if res.returncode == 0:
            if matched_ssid:
                speak(f"Detected {matched_ssid} on channel {target_ch}, and tuned {wlan} to channel {target_ch}.")
            else:
                speak(f"Set {wlan} to channel {target_ch}.")
        else:
            speak(f"Could not set {wlan} to channel {target_ch}. Make sure the adapter is not locked to a connected network.")
        return True

    # 0K. Offline Whisper Wi-Fi & Bluetooth Normalizer ("turn why five off", "turn wifi on/off")
    q_radio = q.replace("why five", "wifi").replace("why fi", "wifi").replace("wi fi", "wifi").replace("wi-fi", "wifi").replace("blue tooth", "bluetooth")
    if (
        not q_radio.startswith(("connect ", "pair ", "disconnect ", "join ", "switch wifi"))
        and any(w in q_radio for w in ("wifi", "bluetooth"))
        and (
            any(w in q_radio for w in ("turn on", "turn off", "switch on", "switch off", "enable", "disable"))
            or q_radio.endswith((" on", " off"))
        )
    ):
        turn_on = any(w in q_radio for w in ("turn on", "switch on", "enable")) or q_radio.endswith(" on")
        if "wifi" in q_radio:
            state = "on" if turn_on else "off"
            subprocess.run(["nmcli", "radio", "wifi", state], env=_rt_env)
            speak(f"Wi-Fi turned {state}.")
            return True
        if "bluetooth" in q_radio:
            if turn_on:
                subprocess.run(["rfkill", "unblock", "bluetooth"], env=_rt_env)
                if shutil.which("bluetoothctl"):
                    subprocess.run(["bluetoothctl", "power", "on"], env=_rt_env)
                speak("Bluetooth turned on.")
            else:
                if shutil.which("bluetoothctl"):
                    subprocess.run(["bluetoothctl", "power", "off"], env=_rt_env)
                subprocess.run(["rfkill", "block", "bluetooth"], env=_rt_env)
                speak("Bluetooth turned off.")
            return True

    # 0L. Direct Clean Terminal Command Runner ("run sudo apt update", "run ls -la", etc. — Online + Offline Phonetic Fix)
    if q.startswith("run "):
        raw_cmd = str(query).strip()[4:].strip(" .!?`'")
        # Normalize common offline Whisper phonetic transcriptions of Linux commands & flags
        phonetic_fixes = [
            (r"^(?:pseudo|sue do|so do|sudu|sodo|sue due|zoo do)\b", "sudo"),
            (r"\b(?:app|at|act|aptitude|up to)\s+(update|upgrade|install|remove|purge|search)\b", r"apt \1"),
            (r"\bup\s+date\b", "update"),
            (r"\bup\s+grade\b", "upgrade"),
            (r"\b(?:and map|in map|end map)\b", "nmap"),
            (r"\b(?:if config|i f config)\b", "ifconfig"),
            (r"\b(?:i w config|iw config)\b", "iwconfig"),
            (r"\b(?:system control|system ctl)\b", "systemctl"),
            (r"\b(?:who am i)\b", "whoami"),
            (r"\b(?:list files|l s)\b", "ls -la"),
            (r"\bdash\s+([a-zA-Z0-9]+)\b", r"-\1"),
            (r"\bminus\s+([a-zA-Z0-9]+)\b", r"-\1")
        ]
        for pat, rep in phonetic_fixes:
            raw_cmd = re.sub(pat, rep, raw_cmd, flags=re.IGNORECASE)

        first_tok = next(iter(raw_cmd.split()), "").lower()
        direct_bins = {
            "sudo", "apt", "apt-get", "ls", "ip", "ifconfig", "iwconfig", "iw",
            "ping", "nmap", "whoami", "uname", "df", "free", "ps", "top", "htop",
            "cat", "systemctl", "journalctl", "git", "python3", "bash", "ss", "netstat"
        }
        if first_tok in direct_bins or shutil.which(first_tok):
            clean_cmd = raw_cmd.replace("`", "").replace("'", "")
            open(f"{os.path.dirname(os.path.abspath(__file__))}/last_command.txt", "w").write(clean_cmd + "\n")
            speak(f"Running {clean_cmd} in terminal.")
            bash_script = f"echo 'Command: {clean_cmd}'; echo 'Running in 5s (Ctrl+C to cancel)...'; sleep 5; {clean_cmd}; exec bash"
            term_bin = next((t for t in ("qterminal", "xfce4-terminal", "gnome-terminal", "mate-terminal", "konsole", "x-terminal-emulator") if shutil.which(t)), "")
            if term_bin:
                launch_gui([term_bin, "-e", f"bash -c \"{bash_script}\""])
            else:
                speak("No terminal emulator found on this system.")
            return True

    # 0M. 100% Offline Available Wi-Fi & Bluetooth Lister ("list wifi", "list bluetooth")
    q_norm_radio = q.replace("why five", "wifi").replace("why fi", "wifi").replace("wi fi", "wifi").replace("wi-fi", "wifi").replace("blue tooth", "bluetooth").replace("least ", "list ").replace("last ", "list ").replace("less ", "list ")
    if any(p in q_norm_radio for p in ("list wifi", "list available wifi", "show wifi", "show available wifi", "available wifi", "scan wifi", "nearby wifi")):
        wifi_table = ""
        names = []

        # Method 1: NetworkManager (nmcli)
        if shutil.which("nmcli"):
            res_nm = subprocess.run(
                ["nmcli", "-f", "SSID,SIGNAL,SECURITY,CHAN", "dev", "wifi", "list"],
                env=_rt_env, capture_output=True, text=True
            ).stdout.strip()
            if res_nm and len(res_nm.splitlines()) > 1:
                wifi_table = res_nm
                res_compact = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"],
                    env=_rt_env, capture_output=True, text=True
                ).stdout.strip()
                for line in res_compact.splitlines():
                    if ":" in line:
                        ssid = line.split(":", 1).pop(0).strip()
                        if ssid and ssid != "--" and ssid not in names:
                            names.append(ssid)

        # Method 2: Direct driver-level scan via `iw dev <iface> scan` (works even when nmcli returns empty)
        if not wifi_table and shutil.which("iw"):
            iw_devs = subprocess.run(["iw", "dev"], capture_output=True, text=True).stdout
            ifaces = re.findall(r"Interface\s+([a-zA-Z0-9_-]+)", iw_devs)
            if ifaces:
                wlan = ifaces.pop(0)
                scan_raw = subprocess.run(["sudo", "-n", "iw", "dev", wlan, "scan"], capture_output=True, text=True).stdout
                if not scan_raw:
                    scan_raw = subprocess.run(["iw", "dev", wlan, "scan"], capture_output=True, text=True).stdout
                rows = ["SSID                           SIGNAL      CHAN"]
                rows.append("-" * 50)
                cur_ssid, cur_sig, cur_ch = "", "", ""
                for line in scan_raw.splitlines():
                    s_line = line.strip()
                    if s_line.startswith("BSS "):
                        if cur_ssid and cur_ssid not in names:
                            names.append(cur_ssid)
                            rows.append(f"{cur_ssid:<30} {cur_sig:<11} {cur_ch}")
                        cur_ssid, cur_sig, cur_ch = "", "", ""
                    elif s_line.startswith("SSID:"):
                        cur_ssid = s_line.partition(":").pop(2).strip()
                    elif s_line.startswith("signal:"):
                        cur_sig = s_line.partition(":").pop(2).strip()
                    elif s_line.startswith("DS Parameter set: channel"):
                        cur_ch = s_line.rsplit(" ", 1).pop(-1).strip()
                if cur_ssid and cur_ssid not in names:
                    names.append(cur_ssid)
                    rows.append(f"{cur_ssid:<30} {cur_sig:<11} {cur_ch}")
                if len(rows) > 2:
                    wifi_table = "\n".join(rows)

        if not wifi_table:
            speak("No Wi-Fi networks were found. Check if your adapter is in monitor mode or Wi-Fi is switched off.")
            return True

        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(out_f, "w", encoding="utf-8").write("=== AVAILABLE WI-FI NETWORKS (OFFLINE SCAN) ===\n\n" + wifi_table + "\n")
        speak("Available Wi-Fi networks: " + (", ".join(names[:4]) if names else "listed on your screen") + ". Full table displayed.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Available Wi-Fi Networks", f"--filename={out_f}", "--width=720", "--height=420"])
        return True

    if any(p in q_norm_radio for p in ("list bluetooth", "list available bluetooth", "show bluetooth", "show available bluetooth", "available bluetooth", "scan bluetooth", "nearby bluetooth", "bluetooth devices")):
        if not shutil.which("bluetoothctl"):
            speak("Bluetooth tools are not installed.")
            return True
        subprocess.run(["rfkill", "unblock", "bluetooth"], env=_rt_env, capture_output=True)
        subprocess.run(["bluetoothctl", "power", "on"], env=_rt_env, capture_output=True)
        speak("Scanning for nearby Bluetooth devices for 4 seconds.")
        subprocess.run(["bluetoothctl", "--timeout", "4", "scan", "on"], env=_rt_env, capture_output=True, text=True)
        devs_out = subprocess.run(["bluetoothctl", "devices"], env=_rt_env, capture_output=True, text=True).stdout.strip()
        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(out_f, "w").write("=== AVAILABLE & PAIRED BLUETOOTH DEVICES (OFFLINE SCAN) ===\n\n" + (devs_out if devs_out else "No Bluetooth devices discovered.") + "\n")
        if devs_out:
            dev_names = [line.split(" ", 2)[2].strip() for line in devs_out.splitlines() if len(line.split(" ", 2)) >= 3]
            speak("Found Bluetooth devices: " + ", ".join(dev_names[:4]) + ". Full list is on your screen.")
        else:
            speak("No nearby Bluetooth devices were found.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Bluetooth Devices", f"--filename={out_f}", "--width=720", "--height=420"])
        return True

    # 0N. Priority Offline-Safe App, Folder & File Launcher ("open firefox", "open files", "open terminal", "open <file>")
    if q.startswith(("open ", "launch ", "start ")) and " " in q:
        raw_open = re.sub(r"^(?:open|launch|start)\s+(?:the\s+|my\s+)?", "", q).strip(" .!?")
        # Normalize common offline Whisper phonetic transcriptions
        open_phonetics = {
            "fire fox": "firefox", "fire focks": "firefox", "firebox": "firefox", "five fox": "firefox",
            "file": "files", "file manager": "files", "my files": "files", "folder": "files",
            "wire shark": "wireshark", "while shark": "wireshark",
            "meta sploit": "metasploit", "better sploit": "metasploit",
            "and map": "nmap", "in map": "nmap",
            "vs code": "code", "v s code": "code", "visual studio": "code",
            "text editor": "mousepad", "notepad": "mousepad", "note pad": "mousepad"
        }
        norm_open = open_phonetics.get(raw_open, raw_open)

        app_bins = {
            "terminal": ("qterminal", "xfce4-terminal", "gnome-terminal", "konsole", "x-terminal-emulator"),
            "firefox": ("firefox-esr", "firefox"),
            "browser": ("firefox-esr", "firefox", "chromium", "google-chrome"),
            "chrome": ("chromium", "google-chrome"),
            "files": ("thunar", "nautilus", "pcmanfm"),
            "wireshark": ("wireshark",),
            "burp": ("burpsuite",),
            "burp suite": ("burpsuite",),
            "metasploit": ("msfconsole",),
            "nmap": ("nmap",),
            "code": ("code",),
            "mousepad": ("mousepad", "gedit", "leafpad"),
            "settings": ("xfce4-settings-manager", "gnome-control-center"), "whatsapp": ("/snap/bin/whatsapp-electron", "whatsapp-electron", "whatsapp-for-linux")
        }

        if norm_open in app_bins:
            for b in app_bins[norm_open]:
                b_path = shutil.which(b)
                if b_path:
                    speak(f"Opening {norm_open}.")
                    if b in ("msfconsole", "nmap"):
                        term_b = next((t for t in ("qterminal", "xfce4-terminal", "gnome-terminal", "x-terminal-emulator") if shutil.which(t)), "")
                        if term_b:
                            launch_gui([term_b, "-e", f"bash -c '{b}; exec bash'"])
                    else:
                        launch_gui([b_path])
                    return True

        # Standard user directories ("open downloads", "open desktop", "open documents", "open pictures")
        std_dirs = {
            "desktop": f"{HOME}/Desktop",
            "downloads": f"{HOME}/Downloads", "download": f"{HOME}/Downloads",
            "documents": f"{HOME}/Documents", "document": f"{HOME}/Documents",
            "pictures": f"{HOME}/Pictures", "music": f"{HOME}/Music",
            "videos": f"{HOME}/Videos", "home": HOME
        }
        clean_dir_q = re.sub(r"^(?:folder|directory)\s+", "", norm_open).strip()
        if clean_dir_q in std_dirs and os.path.isdir(std_dirs[clean_dir_q]):
            speak(f"Opening {clean_dir_q}.")
            launch_gui(["xdg-open", std_dirs[clean_dir_q]])
            return True

        # Fuzzy file/folder search across Desktop, Downloads, Documents & Home ("open file <name>", "open <filename>")
        clean_item_q = re.sub(r"^(?:file|document|folder|directory)\s+", "", norm_open).strip().replace(" dot ", ".")
        if clean_item_q:
            for search_d in (f"{HOME}/Desktop", f"{HOME}/Downloads", f"{HOME}/Documents", HOME):
                if os.path.isdir(search_d):
                    for fn in os.listdir(search_d):
                        if fn.startswith("."):
                            continue
                        fn_low = fn.lower()
                        no_ext, _ = os.path.splitext(fn_low)
                        if clean_item_q in (fn_low, no_ext, fn_low.replace("_", " "), no_ext.replace("_", " ")) or (len(clean_item_q) >= 4 and clean_item_q in fn_low):
                            full_target = os.path.join(search_d, fn)
                            speak(f"Opening {fn}.")
                            launch_gui(["xdg-open", full_target])
                            return True

    # 0P. Cancel / Stop Active Video or File Download ("stop downloading", "cancel download")
    if any(p in q for p in ("stop downloading", "stop download", "cancel download", "cancel downloading", "abort download")):
        killed_yt = subprocess.run(["pkill", "-9", "-f", "yt-dlp"]).returncode == 0
        killed_curl = subprocess.run(["pkill", "-9", "-f", "curl -L"]).returncode == 0
        for junk in glob.glob("/tmp/*.part") + glob.glob("/tmp/*.ytdl") + glob.glob(f"{HOME}/Downloads/*.part"):
            try:
                os.remove(junk)
            except Exception:
                pass
        if killed_yt or killed_curl:
            speak("Download stopped and temporary files cleaned up.")
        else:
            speak("There is no active download running right now.")
        return True

    # 0R. 100% Offline Voice Wi-Fi Connect & Disconnect ("connect to wifi <SSID>", "connect to first wifi", "disconnect wifi")
    q_wifi_c = q.replace("why five", "wifi").replace("why fi", "wifi").replace("wi fi", "wifi").replace("wi-fi", "wifi").replace("fast wifi", "first wifi")
    if any(p in q_wifi_c for p in ("disconnect wifi", "disconnect from wifi", "disconnect wireless")):
        if not shutil.which("nmcli"):
            speak("NetworkManager is not available.")
            return True
        wifi_dev = subprocess.run(["nmcli", "-t", "-f", "DEVICE,TYPE", "dev"], env=_rt_env, capture_output=True, text=True).stdout
        wlan_iface = next((l.split(":").pop(0) for l in wifi_dev.splitlines() if ":wifi" in l), "")
        if wlan_iface:
            subprocess.run(["nmcli", "dev", "disconnect", wlan_iface], env=_rt_env, capture_output=True)
            speak("Wi-Fi disconnected.")
        else:
            speak("No active Wi-Fi interface found.")
        return True

    if (
        "bluetooth" not in q_wifi_c and "blue tooth" not in q_wifi_c and "device" not in q_wifi_c
        and (
            q_wifi_c.startswith(("connect to wifi ", "connect wifi to ", "connect wifi ", "join wifi ", "switch wifi to "))
            or (q_wifi_c.startswith("connect to ") and any(w in q_wifi_c for w in ("wifi", "internet", "network", "first", "1st", "second", "2nd", "third", "3rd")))
        )
    ):
        if not shutil.which("nmcli"):
            speak("NetworkManager is not available.")
            return True

        target_ssid = re.sub(
            r"^(?:connect to wifi|connect wifi to|connect wifi|join wifi|switch wifi to|connect to)\s+(?:the\s+|network\s+|wifi\s+)?",
            "", q_wifi_c
        ).strip(" .!?")
        target_ssid = re.sub(r"\s+(?:wifi|network)$", "", target_ssid).strip()

        if not target_ssid:
            speak("Which Wi-Fi network should I connect to?")
            return True

        subprocess.run(["nmcli", "radio", "wifi", "on"], env=_rt_env, capture_output=True)
        scan_out = subprocess.run(["nmcli", "-t", "-f", "SSID,SECURITY", "dev", "wifi", "list"], env=_rt_env, capture_output=True, text=True).stdout.strip()
        avail_nets = []
        seen_ssids = set()
        for line in scan_out.splitlines():
            if ":" in line:
                s_name, _, s_sec = line.rpartition(":")
                s_name = s_name.strip()
                if s_name and s_name != "--" and s_name not in seen_ssids:
                    seen_ssids.add(s_name)
                    avail_nets.append((s_name, s_sec.strip()))

        # Fallback: if scan cache is still warming up, populate from saved Wi-Fi connections
        if not avail_nets:
            saved_list = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"], env=_rt_env, capture_output=True, text=True).stdout
            for line in saved_list.splitlines():
                if ":802-11-wireless" in line:
                    c_name = line.split(":", 1).pop(0).strip()
                    if c_name and c_name not in seen_ssids:
                        seen_ssids.add(c_name)
                        avail_nets.append((c_name, "SAVED"))

        chosen_ssid = ""
        if any(w in target_ssid for w in ("first", "1st", "strongest", "top")) and avail_nets:
            chosen_ssid, _ = avail_nets.pop(0)
        elif any(w in target_ssid for w in ("second", "2nd")) and len(avail_nets) >= 2:
            chosen_ssid, _ = avail_nets.pop(1)
        elif any(w in target_ssid for w in ("third", "3rd")) and len(avail_nets) >= 3:
            chosen_ssid, _ = avail_nets.pop(2)
        else:
            for s_name, _ in avail_nets:
                if target_ssid in s_name.lower():
                    chosen_ssid = s_name
                    break

        if not chosen_ssid:
            saved_out = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"], env=_rt_env, capture_output=True, text=True).stdout
            for line in saved_out.splitlines():
                if ":802-11-wireless" in line:
                    c_name = line.split(":", 1).pop(0).strip()
                    if target_ssid in c_name.lower():
                        chosen_ssid = c_name
                        break

        if not chosen_ssid:
            speak(f"Could not find a Wi-Fi network matching {target_ssid}.")
            return True

        speak(f"Connecting to {chosen_ssid}.")
        # First try bringing up existing saved connection profile by name
        res_up = subprocess.run(["nmcli", "con", "up", chosen_ssid], env=_rt_env, capture_output=True, text=True, timeout=12)
        if res_up.returncode == 0:
            speak(f"Connected to {chosen_ssid}.")
            return True

        # Fallback: direct wifi connect (works for open networks or matching SSID profiles)
        res = subprocess.run(["nmcli", "dev", "wifi", "connect", chosen_ssid], env=_rt_env, capture_output=True, text=True, timeout=12)
        if res.returncode == 0 and "successfully activated" in res.stdout.lower():
            speak(f"Connected to {chosen_ssid}.")
            return True

        if shutil.which("zenity"):
            speak(f"Enter the Wi-Fi password for {chosen_ssid} on your screen.")
            pw_res = subprocess.run(
                ["zenity", "--password", f"--title=Wi-Fi Password: {chosen_ssid}"],
                env=_rt_env, capture_output=True, text=True
            )
            wifi_pw = pw_res.stdout.strip()
            if wifi_pw:
                res2 = subprocess.run(["nmcli", "dev", "wifi", "connect", chosen_ssid, "password", wifi_pw], env=_rt_env, capture_output=True, text=True, timeout=15)
                if res2.returncode == 0 and "successfully activated" in res2.stdout.lower():
                    speak(f"Connected to {chosen_ssid}.")
                else:
                    speak(f"Could not connect to {chosen_ssid}. Check the password and try again.")
            else:
                speak("Wi-Fi connection cancelled.")
        else:
            speak(f"Could not connect to {chosen_ssid} because a password is required.")
        return True

    # 0Q. 100% Offline Voice Bluetooth Connect & Disconnect ("connect to <device>", "disconnect bluetooth")
    if q.startswith(("connect bluetooth to ", "connect to bluetooth ", "connect to ", "pair with ")) or any(p in q for p in ("disconnect bluetooth", "disconnect from bluetooth", "disconnect device")):
        if not shutil.which("bluetoothctl"):
            speak("Bluetooth tools are not installed.")
            return True

        # Handle Bluetooth disconnect
        if any(p in q for p in ("disconnect bluetooth", "disconnect from bluetooth", "disconnect device")):
            info_out = subprocess.run(["bluetoothctl", "info"], env=_rt_env, capture_output=True, text=True).stdout
            m_mac = re.search(r"Device\s+([0-9A-Fa-f:]{17})", info_out)
            if m_mac:
                subprocess.run(["bluetoothctl", "disconnect", m_mac.group(1)], env=_rt_env, capture_output=True)
                speak("Bluetooth device disconnected.")
            else:
                speak("No Bluetooth device is currently connected.")
            return True

        target_dev = re.sub(r"^(?:connect bluetooth to|connect to bluetooth|connect to|pair with)\s+(?:the\s+|my\s+)?", "", q).strip(" .!?")
        target_dev = re.sub(r"\s+(?:on|via|over|with|using)?\s*blue\s*tooth(?:\s+device)?$", "", target_dev).strip()
        target_dev = re.sub(r"\s+(?:bluetooth\s+)?device$", "", target_dev).strip()
        target_dev = re.sub(r"^device\s+", "", target_dev).strip()
        target_dev = target_dev.replace("fast", "first")
        # Ignore Wi-Fi connect phrases if user said "connect to wifi ..."
        if any(w in target_dev for w in ("wifi", "wi-fi", "internet", "network")):
            pass
        else:
            if not target_dev:
                speak("Which Bluetooth device should I connect to?")
                return True

            subprocess.run(["rfkill", "unblock", "bluetooth"], env=_rt_env, capture_output=True)
            subprocess.run(["bluetoothctl", "power", "on"], env=_rt_env, capture_output=True)

            _bt_ord_map = {
                "first": 0, "1st": 0, "one": 0, "1": 0, "number 1": 0, "number one": 0,
                "second": 1, "2nd": 1, "two": 1, "2": 1, "number 2": 1, "number two": 1,
                "third": 2, "3rd": 2, "three": 2, "3": 2, "number 3": 2, "number three": 2,
                "fourth": 3, "4th": 3, "four": 3, "4": 3, "number 4": 3, "number four": 3,
                "fifth": 4, "5th": 4, "five": 4, "5": 4, "number 5": 4, "number five": 4,
            }
            ord_idx = _bt_ord_map.get(target_dev, None)

            def _parse_bt_devs(raw_out):
                res_list = []
                for ln in raw_out.splitlines():
                    pts = ln.split(" ", 2)
                    if len(pts) >= 3 and pts[0] == "Device":
                        res_list.append((pts[1].strip(), pts[2].strip()))
                return res_list

            devs_list = _parse_bt_devs(subprocess.run(["bluetoothctl", "devices"], env=_rt_env, capture_output=True, text=True).stdout)
            matched_mac = ""
            matched_name = ""

            if ord_idx is not None:
                if len(devs_list) <= ord_idx:
                    speak("Scanning for nearby Bluetooth devices.")
                    subprocess.run(["bluetoothctl", "--timeout", "4", "scan", "on"], env=_rt_env, capture_output=True, text=True)
                    devs_list = _parse_bt_devs(subprocess.run(["bluetoothctl", "devices"], env=_rt_env, capture_output=True, text=True).stdout)
                if 0 <= ord_idx < len(devs_list):
                    matched_mac, matched_name = devs_list[ord_idx]
            else:
                for mac_i, name_i in devs_list:
                    if target_dev in name_i.lower():
                        matched_mac, matched_name = mac_i, name_i
                        break
                if not matched_mac:
                    speak(f"Searching for {target_dev} via Bluetooth.")
                    subprocess.run(["bluetoothctl", "--timeout", "4", "scan", "on"], env=_rt_env, capture_output=True, text=True)
                    devs_list = _parse_bt_devs(subprocess.run(["bluetoothctl", "devices"], env=_rt_env, capture_output=True, text=True).stdout)
                    for mac_i, name_i in devs_list:
                        if target_dev in name_i.lower():
                            matched_mac, matched_name = mac_i, name_i
                            break

            if not matched_mac:
                speak(f"Could not find a Bluetooth device matching {target_dev}. Make sure it is turned on and in range.")
                return True

            speak(f"Connecting to {matched_name}.")
            subprocess.run(["bluetoothctl", "trust", matched_mac], env=_rt_env, capture_output=True)
            res = subprocess.run(["bluetoothctl", "connect", matched_mac], env=_rt_env, capture_output=True, text=True, timeout=12)
            if res.returncode == 0 or "Connection successful" in res.stdout:
                speak(f"Connected to {matched_name}.")
            else:
                speak(f"Could not connect to {matched_name}. Make sure Bluetooth is enabled and paired on the device.")
            return True

    # 0Y. Instant "Close Everything / Close All Windows" Handler (0.00s Parallel Close)
    if q in ("close everything", "close all", "close all windows", "close all apps", "close every window", "clear all windows", "funga kila kitu", "funga zote"):
        def _fast_close_all():
            if shutil.which("wmctrl"):
                wins = subprocess.run(["wmctrl", "-lx"], env=_rt_env, capture_output=True, text=True).stdout.splitlines()
                for w in wins:
                    low_w = w.lower()
                    if any(sys_w in low_w for sys_w in ("xfce4-panel", "xfdesktop", "wrapper-2.0")):
                        continue
                    parts = w.split()
                    if parts:
                        subprocess.Popen(["wmctrl", "-ic", parts.pop(0)], env=_rt_env)
            elif shutil.which("xdotool"):
                wids = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "."], env=_rt_env, capture_output=True, text=True).stdout.split()
                for wid in wids:
                    subprocess.Popen(["xdotool", "windowclose", wid], env=_rt_env)
        threading.Thread(target=_fast_close_all, daemon=True).start()
        speak("Closing everything.")
        return True

    # Normalize common STT mishearings of "OSINT"
    q = re.sub(r"\b(?:all sent|oh sent|oh sin|o sin|o sent|os int|ocean|osent|awsome|awesome)\b", "osint", q)

    # 0AD. Priority Live-Terminal OSINT Runner (Standalone osint_worker.py)
    osint_trigs = ("gather information on ", "gather info on ", "osint on ", "osint for ", "osint ", "run osint on ", "run osint ", "recon on ", "recon ", "investigate ")
    if any(q.startswith(t) for t in osint_trigs):
        raw_tgt = re.sub(r"^(?:gather\s+information\s+on|gather\s+info\s+on|run\s+osint\s+on|run\s+osint|osint\s+on|osint\s+for|osint|all\s+sent|oh\s+sent|ocean|recon\s+on|recon|investigate)\s+", "", str(query).strip(), flags=re.IGNORECASE).strip(" .!?")
        if not raw_tgt:
            speak("Please specify a person, username, domain, or IP address to investigate.")
            return True
        slug = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_tgt)[:40]
        rep = f"{HOME}/Desktop/osint_{slug}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        py_bin = f"{os.path.dirname(os.path.abspath(__file__))}/venv/bin/python3"
        worker_py = f"{os.path.dirname(os.path.abspath(__file__))}/osint_worker.py"
        speak(f"Opening terminal and gathering live OSINT intelligence on {raw_tgt}.")
        tb = shutil.which("qterminal") or shutil.which("xfce4-terminal") or shutil.which("x-terminal-emulator")
        if tb:
            launch_gui([tb, "-e", "bash", "-c", f"'{py_bin}' '{worker_py}' '{raw_tgt}' '{rep}'; exec bash"])
        return True

    # 0AC. Priority Clipboard Image-Link Downloader ("download this image", "download image", "save image link")
    if any(p in q for p in ("download this image", "download image", "download the image", "save this image", "save image link", "download photo", "download picture")):
        clip_url = ""
        if shutil.which("xclip"):
            clip_url = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=_rt_env, capture_output=True, text=True).stdout.strip()
        if not clip_url.startswith(("http://", "https://")):
            speak("Please copy a valid image link starting with http or https first.")
            return True

        # Unwrap Google Images / Bing redirect URLs (?imgurl=https%3A%2F%2F...)
        import urllib.parse as _up, urllib.request as _ur
        parsed = _up.urlparse(clip_url)
        qs = _up.parse_qs(parsed.query)
        if "imgurl" in qs and qs["imgurl"]:
            clip_url = qs["imgurl"].pop(0)

        pic_dir = f"{HOME}/Pictures"
        os.makedirs(pic_dir, exist_ok=True)
        speak("Downloading image from your clipboard link now.")

        def _bg_dl_image(target_url, out_dir):
            try:
                p_u = _up.urlparse(target_url)
                origin = f"{p_u.scheme}://{p_u.netloc}/"
                req = _ur.Request(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Referer": origin
                })
                with _ur.urlopen(req, timeout=20) as resp:
                    data = resp.read()
                    ctype = resp.headers.get("Content-Type", "").lower()

                # Reject HTML anti-bot/hotlink error pages before saving
                if "text/html" in ctype or data.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                    speak("That website blocked direct image download. Try copying the direct image address instead.")
                    return

                stamp = time.strftime('%Y%m%d_%H%M%S')
                raw_path = os.path.join(out_dir, f"raw_{stamp}.bin")
                final_name = f"kali_img_{stamp}.png"
                final_path = os.path.join(out_dir, final_name)
                open(raw_path, "wb").write(data)

                # Decode & convert (WebP / AVIF / JPEG / PNG) into a universally readable PNG
                converted = False
                try:
                    from PIL import Image
                    with Image.open(raw_path) as im:
                        im.convert("RGBA").save(final_path, "PNG")
                    converted = True
                except Exception:
                    if shutil.which("ffmpeg"):
                        r_ff = subprocess.run(["ffmpeg", "-y", "-i", raw_path, final_path], env=_rt_env, capture_output=True)
                        converted = (r_ff.returncode == 0 and os.path.exists(final_path))

                if converted:
                    os.remove(raw_path)
                else:
                    os.rename(raw_path, final_path)

                if shutil.which("xclip"):
                    subprocess.run(["xclip", "-selection", "clipboard"], input=final_path, text=True, env=_rt_env)
                speak(f"Image downloaded and saved to Pictures as {final_name}.")
            except Exception as err:
                speak(f"Sorry, image download failed: {str(err)[:60]}")

        threading.Thread(target=_bg_dl_image, args=(clip_url, pic_dir), daemon=True).start()
        return True

    # 0AB. Priority Owner & Creator Identity Handler
    owner_phrases = (
        "who do you belong to", "who do u belong to", "whom do you belong to",
        "who owns you", "who is your owner", "who's your owner", "whose assistant are you",
        "who created you", "who made you", "who built you", "who programmed you",
        "who is your creator", "who's your creator", "who is your master", "who is your boss",
        "ni wa nani", "unamilikiwa na nani", "nani alikutengeneza"
    )
    if any(p in q for p in owner_phrases):
        speak("I belong to Emmanuel, an ethical penetration tester and bug bounty hunter.")
        return True

    # 0AA. Built-in 100-Command Self-Diagnostic ("check yourself", "self check", "run diagnostics")
    if q in ("check yourself", "check your self", "self check", "self-check", "run self check", "run diagnostics", "diagnose yourself", "test all commands"):
        if globals().get("_RUNNING_SELF_CHECK"):
            return True
        import unittest.mock as _mock
        speak("Running full 113-command self check now.")

        fake_p = _mock.MagicMock(
            returncode=0,
            stdout="SSID SIGNAL\nMyWiFi:80:WPA2:6\nDevice AA:BB:CC:DD:EE:FF TWS\nFilesystem Size Used Avail Use% Mounted\n/dev/sda1 50G 40G 10G 80% /\n",
            stderr=""
        )

        extra_cmds_85 = [
            "volume up", "increase volume", "volume down", "decrease volume",
            "set volume to 50 percent", "set volume to 90%", "mute", "unmute",
            "brightness up", "brightness down",
            "pause", "pause music", "resume", "resume video", "play next",
            "next track", "play Tegemeo", "play music LoFi beats", "play song Alan Walker", "identify music",
            "wifi turn on", "wifi turn off", "turn on wifi", "turn off wifi",
            "turn on bluetooth", "turn off bluetooth", "list wifi", "scan wifi",
            "list bluetooth", "scan bluetooth", "connect to first wifi", "disconnect wifi",
            "connect to TWS", "disconnect bluetooth", "turn off touchpad", "turn on touchpad",
            "turn off screen", "turn on screen", "undercover mode", "refresh desktop",
            "take a screenshot", "screenshot",
            "open firefox", "open terminal", "open files", "open wireshark",
            "open downloads", "open desktop", "open documents", "open pictures",
            "close firefox", "close terminal", "close files", "close everything",
            "call Benson", "voice call Mom", "set a timer for 10 seconds", "set a timer for 5 minutes",
            "remind me in 30 seconds", "set an alarm for 6:30 AM", "wake me up at 7 PM",
            "remind me at 12 PM to check logs", "what time is it", "what is today's date",
            "battery status", "check system health", "run system check", "system status",
            "who is on my network", "check vpn", "public ip", "search google for kali linux",
            "search youtube for python", "take a picture",
            "guard my laptop", "stop guarding", "watch my network", "stop watching network",
            "start screen recording", "stop screen recording", "scan for viruses",
            "hash kali2026", "decode aGVsbG8=", "translate hello to swahili", "fungua firefox", "who do you belong to", "self check",
            "run osint on Elon Musk", "osint Elon Musk", "investigate Elon Musk",
            "connect to gamer on bluetooth", "connect to first bluetooth device", "write hello world", "hacker mode", "revert mode", "send demo_test to first bluetooth"
        ]

        core_cmds_15 = [
            "shutdown laptop", "goodnight", "restart laptop", "sleep", "lock screen",
            "update system", "what is my ip", "display code", "display command",
            "delete saved code", "delete saved command", "create a file demo_test",
            "create a folder demo_dir", "move demo_test to desktop", "run whoami"
        ]

        passed_cnt = 0
        failures = []

        globals()["_RUNNING_SELF_CHECK"] = True
        try:
          with _mock.patch("subprocess.run", return_value=fake_p), \
             _mock.patch("subprocess.Popen", return_value=fake_p), \
             _mock.patch("shutil.move", return_value=None), \
             _mock.patch("os.remove", return_value=None), \
             _mock.patch("time.sleep", return_value=None):
            for idx, cmd in enumerate(extra_cmds_85, 1):
                try:
                    if handle_extra(cmd, lambda m, **kw: None, lambda c: True, _rt_env):
                        passed_cnt += 1
                    else:
                        failures.append(f"[{idx:03d}] {cmd}: unhandled")
                except Exception as exc:
                    failures.append(f"[{idx:03d}] {cmd}: {exc}")

            import __main__ as _hk_main
            if hasattr(_hk_main, "handle_query"):
                hk_ns = _hk_main.__dict__
            else:
                m_src, _, _ = open(f"{os.path.dirname(os.path.abspath(__file__))}/hey_kali.py", "r", encoding="utf-8").read().partition('print("Ready! Say \'Hey Kali\'..."')
                hk_ns = {"__name__": "__selfcheck__"}
                for _mod_n in ("pyaudio", "vosk", "faster_whisper"):
                    sys.modules.setdefault(_mod_n, _mock.MagicMock())
                exec(m_src, hk_ns)

            orig_spk = hk_ns.get("speak", speak)
            orig_gui = hk_ns.get("launch_gui", launch_gui)
            try:
                hk_ns["speak"] = lambda m, **kw: False
                hk_ns["launch_gui"] = lambda c: True
                for offset, cmd in enumerate(core_cmds_15, 97):
                    try:
                        hk_ns["handle_query"](cmd)
                        passed_cnt += 1
                    except Exception as exc:
                        failures.append(f"[{offset:03d}] {cmd}: {exc}")
            finally:
                hk_ns["speak"] = orig_spk
                hk_ns["launch_gui"] = orig_gui
            # [106] OSINT Worker syntax & real regex extraction verification
            try:
                import py_compile as _pyc
                _wk_path = f"{os.path.dirname(os.path.abspath(__file__))}/osint_worker.py"
                _pyc.compile(_wk_path, doraise=True)
                _wk_src = open(_wk_path, "r", encoding="utf-8").read()
                _sample = (
                    "Elon Reeve Musk was born on June 28, 1971, in Pretoria, South Africa. "
                    "He holds Canadian and American citizenship. "
                    "He is an industrialist, futurist, and former United States public official. "
                    "He is the CEO of Tesla and SpaceX. "
                    "He received bachelor's degrees in 1997 from the University of Pennsylvania before moving. "
                    "Musk family. Contact test@example.com or +1-555-010-9999."
                )
                _ns = {"re": re, "corpus": _sample}
                for _line in _wk_src.splitlines():
                    if _line.lstrip().startswith(("m_loc =", "nat_hits =", "m_occ =", "m_assoc =", "m_edu =", "m_fam =", "emails =", "phones =")):
                        exec(_line.lstrip(), _ns)
                if (
                    _ns.get("m_loc") and "Pretoria" in _ns["m_loc"].group(1)
                    and _ns.get("m_edu") and "University of Pennsylvania" in _ns["m_edu"].group(1)
                    and "test@example.com" in _ns.get("emails", [])
                    and _ns.get("phones")
                ):
                    passed_cnt += 1
                else:
                    failures.append("[106] osint_worker regex check: extraction mismatch")
            except Exception as exc:
                failures.append(f"[106] osint_worker check: {exc}")

            # [108] Multi-action "and" command chaining verification
            try:
                hk_ns["handle_query"]("open terminal and volume up")
                passed_cnt += 1
            except Exception as exc:
                failures.append(f"[108] multi-action 'and' chaining: {exc}")

        finally:
          globals()["_RUNNING_SELF_CHECK"] = False

        for cleanup_f in (f"{HOME}/Desktop/demo_test.txt", f"{HOME}/Desktop/demo_dir"):
            if os.path.isfile(cleanup_f):
                os.remove(cleanup_f)
            elif os.path.isdir(cleanup_f):
                os.rmdir(cleanup_f)

        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        report_lines = [
            "=== HEY KALI 113-COMMAND SELF-DIAGNOSTIC REPORT ===",
            f"Result: {passed_cnt}/113 PASSED | {len(failures)} FAILED",
            "=" * 52,
            ""
        ]
        if failures:
            report_lines.append("Failed Commands:")
            report_lines.extend(failures)
        else:
            report_lines.append("All 113 voice command modules executed cleanly with 0 errors!")

        open(out_f, "w", encoding="utf-8").write("\n".join(report_lines) + "\n")

        if failures:
            failed_names = ", ".join(f.split("] ", 1).pop(-1).split(":", 1).pop(0) for f in failures[:4])
            speak(f"Self check complete. {passed_cnt} of 113 passed, and {len(failures)} failed: {failed_names}. Full report shown on screen.")
        else:
            speak("Self check complete. All 113 commands passed with zero errors.")

        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Hey Kali Self-Check (113 Commands)", f"--filename={out_f}", "--width=740", "--height=440"])
        return True

    # 0Z. Priority Media Controls (Pause, Resume, Play Next, Play Previous)
    if q in ("pause", "resume", "continue") or any(p in q for p in ("pause music", "pause video", "pause song", "stop music", "stop video", "resume music", "resume video", "resume song", "continue playing")):
        if shutil.which("playerctl") and subprocess.run(["playerctl", "status"], env=_rt_env, capture_output=True).returncode == 0:
            subprocess.run(["playerctl", "play-pause"], env=_rt_env)
        elif shutil.which("xdotool"):
            for cls in ("firefox", "chromium", "google-chrome", "vlc"):
                wids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], env=_rt_env, capture_output=True, text=True).stdout.split()
                if wids:
                    subprocess.run(["xdotool", "windowactivate", "--sync", wids.pop(0)], env=_rt_env, capture_output=True)
                    break
            subprocess.run(["xdotool", "key", "space"], env=_rt_env)
        speak("Playback toggled.")
        return True

    if q in ("next", "skip") or any(p in q for p in ("play next", "next track", "next song", "next video", "skip song", "skip track")):
        if shutil.which("playerctl") and subprocess.run(["playerctl", "status"], env=_rt_env, capture_output=True).returncode == 0:
            subprocess.run(["playerctl", "next"], env=_rt_env)
        elif shutil.which("xdotool"):
            for cls in ("firefox", "chromium", "google-chrome"):
                wids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls], env=_rt_env, capture_output=True, text=True).stdout.split()
                if wids:
                    subprocess.run(["xdotool", "windowactivate", "--sync", wids.pop(0)], env=_rt_env, capture_output=True)
                    break
            subprocess.run(["xdotool", "key", "shift+N"], env=_rt_env)
        speak("Playing next track.")
        return True

    # 0X. WhatsApp Desktop Voice Caller ("call <name>", "voice call <name>", "call <name> on whatsapp")
    if q.startswith(("call ", "voice call ", "whatsapp call ", "phone ")) and len(q.split()) >= 2:
        contact_name = re.sub(
            r"^(?:voice\s+call|whatsapp\s+call|call|phone)\s+(?:my\s+|contact\s+)?",
            "", str(query).strip(), flags=re.IGNORECASE
        ).strip(" .!?")
        contact_name = re.sub(r"\s+(?:on\s+whatsapp|via\s+whatsapp)$", "", contact_name, flags=re.IGNORECASE).strip()

        if not contact_name:
            speak("Who would you like me to call on WhatsApp?")
            return True

        # 1) Locate installed WhatsApp Desktop executable or .desktop launcher
        wa_cmd = []
        for snap_p in ("/snap/bin/whatsapp-electron", "/snap/whatsapp-electron/current/whatsapp-electron"):
            if os.path.exists(snap_p):
                wa_cmd = [snap_p, "--no-sandbox"]
                break
        if not wa_cmd:
          for cand in ("whatsapp-electron", "whatsapp-for-linux", "whatsapp-desktop", "zapzap", "whatsapp", "wasistlos"):
            if shutil.which(cand):
                wa_cmd = [shutil.which(cand)]
                break

        if not wa_cmd:
            for d_file in glob.glob("/usr/share/applications/*.desktop") + glob.glob(f"{HOME}/.local/share/applications/*.desktop") + glob.glob("/var/lib/snapd/desktop/applications/*.desktop"):
                if "whatsapp" in os.path.basename(d_file).lower() or "zapzap" in os.path.basename(d_file).lower():
                    for line in open(d_file, errors="ignore"):
                        if line.startswith("Exec="):
                            raw_exec = line.split("=", 1).pop(1).strip()
                            wa_cmd = [tok for tok in shlex.split(raw_exec) if not tok.startswith("%")]
                            break
                if wa_cmd:
                    break

        if not wa_cmd:
            speak("WhatsApp Desktop was not found on your system. Opening WhatsApp Web instead.")
            launch_gui(["firefox", "https://whatsapp.com"])
            return True

        speak(f"Opening WhatsApp and calling {contact_name}.")

        def _do_wa_call(cmd_list, target_person):
            # Launch or bring WhatsApp Desktop to front
            launch_gui(cmd_list)
            time.sleep(3.5)
            if not shutil.which("xdotool"):
                return
            wid = ""
            cand_wids = []
            for flag, pat in (("--name", "WhatsApp"), ("--class", "whatsapp"), ("--class", "electron")):
                cand_wids.extend(subprocess.run(
                    ["xdotool", "search", "--onlyvisible", flag, pat],
                    env=_rt_env, capture_output=True, text=True
                ).stdout.split())
            for cw in dict.fromkeys(cand_wids):
                g_chk = dict(l.split("=", 1) for l in subprocess.run(
                    ["xdotool", "getwindowgeometry", "--shell", cw],
                    env=_rt_env, capture_output=True, text=True
                ).stdout.splitlines() if "=" in l)
                if int(g_chk.get("WIDTH", 0)) > 600 and int(g_chk.get("HEIGHT", 0)) > 400:
                    wid = cw
                    break
            if wid:
                subprocess.run(["xdotool", "windowactivate", "--sync", wid], env=_rt_env, capture_output=True)
                time.sleep(0.5)
                # Use WhatsApp Web/Electron global search shortcut (Ctrl+Alt+slash) + fallback click on search box
                geom = subprocess.run(["xdotool", "getwindowgeometry", "--shell", wid], env=_rt_env, capture_output=True, text=True).stdout
                g_map = dict(l.split("=", 1) for l in geom.splitlines() if "=" in l)
                wx, wy, ww = int(g_map.get("X", 0)), int(g_map.get("Y", 0)), int(g_map.get("WIDTH", 1000))

                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+alt+slash"], env=_rt_env)
                time.sleep(0.35)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+a", "BackSpace"], env=_rt_env)
                subprocess.run(["xdotool", "type", "--delay", "40", target_person], env=_rt_env)
                time.sleep(1.1)
                # Press Down + Return AND click first search result row (wx + 190, wy + 225) so chat always opens
                subprocess.run(["xdotool", "key", "Down", "Return"], env=_rt_env)
                time.sleep(0.3)
                subprocess.run(["xdotool", "mousemove", "--sync", str(wx + 190), str(wy + 225)], env=_rt_env)
                subprocess.run(["xdotool", "click", "1"], env=_rt_env)
                time.sleep(0.8)

                # Exact 1366x768 Voice Call button center (from image_HE65ip.png tooltip: X=1213, Y=96)
                if ww > 200:
                    call_x = 1213 if ww >= 1300 else (wx + ww - 153)
                    call_y = 96 if ww >= 1300 else (wy + 68)
                    subprocess.run(["xdotool", "mousemove", "--sync", str(call_x), str(call_y)], env=_rt_env)
                    time.sleep(0.35)
                    subprocess.run(["xdotool", "mousedown", "1"], env=_rt_env)
                    time.sleep(0.12)
                    subprocess.run(["xdotool", "mouseup", "1"], env=_rt_env)

        threading.Thread(target=_do_wa_call, args=(wa_cmd, contact_name), daemon=True).start()
        return True

    # 0A. Priority Audio & Volume Controls (100% Offline)
    if any(p in q for p in ("volume up", "increase volume", "turn up volume", "raise volume", "louder")):
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env)
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+15%"], env=_rt_env)
        speak("Volume increased.")
        return True

    if any(p in q for p in ("volume down", "decrease volume", "turn down volume", "lower volume", "quieter")):
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-15%"], env=_rt_env)
        speak("Volume decreased.")
        return True

    if q in ("mute", "mute audio", "mute volume", "silence audio", "turn off sound", "turn off audio"):
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], env=_rt_env)
        return True

    if q in ("unmute", "unmute audio", "unmute volume", "turn on sound", "turn on audio"):
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env)
        speak("Audio unmuted.")
        return True

    m_vol = re.search(r'(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*(?:percent|%)?', q)
    if m_vol:
        pct = max(0, min(100, int(m_vol.group(1))))
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env)
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], env=_rt_env)
        speak(f"Volume set to {pct} percent.")
        return True

    # 0B. Priority Hardware & System Toggles ("turn off wifi", "turn on bluetooth", "turn off touchpad", "turn off screen")
    if q.startswith(("turn off ", "turn on ", "disable ", "enable ", "switch off ", "switch on ")):
        turn_on = q.startswith(("turn on ", "enable ", "switch on "))
        target = re.sub(r'^(turn off|turn on|disable|enable|switch off|switch on)\s+(the\s+|my\s+)?', '', q).strip()

        if any(w in target for w in ("wi-fi", "wifi", "wireless", "internet")):
            state = "on" if turn_on else "off"
            subprocess.run(["nmcli", "radio", "wifi", state], env=_rt_env)
            speak(f"Wi-Fi turned {state}.")
            return True

        if "bluetooth" in target:
            if turn_on:
                subprocess.run(["rfkill", "unblock", "bluetooth"], env=_rt_env)
                if shutil.which("bluetoothctl"):
                    subprocess.run(["bluetoothctl", "power", "on"], env=_rt_env)
                speak("Bluetooth turned on.")
            else:
                if shutil.which("bluetoothctl"):
                    subprocess.run(["bluetoothctl", "power", "off"], env=_rt_env)
                subprocess.run(["rfkill", "block", "bluetooth"], env=_rt_env)
                speak("Bluetooth turned off.")
            return True

        if "airplane" in target or "flight mode" in target:
            if turn_on:
                subprocess.run(["nmcli", "radio", "all", "off"], env=_rt_env)
                subprocess.run(["rfkill", "block", "all"], env=_rt_env)
                speak("Airplane mode turned on.")
            else:
                subprocess.run(["rfkill", "unblock", "all"], env=_rt_env)
                subprocess.run(["nmcli", "radio", "all", "on"], env=_rt_env)
                speak("Airplane mode turned off.")
            return True

        if any(w in target for w in ("touchpad", "trackpad", "touch pad")):
            toggled = False
            if shutil.which("xfconf-query"):
                props = subprocess.run(["xfconf-query", "-c", "pointers", "-l"], env=_rt_env, capture_output=True, text=True).stdout.splitlines()
                tp_props = [p.strip() for p in props if p.strip().endswith("/Properties/Device_Enabled") and any(k in p.lower() for k in ("touchpad", "synaptics", "synps2", "alps", "elan"))]
                for prop in tp_props:
                    subprocess.run(["xfconf-query", "-c", "pointers", "-p", prop, "-s", "1" if turn_on else "0"], env=_rt_env)
                    toggled = True
            if not toggled and shutil.which("xinput"):
                out = subprocess.run(["xinput", "list"], env=_rt_env, capture_output=True, text=True).stdout
                for line in out.splitlines():
                    if any(k in line.lower() for k in ("touchpad", "synaptics", "synps/2", "alps", "elan")):
                        m_id = re.search(r'id=(\d+)', line)
                        if m_id:
                            subprocess.run(["xinput", "enable" if turn_on else "disable", m_id.group(1)], env=_rt_env)
                            toggled = True
            speak(f"Touchpad {'enabled' if turn_on else 'disabled'}." if toggled else "Could not find a touchpad device.")
            return True

        if any(w in target for w in ("screen", "display", "monitor")):
            if not turn_on:
                speak("Turning off the display.")
                subprocess.Popen(["xset", "dpms", "force", "off"], env=_rt_env)
            else:
                subprocess.Popen(["xset", "dpms", "force", "on"], env=_rt_env)
                speak("Display turned on.")
            return True

    q = str(query).strip().lower()
    # Graceful Window & App Closer (Matches BOTH X11 App Class & Window Title via wmctrl -lx)
    close_prefixes = ("close ", "exit ", "quit ")
    if any(q.startswith(p) for p in close_prefixes) and " " in str(query):
        target = ""
        for p in close_prefixes:
            if q.startswith(p):
                target = str(query)[len(p):].strip(" ?.")
                break
        for filler in ("the ", "app ", "application ", "window ", "file ", "folder "):
            if target.lower().startswith(filler):
                target = target[len(filler):].strip()

        if not target:
            speak("Please tell me which open app or window to close.")
            return True

        win_env = os.environ.copy()
        win_env["DISPLAY"] = ":0"
        win_env["XAUTHORITY"] = f"{HOME}/.Xauthority"

        win_lines = subprocess.run(["wmctrl", "-lx"], env=win_env, capture_output=True, text=True).stdout.splitlines()

        aliases = {
            "terminal": ("qterminal", "xfce4-terminal", "gnome-terminal", "konsole", "xterm", "gameronduty"),
            "notepad": ("mousepad", "leafpad", "gedit"),
            "editor": ("mousepad", "code", "gedit"),
            "browser": ("firefox", "chromium", "chrome"),
            "chrome": ("chrome", "chromium"),
            "files": ("thunar", "nautilus", "pcmanfm"),
            "file manager": ("thunar", "nautilus", "pcmanfm"),
            "code": ("code", "vscodium")
        }

        search_terms = [target.lower()]
        if target.lower() in aliases:
            search_terms.extend(aliases.get(target.lower(), ()))

        matched_ids = []
        for line in win_lines:
            low_line = line.lower()
            if any(term in low_line for term in search_terms):
                win_id = line.split().pop(0)
                matched_ids.append(win_id)

        if not matched_ids:
            speak(f"I could not find an open window for {target}.")
            return True

        target_id = matched_ids.pop(-1)
        subprocess.run(["wmctrl", "-ic", target_id], env=win_env)

        time.sleep(0.8)
        still_open = subprocess.run(["wmctrl", "-lx"], env=win_env, capture_output=True, text=True).stdout.lower()
        if target_id.lower() in still_open:
            speak(f"{target} has an unsaved file or active download prompt. Are you sure you want to exit? Please confirm on your screen.")
        else:
            speak(f"Closed {target}.")
        return True

    q = str(query).strip().lower()
    # Paste-Proof Web Search ("search for <topic>", "search google for <topic>", "google <topic>")
    search_prefixes = ("search google for ", "search the web for ", "search for ", "google ", "search ")
    if any(q.startswith(p) for p in search_prefixes) and " " in str(query):
        term = ""
        for p in search_prefixes:
            if q.startswith(p):
                term = str(query)[len(p):].strip(" ?.")
                break
        if not term:
            speak("Please tell me what you want to search for.")
            return True

        g_host = ".".join(["www", "google", "com"])
        q_str = urllib.parse.urlencode({"q": term})
        search_url = urllib.parse.urlunparse(("https", g_host, "/search", "", q_str, ""))

        browser_env = os.environ.copy()
        browser_env["DISPLAY"] = ":0"
        browser_env["XAUTHORITY"] = f"{HOME}/.Xauthority"
        browser_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
        subprocess.Popen(["/usr/bin/firefox", search_url], env=browser_env, start_new_session=True)
        speak(f"Searching Google for {term}.")
        return True

    # Module A: Smart Clipboard AI
    # Direct File & Video Downloader ("create a download link", "download this link")
    dl_phrases = (
        "create a download link", "create download link", "generate a download link",
        "generate download link", "make a download link", "get download link",
        "direct download link", "download this link", "download copied link",
        "download this video", "download video",
        "download this image", "download image", "save this image", "save copied image",
        "download this picture", "save this picture"
    )
    if any(p in q for p in dl_phrases):
        clip_env = os.environ.copy()
        clip_env["DISPLAY"] = ":0"
        clip_env["XAUTHORITY"] = f"{HOME}/.Xauthority"

        raw_url = ""
        if shutil.which("xclip"):
            raw_url = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=clip_env, capture_output=True, text=True).stdout.strip()
        elif shutil.which("xsel"):
            raw_url = subprocess.run(["xsel", "--clipboard", "--output"], env=clip_env, capture_output=True, text=True).stdout.strip()

        m_url = re.search(r"https?://[^\s'\"<>]+", raw_url)
        if not m_url:
            # Check if raw image data was copied directly via browser "Copy Image"
            if shutil.which("xclip"):
                targets = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "TARGETS"], env=clip_env, capture_output=True, text=True).stdout.splitlines()
                mime_pick = next((t.strip() for t in targets if t.strip() in ("image/png", "image/jpeg", "image/webp")), "")
                if mime_pick:
                    raw_img = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", mime_pick], env=clip_env, capture_output=True).stdout
                    if raw_img:
                        dl_dir = f"{HOME}/Downloads"
                        os.makedirs(dl_dir, exist_ok=True)
                        ext = ".jpg" if "jpeg" in mime_pick else (".webp" if "webp" in mime_pick else ".png")
                        out_img = f"{dl_dir}/kali_image_{time.strftime('%Y%m%d_%H%M%S')}{ext}"
                        open(out_img, "wb").write(raw_img)
                        speak(f"Saved copied image directly into your Downloads folder as {os.path.basename(out_img)}.")
                        return True
            speak("I did not find a valid web link or image in your clipboard. Copy an image or link first.")
            return True

        src_url = m_url.group(0)
        dl_dir = f"{HOME}/Downloads"
        os.makedirs(dl_dir, exist_ok=True)

        # Case 1: Video platforms (YouTube, TikTok, Instagram, X, Vimeo) -> Download actual merged MP4 video via yt-dlp!
        video_domains = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com", "x.com", "twitter.com", "facebook.com", "vimeo.com")
        if any(d in src_url.lower() for d in video_domains):
            yt_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "yt-dlp") if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "yt-dlp")) else shutil.which("yt-dlp")
            if not yt_bin:
                speak("yt-dlp is not installed yet. Install it inside your virtual environment first.")
                return True

            speak("Downloading the actual video straight into your Downloads folder now. I will notify you when it finishes.")
            out_tmpl = f"{dl_dir}/%(title).80s.%(ext)s"

            def _bg_video_dl(url_to_get):
                res = subprocess.run([
                    yt_bin, "--no-playlist", "--concurrent-fragments", "4",
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "-o", out_tmpl,
                    url_to_get
                ], capture_output=True, text=True)
                if res.returncode == 0:
                    speak("Your video download is complete and saved in Downloads.")
                else:
                    print(f"[Video DL Error] {res.stderr[:200]}", flush=True)
                    speak("Sorry, the video download failed. Check the link and try again.")

            threading.Thread(target=_bg_video_dl, args=(src_url,), daemon=True).start()
            return True

        # Case 2: Direct files, images, Google Drive, Dropbox & GitHub links
        speak("Resolving and downloading the file into your Downloads folder now.")
        direct_url = src_url
        fname_hint = ""

        gdrive_m = re.search(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", src_url)
        if not gdrive_m:
            gdrive_m = re.search(r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)", src_url)
        if gdrive_m:
            direct_url = f"https://drive.google.com/uc?export=download&id={gdrive_m.group(1)}"
        elif ".".join(["dropbox", "com"]) in src_url:
            direct_url = re.sub(r"([?&])dl=0\b", r"\1dl=1", src_url)
            if "dl=1" not in direct_url:
                direct_url += ("&" if "?" in direct_url else "?") + "dl=1"
        elif ".".join(["github", "com"]) in src_url and "/blob/" in src_url:
            direct_url = src_url.replace(".".join(["github", "com"]), ".".join(["raw", "githubusercontent", "com"])).replace("/blob/", "/")

        ctype = ""
        try:
            head_r = _HTTP.head(direct_url, allow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if head_r.status_code >= 400:
                head_r = _HTTP.get(direct_url, stream=True, allow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            direct_url = head_r.url
            ctype = head_r.headers.get("Content-Type", "").lower()
            cdisp = head_r.headers.get("Content-Disposition", "")
            m_cd = re.search(r'filename="?([^";]+)"?', cdisp)
            if m_cd:
                fname_hint = m_cd.group(1).strip()

            if "text/html" in ctype:
                html_txt = _HTTP.get(direct_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}).text
                found_assets = re.findall(r"https?://[^\s'\"<>]+?\.(?:zip|7z|rar|tar\.gz|tgz|iso|deb|apk|exe|msi|pdf|mp4|mkv|mp3|png|jpg|jpeg|webp)(?:\?[^\s'\"<>]*)?", html_txt, re.IGNORECASE)
                if found_assets:
                    direct_url = found_assets.pop(0)
        except Exception as _dl_err:
            print(f"[File DL resolver] {_dl_err}", flush=True)

        if shutil.which("xclip"):
            p_clip = subprocess.Popen(["xclip", "-i", "-selection", "clipboard"], stdin=subprocess.PIPE, env=clip_env)
            p_clip.communicate(input=direct_url.encode("utf-8"))

        raw_name = fname_hint or os.path.basename(urllib.parse.urlparse(direct_url).path) or f"kali_download_{int(time.time())}"
        if "." not in raw_name and "image/" in ctype:
            ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
            for k_ct, v_ext in ext_map.items():
                if k_ct in ctype:
                    raw_name += v_ext
                    break

        out_path = os.path.join(dl_dir, raw_name)
        subprocess.Popen(["curl", "-L", "-s", "-A", "Mozilla/5.0", "-o", out_path, direct_url])
        speak(f"Direct link copied to clipboard, and file saved to your Downloads folder as {raw_name}.")
        return True

    # Copied Image Vision Analyzer ("explain image", "describe image", "what is in this image")
    img_phrases = (
        "explain image", "explain this image", "explain the image",
        "describe image", "describe this image", "describe the image",
        "what is in this image", "what is in the image", "analyze image", "analyse image",
        "analyze this image", "analyse this image"
    )
    if any(p in q for p in img_phrases):
        clip_env = os.environ.copy()
        clip_env["DISPLAY"] = ":0"
        clip_env["XAUTHORITY"] = f"{HOME}/.Xauthority"

        img_path = ""
        tmp_clip_img = "/tmp/kali_clip_img.png"
        if os.path.exists(tmp_clip_img):
            os.remove(tmp_clip_img)

        # Case A: Image file copied in file manager (text/uri-list)
        if shutil.which("xclip"):
            uri_raw = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "text/uri-list"], env=clip_env, capture_output=True, text=True).stdout.strip()
            for line in uri_raw.splitlines():
                line = line.strip()
                if line.startswith("file://"):
                    cand = urllib.parse.unquote(line[7:])
                    if os.path.isfile(cand) and cand.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
                        img_path = cand
                        break

        # Case B: Raw image data copied to clipboard (e.g., from browser "Copy Image" or screenshot tool)
        if not img_path and shutil.which("xclip"):
            targets = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "TARGETS"], env=clip_env, capture_output=True, text=True).stdout.splitlines()
            mime_pick = next((t.strip() for t in targets if t.strip() in ("image/png", "image/jpeg", "image/webp")), "")
            if mime_pick:
                raw_img = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", mime_pick], env=clip_env, capture_output=True).stdout
                if raw_img:
                    open(tmp_clip_img, "wb").write(raw_img)
                    img_path = tmp_clip_img

        if not img_path or not os.path.exists(img_path):
            speak("No image was found in your clipboard. Copy an image file or right-click and copy an image first.")
            return True

        or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not or_key and os.path.exists(f"{HOME}/.openrouter_key"):
            or_key = open(f"{HOME}/.openrouter_key").read().strip()

        if not or_key or not or_key.startswith("sk-or-"):
            speak("OpenRouter vision key is missing. Make sure your key is saved in dot openrouter underscore key.")
            return True

        speak("Analyzing the copied image now.")
        try:
            # Convert/resize cleanly to JPEG via ffmpeg so any image format (PNG/WEBP/BMP/large photo) uploads fast
            norm_jpg = "/tmp/kali_clip_norm.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "quiet", "-i", img_path, "-vf", "scale='min(1280,iw)':-2", norm_jpg])
            use_file = norm_jpg if os.path.exists(norm_jpg) and os.path.getsize(norm_jpg) > 0 else img_path
            img_b64 = base64.b64encode(open(use_file, "rb").read()).decode("utf-8")

            s = chr(47)
            or_base = "https:" + s + s + "openrouter.ai" + s + "api" + s + "v1"
            or_hdrs = {
                "Authorization": f"Bearer {or_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https:" + s + s + "localhost",
                "X-Title": "HeyKali"
            }

            free_vision_models = []
            try:
                m_resp = _HTTP.get(or_base + s + "models", timeout=6)
                if m_resp.status_code == 200:
                    for m in m_resp.json().get("data", []):
                        mid = m.get("id", "")
                        mods = m.get("architecture", {}).get("input_modalities") or []
                        if ":free" in mid and "image" in mods:
                            free_vision_models.append(mid)
            except Exception:
                pass
            free_vision_models.append("openrouter/free")

            img_desc = ""
            for or_mod in dict.fromkeys(free_vision_models):
                or_body = {
                    "model": or_mod,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "You are Kali, a smart voice assistant. Describe clearly what you see in this image in 2 to 3 natural spoken sentences, including any objects, people, text, or important details."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }],
                    "max_tokens": 160
                }
                or_resp = _HTTP.post(or_base + s + "chat" + s + "completions", headers=or_hdrs, json=or_body, timeout=15)
                if or_resp.status_code == 200:
                    choices = or_resp.json().get("choices") or []
                    if choices:
                        msg = choices.pop(0).get("message") or {}
                        img_desc = str(msg.get("content") or msg.get("reasoning") or "").strip()
                        if img_desc:
                            break

            if not img_desc:
                speak("Sorry, I could not get a description from the vision service right now.")
                return True

            out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
            open(out_f, "w").write(f"=== COPIED IMAGE ANALYSIS ===\n\n{img_desc}\n")
            speak(img_desc)
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", "--title=Copied Image Explanation", f"--filename={out_f}", "--width=680", "--height=320"])
        except Exception as _ierr:
            print(f"[Explain image error] {_ierr}", flush=True)
            speak("Sorry, something went wrong while analyzing the copied image.")
        return True

    # Smart Clipboard AI — Scans Copied Files/Apps for Malware & Answers/Explains Copied Text
    cb_phrases = (
        "read my clipboard", "what did i copy", "what is in my clipboard",
        "answer this", "answer what i copied", "solve this", "solve what i copied",
        "explain this", "explain what i copied", "explain this error", "fix what i copied",
        "scan what i copied", "scan this file", "check what i copied", "check my clipboard",
        "summarize this", "summarize what i copied", "summarise this", "summarise what i copied",
        "what does this say", "what does this mean"
    )
    if any(p in q for p in cb_phrases):
        clip_env = os.environ.copy()
        clip_env["DISPLAY"] = ":0"
        clip_env["XAUTHORITY"] = f"{HOME}/.Xauthority"

        # 1. Check if a file or app was copied in the file manager (text/uri-list) or as a file path
        copied_file = ""
        if shutil.which("xclip"):
            uri_raw = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "text/uri-list"], env=clip_env, capture_output=True, text=True).stdout.strip()
            for line in uri_raw.splitlines():
                line = line.strip()
                if line.startswith("file://"):
                    cand = urllib.parse.unquote(line[7:])
                    if os.path.isfile(cand):
                        copied_file = cand
                        break

        clip_txt = ""
        if shutil.which("xclip"):
            clip_txt = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=clip_env, capture_output=True, text=True).stdout.strip()
        elif shutil.which("xsel"):
            clip_txt = subprocess.run(["xsel", "--clipboard", "--output"], env=clip_env, capture_output=True, text=True).stdout.strip()

        if not copied_file and clip_txt:
            cand_path = os.path.expanduser(clip_txt.strip("'\""))
            if os.path.isfile(cand_path):
                copied_file = cand_path

        # 2. If a real file/app was copied, run smart static binary/script & malware analysis!
        if copied_file:
            fname = os.path.basename(copied_file)
            fsize = os.path.getsize(copied_file)
            raw_bytes = open(copied_file, "rb").read(262144)  # inspect first 256 KB
            sha256 = hashlib.sha256(open(copied_file, "rb").read()).hexdigest()
            file_type = subprocess.run(["file", "-b", copied_file], capture_output=True, text=True).stdout.strip()

            indicators = []
            # Check magic header
            if raw_bytes.startswith(b"\x7fELF"):
                indicators.append("Linux ELF executable binary")
            elif raw_bytes.startswith(b"MZ"):
                indicators.append("Windows PE executable (.exe/.dll)")
            elif raw_bytes.startswith(b"PK\x03\x04") and copied_file.lower().endswith(".apk"):
                indicators.append("Android APK application package")
            elif raw_bytes.startswith(b"#!"):
                indicators.append("Executable script (" + next(iter(raw_bytes.splitlines()), b"").decode("utf-8", "ignore")[:40] + ")")

            # Extract printable ASCII strings & check for reverse-shell / payload / C2 patterns
            ascii_strs = re.findall(rb'[ -~]{4,}', raw_bytes)
            joined_lower = b" ".join(ascii_strs).lower()

            suspicious_patterns = [
                (b"socket", "raw network socket creation"),
                (b"connect", "outbound TCP/UDP network connection"),
                (b"dup2", "stdin/stdout socket redirection (classic reverse shell)"),
                (b"/bin/sh", "interactive /bin/sh shell invocation"),
                (b"/bin/bash", "interactive /bin/bash shell invocation"),
                (b"cmd.exe", "Windows cmd.exe shell invocation"),
                (b"powershell", "PowerShell execution"),
                (b"meterpreter", "Metasploit Meterpreter payload signature"),
                (b"metasploit", "Metasploit framework artifact"),
                (b"execve", "process execution syscall (execve)"),
                (b"virtualalloc", "executable memory allocation (shellcode loader)"),
                (b"base64", "encoded payload handling")
            ]
            matched_behaviors = [desc for sig, desc in suspicious_patterns if sig in joined_lower]

            # Extract embedded IPv4 addresses if present
            ips = sorted(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', joined_lower.decode("utf-8", "ignore"))))
            ips = [ip for ip in ips if not ip.startswith(("0.", "127.", "255."))][:5]

            # Optional ClamAV check if installed
            clam_hit = ""
            if shutil.which("clamscan"):
                c_out = subprocess.run(["clamscan", "--no-summary", copied_file], capture_output=True, text=True).stdout.strip()
                if "FOUND" in c_out:
                    clam_hit = c_out.split(":", 1)[-1].strip()

            verdict = "CLEAN / BENIGN FILE"
            if clam_hit or len(matched_behaviors) >= 2 or ("dup2" in str(matched_behaviors) and ("/bin/sh" in str(matched_behaviors) or "cmd.exe" in str(matched_behaviors))):
                verdict = "HIGH-RISK / REVERSE-SHELL OR MALWARE PAYLOAD DETECTED"
            elif matched_behaviors or ips:
                verdict = "SUSPICIOUS NETWORK / EXECUTION CAPABILITIES DETECTED"

            report = (
                f"=== COPIED FILE & MALWARE STATIC ANALYSIS ===\n\n"
                f"File Name    : {fname}\n"
                f"Full Path    : {copied_file}\n"
                f"File Size    : {fsize} bytes\n"
                f"File Type    : {file_type}\n"
                f"SHA-256      : {sha256}\n"
                f"Verdict      : {verdict}\n"
                f"ClamAV Match : {clam_hit if clam_hit else 'None'}\n"
                f"Embedded IPs : {', '.join(ips) if ips else 'None found'}\n"
                f"Behaviors    : {', '.join(matched_behaviors) if matched_behaviors else 'No suspicious shell/network strings detected'}\n"
            )
            out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
            open(out_f, "w").write(report)

            if "HIGH-RISK" in verdict:
                spoken = f"Warning. {fname} is a {file_type.split(',')[0]} containing high-risk reverse shell or payload indicators, including {', '.join(matched_behaviors[:3])}."
                if ips:
                    spoken += f" It also contains an embedded IP address: {next(iter(ips), '')}."
            elif "SUSPICIOUS" in verdict:
                spoken = f"{fname} has suspicious capabilities including {', '.join(matched_behaviors[:3])}."
            else:
                spoken = f"{fname} appears clean. No reverse shell or malware indicators were found."

            speak(spoken)
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", "--title=Copied File Security Analysis", f"--filename={out_f}", "--width=740", "--height=380"])
            return True

        if not clip_txt:
            speak("Your clipboard is currently empty. Copy a file or highlight some text first.")
            return True

        if "read" in q or "what did i copy" in q or "what is in my clipboard" in q:
            speak("You copied: " + clip_txt[:350])
            return True

        if any(w in q for w in ("summarize", "summarise")):
            task_prompt = "Summarize this copied text clearly in 2 short spoken sentences:"
        elif any(w in q for w in ("answer", "solve")):
            task_prompt = "Answer or solve the question/problem in this copied text directly and clearly in 2 to 3 short spoken sentences:"
        else:
            task_prompt = "Analyze this copied text (if it is a question, answer it directly; if it is an error or code, explain what it means and how to fix it; if it is general text, explain it clearly) in 2 to 3 short spoken sentences:"

        try:
            url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
            payload = json.dumps({
                "model": "gemma3:1b",
                "system": "You are Kali, a sharp voice assistant. Give a direct, natural spoken answer with no markdown symbols.",
                "prompt": f"{task_prompt}\n\n{clip_txt[:2200]}",
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 140, "num_ctx": 1536, "temperature": 0.25}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                ans = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            if ans:
                out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
                open(out_f, "w").write(f"=== CLIPBOARD AI ANALYSIS ===\n\n{ans}\n\n--- Copied Input ---\n{clip_txt[:1500]}\n")
                speak(ans)
                return True
        except Exception:
            pass
        speak("You copied: " + clip_txt[:250])
        return True

    # Persistent Scan Whitelist Handler ("add first item to whitelist", "add second virus to whitelist", "whitelist item 2")
    if "whitelist" in q and any(w in q for w in ("add", "item", "virus", "first", "second", "third", "fourth", "fifth", "1", "2", "3", "4", "5")):
        wl_file = f"{os.path.dirname(os.path.abspath(__file__))}/scan_whitelist.json"
        last_scan_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_scan_items.json"
        if not os.path.exists(last_scan_file):
            speak("There is no recent scan list to whitelist from. Run a virus scan first.")
            return True

        try:
            items = json.loads(open(last_scan_file).read())
        except Exception:
            items = []

        if not items:
            speak("Your last scan was clean, so there are no items to whitelist.")
            return True

        ord_map = {
            "first": 1, "1st": 1, "one": 1, "1": 1,
            "second": 2, "2nd": 2, "two": 2, "2": 2,
            "third": 3, "3rd": 3, "three": 3, "3": 3,
            "fourth": 4, "4th": 4, "four": 4, "4": 4,
            "fifth": 5, "5th": 5, "five": 5, "5": 5
        }
        chosen_idx = 0
        for word in re.findall(r'[a-z0-9]+', q):
            if word in ord_map:
                chosen_idx = ord_map[word]
                break

        if chosen_idx < 1 or chosen_idx > len(items):
            speak(f"Please choose an item number between 1 and {len(items)}.")
            return True

        target_item = items[chosen_idx - 1]
        # Strip dynamic PID numbers at start of process lines so whitelisting survives reboots!
        sig = re.sub(r'^(\[[^\]]+\]\s*)\d+\s+', r'\1', target_item).strip()

        wl = []
        if os.path.exists(wl_file):
            try:
                wl = json.loads(open(wl_file).read())
            except Exception:
                wl = []

        if sig not in wl:
            wl.append(sig)
            open(wl_file, "w").write(json.dumps(wl, indent=2))

        speak(f"Added item {chosen_idx} to your permanent scan whitelist. I will ignore it in all future scans.")
        return True

    # PC Virus, Rootkit & Malware Persistence Scanner ("scan for viruses", "scan my pc")
    virus_phrases = (
        "scan for virus", "scan for viruses", "scan virus", "scan viruses",
        "scan my pc", "scan my laptop", "scan my computer", "scan for malware",
        "check for virus", "check for viruses", "antivirus scan", "security scan"
    )
    if any(p in q for p in virus_phrases):
        speak("Scanning your system for viruses, hidden malware, and suspicious persistence now.")
        wl_file = f"{os.path.dirname(os.path.abspath(__file__))}/scan_whitelist.json"
        whitelist = []
        if os.path.exists(wl_file):
            try:
                whitelist = json.loads(open(wl_file).read())
            except Exception:
                whitelist = []

        def _is_whitelisted(entry_str):
            norm = re.sub(r'^(\[[^\]]+\]\s*)\d+\s+', r'\1', entry_str).strip()
            return any(w == norm or w in norm for w in whitelist)

        raw_findings = []

        # 1. Check ClamAV if installed
        if shutil.which("clamscan"):
            res = subprocess.run(
                ["clamscan", "-r", "-i", "--no-summary", f"{HOME}/Downloads", f"{HOME}/Desktop", "/tmp", "/dev/shm"],
                capture_output=True, text=True
            ).stdout.strip()
            for line in res.splitlines():
                if "FOUND" in line:
                    raw_findings.append(f"[ClamAV Signature] {line.strip()}")

        # 2. Check hidden executables or scripts in /tmp, /var/tmp, and /dev/shm
        for tmp_dir in ("/tmp", "/var/tmp", "/dev/shm"):
            if os.path.isdir(tmp_dir):
                for root_d, dirs, files in os.walk(tmp_dir):
                    for fn in files:
                        fp = os.path.join(root_d, fn)
                        try:
                            if os.path.isfile(fp) and not os.path.islink(fp):
                                if fn.startswith(".") or os.access(fp, os.X_OK):
                                    hdr = open(fp, "rb").read(4)
                                    if hdr.startswith(b"\x7fELF") or hdr.startswith(b"#!"):
                                        raw_findings.append(f"[Suspicious Temp Executable] {fp}")
                        except Exception:
                            pass

        # 3. Check processes running from deleted binaries or /tmp /dev/shm
        ps_out = subprocess.run(["ps", "-eo", "pid,user,comm,args"], capture_output=True, text=True).stdout
        for line in ps_out.splitlines()[1:]:
            low = line.lower()
            if any(bad in low for bad in ("/tmp/", "/dev/shm/", "(deleted)", "xmrig", "minerd", "nc -e", "bash -i")):
                if not any(ok in low for ok in ("hey_kali", "voice_aura", "/usr/lib/firefox-esr/crashhelper", "/usr/lib/chromium/")):
                    raw_findings.append(f"[Suspicious Running Process] {line.strip()[:120]}")

        # 4. Check user crontab for suspicious curl/wget/base64 payloads
        cron_out = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        for line in cron_out.splitlines():
            if not line.strip().startswith("#") and any(k in line.lower() for k in ("curl ", "wget ", "base64", "/tmp/", "/dev/shm/", "nc ")):
                raw_findings.append(f"[Suspicious Cron Job] {line.strip()}")

        findings = [f for f in raw_findings if not _is_whitelisted(f)]
        open(f"{os.path.dirname(os.path.abspath(__file__))}/last_scan_items.json", "w").write(json.dumps(findings, indent=2))

        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        if findings:
            report = (
                "=== KALI VIRUS & MALWARE SCAN REPORT ===\n\n"
                f"Detected {len(findings)} suspicious item(s) (say 'Add first/second item to whitelist' to ignore):\n\n"
                + "\n".join(f"{i+1}. {item}" for i, item in enumerate(findings)) + "\n"
            )
            open(out_f, "w").write(report)
            speak(f"Warning. Found {len(findings)} suspicious items on your system. Say add first or second item to whitelist if any are safe.")
        else:
            report = (
                "=== KALI VIRUS & MALWARE SCAN REPORT ===\n\n"
                f"Status: CLEAN (0 threats detected | {len(whitelist)} whitelisted rule(s) active)\n"
                "Checked: User Downloads/Desktop, /tmp & /dev/shm executables, running processes, and cron persistence.\n"
            )
            open(out_f, "w").write(report)
            speak("Scan complete. No viruses or suspicious malware processes were found on your system.")

        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Kali Virus & Security Scan", f"--filename={out_f}", "--width=780", "--height=390"])
        return True

    # All-Language Voice & Clipboard Translator ("translate <text or 'this'> to <any language>")
    if q.startswith("translate "):
        m_tr = re.match(r'^translate\s+(.+?)\s+(?:to|into)\s+([a-zA-Z\s-]+)$', q)
        if not m_tr:
            speak("Say translate followed by your phrase or say translate this, then the target language. For example, translate how are you to Swahili.")
            return True

        phrase_to_tr = m_tr.group(1).strip()
        target_lang = m_tr.group(2).strip().lower()

        if phrase_to_tr in ("this", "what i copied", "my clipboard", "it", "that"):
            clip_env = os.environ.copy()
            clip_env["DISPLAY"] = ":0"
            clip_env["XAUTHORITY"] = f"{HOME}/.Xauthority"
            if shutil.which("xclip"):
                phrase_to_tr = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=clip_env, capture_output=True, text=True).stdout.strip()
            elif shutil.which("xsel"):
                phrase_to_tr = subprocess.run(["xsel", "--clipboard", "--output"], env=clip_env, capture_output=True, text=True).stdout.strip()

        if not phrase_to_tr:
            speak("Your clipboard is empty. Highlight and copy some text first, or speak the phrase directly.")
            return True

        lang_codes = {
            "swahili": "sw", "kiswahili": "sw", "english": "en", "french": "fr",
            "spanish": "es", "arabic": "ar", "german": "de", "italian": "it",
            "portuguese": "pt", "russian": "ru", "chinese": "zh-CN", "mandarin": "zh-CN",
            "japanese": "ja", "korean": "ko", "hindi": "hi", "turkish": "tr",
            "dutch": "nl", "somali": "so", "amharic": "am", "hausa": "ha",
            "yoruba": "yo", "igbo": "ig", "zulu": "zu", "afrikaans": "af",
            "greek": "el", "hebrew": "iw", "indonesian": "id", "malay": "ms",
            "thai": "th", "vietnamese": "vi", "polish": "pl", "ukrainian": "uk",
            "swedish": "sv", "norwegian": "no", "danish": "da", "finnish": "fi"
        }
        tl = lang_codes.get(target_lang, target_lang[:2])
        translated_text = ""

        # 1. Online high-accuracy all-language translation endpoint (auto-detects source language)
        try:
            s = chr(47)
            gt_url = "https:" + s + s + ".".join(["translate", "googleapis", "com"]) + s + "translate_a" + s + "single"
            gt_params = {"client": "gtx", "sl": "auto", "tl": tl, "dt": "t", "q": phrase_to_tr[:2000]}
            gt_resp = _HTTP.get(gt_url, params=gt_params, timeout=5)
            if gt_resp.status_code == 200:
                chunks = gt_resp.json()
                first_block = next(iter(chunks), [])
                translated_text = "".join(next(iter(part), "") for part in first_block if isinstance(part, list)).strip()
        except Exception:
            pass

        # 2. Offline fallback using local gemma3:1b
        if not translated_text:
            try:
                url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
                payload = json.dumps({
                    "model": "gemma3:1b",
                    "system": "You are a precise all-language translator. Output ONLY the translated text with no extra notes or symbols.",
                    "prompt": f"Translate this into {target_lang.capitalize()}:\n{phrase_to_tr[:1500]}",
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_predict": 140, "num_ctx": 1024, "temperature": 0.2}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    translated_text = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            except Exception:
                pass

        if not translated_text:
            speak("Sorry, I could not translate that right now.")
            return True

        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(out_f, "w").write(f"=== TRANSLATION ({target_lang.upper()}) ===\n\n{translated_text}\n\n--- Original ---\n{phrase_to_tr}\n")
        speak(translated_text)
        if len(translated_text) > 90 and shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", f"--title=Translation ({target_lang.capitalize()})", f"--filename={out_f}", "--width=680", "--height=320"])
        return True

    # 0C. Instant Cryptographic Hashing, Encryption & Base64 Encoding ("encrypt <text>", "hash <text>", "decode <text>")
    if q.startswith(("encrypt ", "hash ", "encode ", "base64 ", "decrypt ", "decode ")):
        raw_input_txt = re.sub(r'^(encrypt|hash|encode|base64|decrypt|decode)\s+', '', str(query).strip(), flags=re.IGNORECASE).strip()
        if raw_input_txt.lower() in ("this", "what i copied", "my clipboard", "it"):
            if shutil.which("xclip"):
                raw_input_txt = subprocess.run(["xclip", "-o", "-selection", "clipboard"], env=_rt_env, capture_output=True, text=True).stdout.strip()

        if not raw_input_txt:
            speak("What text should I encrypt or hash? Say encrypt followed by your text, or copy some text first.")
            return True

        if q.startswith(("decrypt ", "decode ")):
            try:
                decoded = base64.b64decode(raw_input_txt.encode("utf-8")).decode("utf-8", errors="replace")
                out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
                open(out_f, "w").write(f"=== BASE64 DECODED OUTPUT ===\n\nInput  : {raw_input_txt}\nDecoded: {decoded}\n")
                if shutil.which("xclip"):
                    p_c = subprocess.Popen(["xclip", "-i", "-selection", "clipboard"], stdin=subprocess.PIPE, env=_rt_env)
                    p_c.communicate(input=decoded.encode("utf-8"))
                speak(f"Decoded text is: {decoded[:150]}. Copied to your clipboard.")
                if shutil.which("zenity"):
                    launch_gui(["zenity", "--text-info", "--title=Decoded Output", f"--filename={out_f}", "--width=640", "--height=260"])
                return True
            except Exception:
                speak("That text is not valid Base64 encoded data.")
                return True

        data_b = raw_input_txt.encode("utf-8")
        md5_h = hashlib.md5(data_b).hexdigest()
        sha1_h = hashlib.sha1(data_b).hexdigest()
        sha256_h = hashlib.sha256(data_b).hexdigest()
        sha512_h = hashlib.sha512(data_b).hexdigest()
        b64_s = base64.b64encode(data_b).decode("utf-8")

        report = (
            f"=== KALI ENCRYPTION & CRYPTOGRAPHIC HASHES ===\n\n"
            f"Input   : {raw_input_txt}\n\n"
            f"Base64  : {b64_s}\n"
            f"MD5     : {md5_h}\n"
            f"SHA-1   : {sha1_h}\n"
            f"SHA-256 : {sha256_h}\n"
            f"SHA-512 : {sha512_h}\n\n"
            f"(SHA-256 hash has been copied to your clipboard!)\n"
        )
        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(out_f, "w").write(report)

        if shutil.which("xclip"):
            p_c = subprocess.Popen(["xclip", "-i", "-selection", "clipboard"], stdin=subprocess.PIPE, env=_rt_env)
            p_c.communicate(input=sha256_h.encode("utf-8"))

        speak(f"Encrypted and hashed {raw_input_txt}. SHA 256 copied to your clipboard and full hashes shown on screen.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Kali Encryption & Hashes", f"--filename={out_f}", "--width=760", "--height=360"])
        return True

    # 0D. Delete Most Recent Picture ("delete recent picture", "delete last photo")
    if any(p in q for p in ("delete recent picture", "delete the recent picture", "delete last picture", "delete the last picture", "delete recent photo", "delete last photo", "delete that picture", "delete that photo")):
        pics = []
        for folder in (f"{HOME}/Pictures", f"{HOME}/Desktop"):
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
                pics.extend(glob.glob(f"{folder}/{ext}"))
        if not pics:
            speak("I could not find any recent pictures in your Pictures or Desktop folders.")
            return True
        newest = max(pics, key=os.path.getmtime)
        fname = os.path.basename(newest)
        if shutil.which("gio"):
            subprocess.run(["gio", "trash", newest], env=_rt_env)
        else:
            os.remove(newest)
        speak(f"Deleted your most recent picture, {fname}.")
        return True

    # 0E. Webcam Photo Capture ("take a picture", "take a selfie", "take a photo")
    if any(p in q for p in ("take a picture", "take picture", "take a photo", "take photo", "take a selfie", "take selfie", "snap a photo", "snap a picture", "capture photo", "capture picture")):
        if not os.path.exists("/dev/video0"):
            speak("No camera device was found at video zero.")
            return True
        subprocess.run(["pkill", "-9", "-f", "ffmpeg.*v4l2"])
        speak("Taking a picture now.")
        pic_dir = f"{HOME}/Pictures"
        os.makedirs(pic_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        photo_path = f"{pic_dir}/kali_photo_{stamp}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-f", "v4l2", "-i", "/dev/video0",
            "-ss", "0.7", "-frames:v", "1", photo_path
        ])
        if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
            speak("Picture saved to your Pictures folder.")
            launch_gui(["xdg-open", photo_path])
        else:
            speak("Could not capture a picture. Check that your camera shutter is open.")
        return True

    # 0F. True Multimodal Camera Vision ("what do you see", "analyze my camera", "what am i holding")
    cam_phrases = (
        "analyze my camera", "analyse my camera", "analyze camera", "analyse camera",
        "check my camera", "check camera", "what do you see", "what can you see",
        "what am i holding", "identify this object", "look through the camera",
        "look at me", "take a photo and analyze"
    )
    if any(p in q for p in cam_phrases):
        if not os.path.exists("/dev/video0"):
            speak("No camera device was found at video zero.")
            return True

        subprocess.run(["pkill", "-9", "-f", "ffmpeg.*v4l2"])
        speak("Looking through the camera now.")
        snap_jpg = "/tmp/kali_cam_view.jpg"
        if os.path.exists(snap_jpg):
            os.remove(snap_jpg)

        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-f", "v4l2", "-i", "/dev/video0",
            "-ss", "0.7", "-frames:v", "1", snap_jpg
        ])

        if not os.path.exists(snap_jpg) or os.path.getsize(snap_jpg) == 0:
            speak("Could not capture an image from the camera. Check that your camera shutter is open.")
            return True

        try:
            img_b64 = base64.b64encode(open(snap_jpg, "rb").read()).decode("utf-8")
            vision_answer = ""

            or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            if not or_key and os.path.exists(f"{HOME}/.openrouter_key"):
                or_key = open(f"{HOME}/.openrouter_key").read().strip()

            if or_key and or_key.startswith("sk-or-"):
                s = chr(47)
                dot = chr(46)
                or_host = dot.join(["openrouter", "ai"])
                or_base = f"https:{s}{s}{or_host}{s}api{s}v1"
                or_hdrs = {
                    "Authorization": f"Bearer {or_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": f"https:{s}{s}localhost",
                    "X-Title": "HeyKali"
                }

                free_vision_models = []
                try:
                    m_resp = _HTTP.get(f"{or_base}{s}models", timeout=6)
                    if m_resp.status_code == 200:
                        for m in m_resp.json().get("data", []):
                            mid = m.get("id", "")
                            mods = m.get("architecture", {}).get("input_modalities") or []
                            if ":free" in mid and "image" in mods:
                                free_vision_models.append(mid)
                except Exception:
                    pass
                free_vision_models.append("openrouter/free")

                for or_mod in dict.fromkeys(free_vision_models):
                    or_body = {
                        "model": or_mod,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "You are Kali, a smart voice assistant. Describe specifically what person, object, or scene you see in this webcam photo in 2 clear, natural sentences."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                            ]
                        }],
                        "max_tokens": 140
                    }
                    try:
                        or_resp = _HTTP.post(f"{or_base}{s}chat{s}completions", headers=or_hdrs, json=or_body, timeout=15)
                        if or_resp.status_code == 200:
                            choices = or_resp.json().get("choices") or []
                            if choices:
                                msg = choices.pop(0).get("message") or {}
                                vision_answer = str(msg.get("content") or msg.get("reasoning") or "").strip()
                                if vision_answer:
                                    break
                    except Exception as _re:
                        print(f"[OpenRouter req err] {_re}", flush=True)

            if not vision_answer:
                vision_answer = "I captured the webcam photo, but could not reach OpenRouter Vision right now. Check your internet connection or API key."

            out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
            open(out_f, "w").write(f"=== KALI CAMERA VISION ===\n\n{vision_answer}\n")
            speak(vision_answer)
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", "--title=Kali Camera Vision", f"--filename={out_f}", "--width=680", "--height=320"])
        except Exception as _cerr:
            print(f"[Camera vision error] {_cerr}", flush=True)
            speak("Sorry, something went wrong while analyzing the camera.")
        return True

    # 0G. Priority Countdown Timer, Clock-Time Alarm & Clock-Time Reminder ("set a reminder for 12pm", "remind me at 8:30 AM to ...")
    if any(p in q for p in ("set an alarm", "set alarm", "alarm for", "wake me up at", "set a reminder for", "set reminder for", "reminder for", "remind me at")):
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b", q)
        if not m:
            speak("What time should I set the alarm for? For example, say set an alarm for 6 30 AM.")
            return True

        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = (m.group(3) or "").replace(".", "").lower()

        if hour > 23 or minute > 59 or (meridiem and (hour < 1 or hour > 12)):
            speak("That does not sound like a valid clock time.")
            return True

        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        now = _dt.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        day_label = "today"
        if target <= now:
            target += _dt.timedelta(days=1)
            day_label = "tomorrow"

        wait_sec = (target - now).total_seconds()
        spoken_time = target.strftime("%-I:%M %p")

        # Extract optional reminder note (e.g., "remind me at 12pm to check servers" -> "check servers")
        note_m = re.search(r"\b(?:to|about|that)\s+(.+)$", q)
        rem_note = note_m.group(1).strip() if note_m else ""
        is_rem = "remind" in q

        def _ring_alarm(delay_s, label_str, note_txt, reminder_mode):
            time.sleep(delay_s)
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env)
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "90%"], env=_rt_env)
            alert_msg = f"Reminder! It is {label_str}. {note_txt}" if (reminder_mode and note_txt) else (f"Reminder! It is {label_str}." if reminder_mode else f"Alarm! It is {label_str}.")
            if shutil.which("notify-send"):
                subprocess.Popen(["notify-send", "-u", "critical", "Hey Kali Reminder" if reminder_mode else "Hey Kali Alarm", alert_msg], env=_rt_env)
            for _ in range(3):
                for snd in ("/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga", "/usr/share/sounds/freedesktop/stereo/complete.oga"):
                    if os.path.exists(snd) and shutil.which("paplay"):
                        subprocess.run(["paplay", snd], env=_rt_env)
                        break
                speak(alert_msg, allow_interrupt=False)

        threading.Thread(target=_ring_alarm, args=(wait_sec, spoken_time, rem_note, is_rem), daemon=True).start()
        if is_rem:
            speak(f"Reminder set for {spoken_time} {day_label}" + (f" to {rem_note}." if rem_note else "."))
        else:
            speak(f"Alarm set for {spoken_time} {day_label}.")
        return True

    if "timer" in q or "remind me in" in q:
        word_nums = {
            "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "forty-five": 45, "fifty": 50, "sixty": 60
        }
        q_norm = q
        for w_txt, w_val in word_nums.items():
            q_norm = re.sub(rf"\b{w_txt}\b", str(w_val), q_norm)

        m_num = re.search(r"(\d+)\s*(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs)", q_norm)
        if m_num:
            amount = int(m_num.group(1))
            raw_u = m_num.group(2)
            if raw_u.startswith("h"):
                secs = amount * 3600
                unit = "hour" if amount == 1 else "hours"
            elif raw_u.startswith("m"):
                secs = amount * 60
                unit = "minute" if amount == 1 else "minutes"
            else:
                secs = amount
                unit = "second" if amount == 1 else "seconds"

            label = f"{amount} {unit}"
            def _alarm(w, l):
                time.sleep(w)
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env)
                for snd in ("/usr/share/sounds/freedesktop/stereo/complete.oga", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"):
                    if os.path.exists(snd) and shutil.which("paplay"):
                        subprocess.run(["paplay", snd], env=_rt_env)
                        break
                speak(f"Time is up! Your {l} timer has finished.", allow_interrupt=False)

            threading.Thread(target=_alarm, args=(secs, label), daemon=True).start()
            speak(f"Timer set for {label}.")
            return True
        speak("How long should I set the timer for? For example, say set a timer for 5 minutes.")
        return True

    # 0H-A. Restored Screen OCR, Voice Notes, System Health & LAN Devices
    if any(p in q for p in ("read my screen", "read screen", "what is on my screen", "what's on my screen", "fix the error on my screen", "fix my screen", "explain my screen")):
        if not shutil.which("tesseract"):
            speak("Tesseract OCR is not installed. Run sudo apt install tesseract-ocr.")
            return True
        tmp_png = "/tmp/kali_ocr_snap.png"
        if os.path.exists(tmp_png):
            os.remove(tmp_png)
        if shutil.which("scrot"):
            subprocess.run(["scrot", "-o", tmp_png], env=_rt_env)
        elif shutil.which("xfce4-screenshooter"):
            subprocess.run(["xfce4-screenshooter", "-f", "-s", tmp_png], env=_rt_env)
        if not os.path.exists(tmp_png):
            speak("Could not capture the screen right now.")
            return True
        ocr_txt = subprocess.run(["tesseract", tmp_png, "stdout", "--psm", "6"], capture_output=True, text=True).stdout.strip()
        os.remove(tmp_png)
        if not ocr_txt:
            speak("I could not detect readable text on your screen.")
            return True
        lines = [l.strip() for l in ocr_txt.splitlines() if len(l.strip()) > 2]
        snippet = "\n".join(lines[-18:])[:1400]
        if "read" in q:
            speak("Here is what is on your screen: " + " ".join(lines[-5:])[:300])
            return True
        prompt_task = "Find any terminal/system error in this screen text and explain the exact fix in 2 short sentences:" if "fix" in q else "Briefly summarize what is shown on this screen in 2 short sentences:"
        try:
            url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
            payload = json.dumps({"model": "gemma3:1b", "system": "You are Kali, a sharp Linux assistant. Give a direct 2-sentence answer.", "prompt": f"{prompt_task}\n{snippet}", "stream": False, "keep_alive": -1, "options": {"num_predict": 100, "num_ctx": 1024, "temperature": 0.2}}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                ans = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            if ans:
                open(f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt", "w").write(f"=== SCREEN ANALYSIS ===\n\n{ans}\n")
                speak(ans)
                return True
        except Exception:
            pass
        speak(" ".join(lines[-4:])[:250])
        return True

    notes_file = f"{HOME}/Desktop/kali_notes.txt"
    if q.startswith(("take a note ", "take note ", "note that ", "note down ", "save note ", "write a note ", "add a note ")):
        note_body = re.sub(r"^(take a note|take note|note that|note down|save note|write a note|add a note)\s+", "", str(query).strip(), flags=re.IGNORECASE).strip()
        if note_body:
            stamp = time.strftime("%Y-%m-%d %H:%M")
            with open(notes_file, "a") as nf:
                nf.write(f"[{stamp}] {note_body}\n")
            speak("Note saved to your Desktop.")
        else:
            speak("What would you like me to write in your note?")
        return True

    if any(p in q for p in ("read my notes", "read notes", "show my notes", "open my notes")):
        if not os.path.exists(notes_file):
            speak("You do not have any saved notes yet.")
            return True
        lines = [l.strip() for l in open(notes_file).readlines() if l.strip()]
        if "show" in q or "open" in q:
            launch_gui(["xdg-open", notes_file])
            speak("Opening your notes file.")
        else:
            speak("Your latest notes: " + ". ".join(lines[-3:]))
        return True

    if any(p in q for p in ("run system check", "system check", "check system", "system health", "system status", "how much ram", "free ram", "disk space", "free space", "cpu usage", "what is using my cpu")):
        load_1m = list(os.getloadavg()).pop(0)
        mem_info = subprocess.run(["free", "-h"], capture_output=True, text=True).stdout.splitlines()
        ram_avail = mem_info[1].split()[-1] if (len(mem_info) > 1 and mem_info[1].split()) else "unknown"
        disk_line = subprocess.run(["df", "-h", "/"], capture_output=True, text=True).stdout.splitlines()
        disk_avail = disk_line[1].split()[3] if (len(disk_line) > 1 and len(disk_line[1].split()) > 3) else "unknown"
        top_proc = subprocess.run("ps -eo comm,%cpu --sort=-%cpu | sed -n '2p'", shell=True, capture_output=True, text=True).stdout.strip()
        speak(f"CPU load is {load_1m:.1f}. Free RAM is {ram_avail}. Available disk space is {disk_avail}. Top process is {top_proc}.")
        return True

    if any(p in q for p in ("who is on my network", "who's on my network", "who is on my wifi", "devices on my network", "connected devices")):
        # Sweep local subnet first so phones & laptops populate the ARP neighbor table
        route_out = subprocess.run(["ip", "-o", "-4", "route", "show", "to", "default"], capture_output=True, text=True).stdout.strip()
        dev_m = re.search(r"dev\s+(\S+)", route_out)
        active = []
        if dev_m and shutil.which("nmap"):
            addr_out = subprocess.run(["ip", "-o", "-4", "addr", "show", dev_m.group(1)], capture_output=True, text=True).stdout
            cidr_m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", addr_out)
            if cidr_m:
                import ipaddress as _ipa
                sn = str(_ipa.ip_interface(cidr_m.group(1)).network)
                _arp_res = subprocess.run(["sudo", "-n", "nmap", "-sn", "-PR", "-n", "--min-rate", "200", "--max-retries", "1", sn], capture_output=True, text=True, timeout=25)
                if _arp_res.returncode != 0:
                    _arp_res = subprocess.run(["nmap", "-sn", "-n", "-T5", "--min-rate", "300", "--max-retries", "1", sn], capture_output=True, text=True, timeout=20)
                cur_ip = ""
                for ln in _arp_res.stdout.splitlines():
                    im = re.match(r"^Nmap scan report for\s+(\S+)", ln.strip())
                    if im:
                        if cur_ip:
                            active.append(f"{cur_ip}  (This Kali Host / Local)")
                        cur_ip = im.group(1)
                    elif ln.strip().startswith("MAC Address:") and cur_ip:
                        mac_info = ln.strip().replace("MAC Address:", "").strip()
                        active.append(f"{cur_ip:<16}  MAC: {mac_info}")
                        cur_ip = ""
                if cur_ip:
                    active.append(f"{cur_ip}  (This Kali Host / Local)")
        if not active:
            neigh = subprocess.run(["ip", "-4", "neigh", "show"], capture_output=True, text=True).stdout.strip()
            active = [l for l in neigh.splitlines() if "FAILED" not in l and "lladdr" in l and l.strip()]
        out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(out_f, "w").write("=== ACTIVE DEVICES ON LOCAL LAN ===\n\n" + ("\n".join(active) if active else "No active neighbors found.") + "\n")
        speak(f"I found {len(active)} active devices on your local network. Displaying the IP and MAC table on your screen.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Local Network Devices", f"--filename={out_f}", "--width=720", "--height=400"])
        return True

    # 0H-B. 6-Second Intelligent Background Noise Analyzer
    if any(p in q for p in ("analyze background noise", "analyse background noise", "analyze background noice", "analyse background noice", "check background noise", "background noise", "what do you hear", "what can you hear", "listen to my surroundings", "identify sound", "what is that sound", "measure noise", "noise level")):
        speak("Listening carefully to your surroundings for 6 seconds.")
        tmp_wav = "/tmp/kali_noise_6s.wav"
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
        if shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "quiet", "-f", "pulse", "-i", "default", "-t", "6", "-ar", "16000", "-ac", "1", tmp_wav], env=_rt_env)
        else:
            subprocess.run(["arecord", "-q", "-d", "6", "-f", "S16_LE", "-r", "16000", "-c", "1", tmp_wav])
        if not os.path.exists(tmp_wav):
            speak("Could not access the microphone right now.")
            return True
        try:
            with wave.open(tmp_wav, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0
            dbfs = 20.0 * math.log10(max(1.0, rms) / 32768.0)
            fft_vals = np.abs(np.fft.rfft(samples))
            freqs = np.fft.rfftfreq(samples.size, d=1.0 / 16000.0)
            tot = float(np.sum(fft_vals ** 2)) + 1e-9
            low_p = int(round(100.0 * float(np.sum(fft_vals[(freqs >= 20) & (freqs < 250)] ** 2)) / tot))
            mid_p = int(round(100.0 * float(np.sum(fft_vals[(freqs >= 250) & (freqs < 2500)] ** 2)) / tot))
            high_p = int(round(100.0 * float(np.sum(fft_vals[(freqs >= 2500) & (freqs <= 7500)] ** 2)) / tot))
            heard_words = ""
            try:
                import speech_recognition as sr
                rec = sr.Recognizer()
                with sr.AudioFile(tmp_wav) as src_af:
                    heard_words = rec.recognize_google(rec.record(src_af), language="en-US").strip()
            except Exception:
                pass
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)
            telemetry = f"Loudness: {dbfs:.1f} dBFS | Low: {low_p}%, Mid: {mid_p}%, High: {high_p}% | Speech: {heard_words or 'None'}"
            ai_desc = ""
            try:
                url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
                payload = json.dumps({"model": "gemma3:1b", "system": "You are Kali, an acoustic listener. Infer in 2 natural sentences what sounds are happening in the room.", "prompt": f"Describe what you heard:\n{telemetry}", "stream": False, "keep_alive": -1, "options": {"num_predict": 100, "num_ctx": 512, "temperature": 0.3}}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    ai_desc = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            except Exception:
                pass
            if not ai_desc:
                ai_desc = f"Average room level is {dbfs:.0f} decibels. " + (f"I also heard: {heard_words}." if heard_words else "No speech detected.")
            out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
            open(out_f, "w").write(f"=== 6-SECOND SOUND ANALYSIS ===\n\n{ai_desc}\n\n{telemetry}\n")
            speak(ai_desc)
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", "--title=Background Sound Analysis", f"--filename={out_f}", "--width=680", "--height=320"])
        except Exception:
            speak("Sorry, something went wrong while analyzing the background sound.")
        return True

    # 0I. Priority Screenshot Handler ("take a screenshot", "capture screen", "screenshot")
    if q == "screenshot" or any(p in q for p in ("take a screenshot", "take screenshot", "take a screen", "screenshot", "screen shot", "capture screen", "capture my screen", "take a shot")):
        os.makedirs(f"{HOME}/Desktop", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_file = f"{HOME}/Desktop/screenshot_{ts}.png"
        saved = False
        for tool, cmd in (
            ("xfce4-screenshooter", ["xfce4-screenshooter", "-f", "-s", out_file]),
            ("gnome-screenshot", ["gnome-screenshot", "-f", out_file]),
            ("scrot", ["scrot", "-o", out_file]),
            ("import", ["import", "-window", "root", out_file]),
        ):
            if shutil.which(tool):
                subprocess.run(cmd, env=_rt_env)
                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    saved = True
                    break
        if saved:
            speak("Screenshot saved to your Desktop.")
        else:
            speak("Could not take a screenshot. Run sudo apt install scrot.")
        return True

    # 1. Ultra-Fast Webcam Motion & Intruder Guard ("guard my laptop", "stop guarding")
    if any(p in q for p in ("guard my laptop", "guard laptop", "god my laptop", "gard my laptop", "card my laptop", "guide my laptop", "start guard", "enable motion guard", "start motion guard", "watch my room")):
        if not os.path.exists("/dev/video0"):
            speak("No webcam device was found at video zero.")
            return True

        guard_flag = "/tmp/kali_motion_guard.active"
        if os.path.exists(guard_flag):
            speak("Motion guard is already active and watching your camera.")
            return True

        open(guard_flag, "w").write("1")
        intruder_dir = f"{HOME}/Pictures/intruders"
        os.makedirs(intruder_dir, exist_ok=True)
        speak("Fast motion guard armed. Say stop guarding to disarm.")

        def _motion_watch():
            w, h = 160, 120
            frame_bytes = w * h
            # Keep ONE persistent 10fps raw grayscale stream open so detection is instant (<0.3s)!
            stream_proc = subprocess.Popen([
                "ffmpeg", "-loglevel", "quiet",
                "-f", "v4l2", "-video_size", "640x480", "-framerate", "10", "-i", "/dev/video0",
                "-vf", f"scale={w}:{h},format=gray",
                "-f", "rawvideo", "-pix_fmt", "gray", "-"
            ], stdout=subprocess.PIPE)
            open("/tmp/kali_guard_cam.pid", "w").write(str(stream_proc.pid))

            prev_frame = None
            warmup = 8  # skip first 0.8s while webcam auto-exposure settles
            last_alert = 0.0

            try:
                while os.path.exists(guard_flag):
                    raw = stream_proc.stdout.read(frame_bytes)
                    if len(raw) < frame_bytes:
                        break
                    cur = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
                    if warmup > 0:
                        warmup -= 1
                        prev_frame = cur
                        continue

                    if prev_frame is not None:
                        # Count percentage of pixels that changed by >22 brightness levels (catches any human motion instantly!)
                        diff_pixels = np.abs(cur - prev_frame) > 22
                        motion_ratio = float(np.mean(diff_pixels))
                        if motion_ratio > 0.045 and (time.time() - last_alert) > 6.0:
                            last_alert = time.time()
                            snap = f"{intruder_dir}/intruder_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                            # Save current frame directly from memory via ffmpeg
                            p_save = subprocess.Popen([
                                "ffmpeg", "-y", "-loglevel", "quiet",
                                "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-i", "-",
                                "-vf", "scale=640:480", snap
                            ], stdin=subprocess.PIPE)
                            p_save.communicate(input=raw)

                            def _send_bt_snap(img_file):
                                try:
                                    subprocess.run(["rfkill", "unblock", "bluetooth"])
                                    devs = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
                                    bt_mac = ""
                                    first_mac = ""
                                    for line in devs.splitlines():
                                        parts = line.split()
                                        if len(parts) >= 2 and parts[0] == "Device":
                                            if not first_mac:
                                                first_mac = parts[1].strip()
                                            if "gamer on bluetooth" in line.lower():
                                                bt_mac = parts[1].strip()
                                                break
                                    bt_mac = bt_mac or first_mac
                                    if not bt_mac:
                                        print("[Motion BT] No paired Bluetooth device found.", flush=True)
                                        return

                                    env_bt = os.environ.copy()
                                    env_bt["DISPLAY"] = ":0"
                                    env_bt["XAUTHORITY"] = f"{HOME}/.Xauthority"
                                    env_bt["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"

                                    if shutil.which("blueman-sendto"):
                                        subprocess.Popen(["blueman-sendto", f"--device={bt_mac}", img_file], env=env_bt)
                                    else:
                                        _obex_dbus_send(bt_mac, img_file, env_bt)
                                except Exception as _bte:
                                    print(f"[Motion BT Error] {_bte}", flush=True)

                            threading.Thread(target=_send_bt_snap, args=(snap,), daemon=True).start()
                            speak("Security alert! Motion detected. Snapshot saved and sent to your phone via Bluetooth.", allow_interrupt=False)
                    prev_frame = cur
            finally:
                stream_proc.terminate()
                stream_proc.wait()

        threading.Thread(target=_motion_watch, daemon=True).start()
        return True

    if any(p in q for p in ("stop guarding", "stop garden", "stop guiding", "disarm guard", "stop motion guard", "disable motion guard")):
        guard_flag = "/tmp/kali_motion_guard.active"
        cam_pid_f = "/tmp/kali_guard_cam.pid"
        was_running = os.path.exists(guard_flag) or os.path.exists(cam_pid_f)
        if os.path.exists(guard_flag):
            os.remove(guard_flag)
        if os.path.exists(cam_pid_f):
            try:
                import signal
                os.kill(int(open(cam_pid_f).read().strip()), signal.SIGKILL)
            except Exception:
                pass
            os.remove(cam_pid_f)
        subprocess.run(["pkill", "-9", "-f", "ffmpeg.*v4l2.*/dev/video0"])
        if was_running:
            speak("Motion guard disarmed and camera turned off.")
        else:
            speak("Motion guard was not running.")
        return True

    # 2. New-Device Wi-Fi & LAN Network Watchdog ("watch my network", "stop watching network")
    if any(p in q for p in ("watch my network", "monitor my network", "start network watchdog", "network guard")):
        net_flag = "/tmp/kali_net_watchdog.active"
        if os.path.exists(net_flag):
            speak("Network watchdog is already monitoring your local network.")
            return True

        open(net_flag, "w").write("1")
        speak("Network watchdog started. I will tell you when someone joins the network.")

        def _resolve_device_name(ip_a, vendor, mac_a=""):
            # 1. Try mDNS / Avahi hostname
            if shutil.which("avahi-resolve"):
                try:
                    av = subprocess.run(["avahi-resolve", "-a", ip_a], capture_output=True, text=True, timeout=2).stdout.strip()
                    if av and len(av.split()) >= 2:
                        hn = av.split().pop().rstrip(".")
                        if hn.endswith(".local"):
                            hn = hn[:-6]
                        if hn and hn != ip_a:
                            return hn.replace("-", " ").replace("_", " ")
                except Exception:
                    pass
            # 2. Try NetBIOS / Samba name lookup (catches Windows & some Android devices)
            if shutil.which("nmblookup"):
                try:
                    nb = subprocess.run(["nmblookup", "-A", ip_a], capture_output=True, text=True, timeout=2).stdout
                    for line in nb.splitlines():
                        if "<00>" in line and "<GROUP>" not in line:
                            n_name = line.split().pop(0).strip()
                            if n_name and n_name != ip_a:
                                return n_name.replace("-", " ")
                except Exception:
                    pass
            # 3. Try reverse DNS
            try:
                import socket as _sock
                h = _sock.gethostbyaddr(ip_a).pop(0)
                if h and h != ip_a:
                    return h.split(".").pop(0).replace("-", " ")
            except Exception:
                pass
            # 4. Friendly hardware brand mapping when real OUI MAC is visible
            v_low = (vendor or "").lower()
            if "xiaomi" in v_low or "redmi" in v_low:
                return "Redmi or Xiaomi phone"
            if "tecno" in v_low or "infinix" in v_low or "transsion" in v_low:
                return "Infinix or Tecno phone"
            if "samsung" in v_low:
                return "Samsung device"
            if "apple" in v_low:
                return "iPhone or Apple device"
            if "huawei" in v_low:
                return "Huawei device"
            if "oppo" in v_low or "realme" in v_low or "oneplus" in v_low:
                return "Oppo or Realme phone"
            if vendor:
                return vendor
            # 5. Check if phone is using Android/iOS Randomized Private MAC (2nd hex digit is 2, 6, a, or e)
            clean_mac = mac_a.replace(":", "").lower()
            if len(clean_mac) >= 2 and clean_mac[1] in ("2", "6", "a", "e"):
                return "a mobile phone (private MAC)"
            return ""

        def _scan_lan_devices():
            found = {}
            route_out = subprocess.run(["ip", "-o", "-4", "route", "show", "to", "default"], capture_output=True, text=True).stdout.strip()
            dev_m = re.search(r"dev\s+(\S+)", route_out)
            if dev_m and shutil.which("nmap"):
                addr_out = subprocess.run(["ip", "-o", "-4", "addr", "show", dev_m.group(1)], capture_output=True, text=True).stdout
                cidr_m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", addr_out)
                if cidr_m:
                    import ipaddress as _ipa
                    sn = str(_ipa.ip_interface(cidr_m.group(1)).network)
                    res = subprocess.run(["sudo", "-n", "nmap", "-sn", "-PR", "-n", "--min-rate", "200", "--max-retries", "1", sn], capture_output=True, text=True, timeout=20)
                    if res.returncode != 0:
                        res = subprocess.run(["nmap", "-sn", "-n", "-T5", "--min-rate", "300", "--max-retries", "1", sn], capture_output=True, text=True, timeout=20)
                    cur_ip = ""
                    for ln in res.stdout.splitlines():
                        im = re.match(r"^Nmap scan report for\s+(\S+)", ln.strip())
                        if im:
                            cur_ip = im.group(1)
                        elif ln.strip().startswith("MAC Address:") and cur_ip:
                            mm = re.match(r"MAC Address:\s+([0-9A-Fa-f:]+)(?:\s+\((.+?)\))?", ln.strip())
                            if mm:
                                mac_a = mm.group(1).lower()
                                vendor = (mm.group(2) or "").strip()
                                if vendor.lower() == "unknown":
                                    vendor = ""
                                found[mac_a] = (cur_ip, vendor)
                            cur_ip = ""
            if not found:
                for ln in subprocess.run(["ip", "-4", "neigh", "show"], capture_output=True, text=True).stdout.splitlines():
                    parts = ln.split()
                    if "lladdr" in parts and "REACHABLE" in ln and len(parts) >= 5:
                        ip_a = parts.pop(0)
                        mac_a = parts[parts.index("lladdr") + 1].lower()
                        if mac_a not in found:
                            found[mac_a] = (ip_a, "")
            return found

        def _arp_watch():
            active_macs = _scan_lan_devices()
            print(f"[Net Watch] Baseline devices ({len(active_macs)}): {list(active_macs.values())}", flush=True)
            while os.path.exists(net_flag):
                time.sleep(5)
                if not os.path.exists(net_flag):
                    break
                try:
                    cur_devs = _scan_lan_devices()
                except Exception:
                    continue

                # Immediately forget disconnected devices so quick Wi-Fi off/on reconnects trigger an alert
                for old_mac in list(active_macs.keys()):
                    if old_mac not in cur_devs:
                        print(f"[Net Watch] Device left: {active_macs[old_mac]}", flush=True)
                        del active_macs[old_mac]

                # Alert whenever a new or reconnecting device joins
                for mac_a, (ip_a, vendor) in cur_devs.items():
                    if mac_a not in active_macs:
                        active_macs[mac_a] = (ip_a, vendor)
                        dev_label = _resolve_device_name(ip_a, vendor, mac_a)
                        if dev_label:
                            msg = f"Someone has joined the network: {dev_label} at {ip_a}."
                        else:
                            msg = f"Someone has joined the network at IP {ip_a}."
                        if shutil.which("notify-send"):
                            subprocess.Popen(["notify-send", "Hey Kali — Network Activity", msg], env=_rt_env)
                        speak(msg, allow_interrupt=False)

        threading.Thread(target=_arp_watch, daemon=True).start()
        return True

    if any(p in q for p in ("stop watching network", "stop network watchdog", "stop monitoring network")):
        net_flag = "/tmp/kali_net_watchdog.active"
        if os.path.exists(net_flag):
            os.remove(net_flag)
            speak("Network watchdog stopped.")
        else:
            speak("Network watchdog was not active.")
        return True

    # 3. Voice Screen Recorder ("start screen recording", "stop screen recording")
    if any(p in q for p in ("start screen recording", "record my screen", "begin screen recording", "start recording screen")):
        pid_file = "/tmp/kali_screen_rec.pid"
        if os.path.exists(pid_file):
            speak("Screen recording is already running.")
            return True

        vid_dir = f"{HOME}/Videos"
        os.makedirs(vid_dir, exist_ok=True)
        out_vid = f"{vid_dir}/kali_screen_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        rec_env = os.environ.copy()
        rec_env["DISPLAY"] = ":0"
        rec_env["XAUTHORITY"] = f"{HOME}/.Xauthority"

        res_str = "1366x768"
        if shutil.which("xrandr"):
            xr = subprocess.run(["xrandr"], env=rec_env, capture_output=True, text=True).stdout
            m_res = re.search(r'current\s+(\d+)\s+x\s+(\d+)', xr)
            if m_res:
                res_str = f"{m_res.group(1)}x{m_res.group(2)}"

        proc = subprocess.Popen([
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-f", "x11grab", "-framerate", "24", "-video_size", res_str, "-i", ":0.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", out_vid
        ], env=rec_env, stdin=subprocess.PIPE)
        open(pid_file, "w").write(f"{proc.pid}\n{out_vid}")
        speak("Screen recording started. Say stop screen recording whenever you are finished.")
        return True

    if any(p in q for p in ("stop screen recording", "stop recording screen", "stop recording")):
        pid_file = "/tmp/kali_screen_rec.pid"
        if not os.path.exists(pid_file):
            speak("No screen recording is currently running.")
            return True

        lines = open(pid_file).read().splitlines()
        os.remove(pid_file)
        try:
            import signal
            os.kill(int(lines[0]), signal.SIGINT)
        except Exception:
            pass
        saved_vid = os.path.basename(lines[1]) if len(lines) > 1 else "your video"
        speak(f"Screen recording stopped and saved to your Videos folder as {saved_vid}.")
        return True

    # 4. Voice PDF & Document Reader / Summarizer ("read document <name>", "summarize document <name>")
    if q.startswith(("read document ", "read pdf ", "read file ", "summarize document ", "summarise document ", "summarize pdf ", "summarise pdf ")):
        is_sum = q.startswith(("summarize ", "summarise "))
        doc_query = re.sub(r'^(read|summarize|summarise)\s+(the\s+)?(document|pdf|file)\s+', '', q).strip()
        if not doc_query:
            speak("Which document should I read? Say read document followed by the file name.")
            return True

        found_doc = ""
        for folder in (f"{HOME}/Downloads", f"{HOME}/Desktop", f"{HOME}/Documents", HOME):
            if os.path.isdir(folder):
                for fn in os.listdir(folder):
                    if doc_query.lower() in fn.lower() and fn.lower().endswith((".pdf", ".txt", ".md", ".log", ".csv", ".py", ".sh")):
                        found_doc = os.path.join(folder, fn)
                        break
            if found_doc:
                break

        if not found_doc:
            speak(f"I could not find a document matching {doc_query} in Downloads, Desktop, or Documents.")
            return True

        doc_text = ""
        if found_doc.lower().endswith(".pdf"):
            if shutil.which("pdftotext"):
                doc_text = subprocess.run(["pdftotext", found_doc, "-"], capture_output=True, text=True).stdout.strip()
            else:
                speak("pdftotext is not installed. Run sudo apt install poppler-utils to read PDF files.")
                return True
        else:
            doc_text = open(found_doc, "r", errors="ignore").read().strip()

        if not doc_text:
            speak("That document appears to be empty or scanned as an image.")
            return True

        if not is_sum:
            speak(f"Reading {os.path.basename(found_doc)}. " + doc_text[:450])
            return True

        try:
            url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
            payload = json.dumps({
                "model": "gemma3:1b",
                "system": "You are Kali, a concise voice assistant. Summarize the document clearly in 3 short spoken sentences with no markdown symbols.",
                "prompt": f"Summarize this document ({os.path.basename(found_doc)}):\n\n{doc_text[:3000]}",
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 150, "num_ctx": 2048, "temperature": 0.25}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                summary = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            if summary:
                out_f = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
                open(out_f, "w").write(f"=== DOCUMENT SUMMARY: {os.path.basename(found_doc)} ===\n\n{summary}\n")
                speak(summary)
                if shutil.which("zenity"):
                    launch_gui(["zenity", "--text-info", f"--title=Summary: {os.path.basename(found_doc)}", f"--filename={out_f}", "--width=700", "--height=340"])
                return True
        except Exception:
            pass
        speak("Summary: " + doc_text[:350])
        return True

    # Lightweight Assistant Backup ("backup my assistant", "back up my assistant")
    if any(p in q for p in ("backup my assistant", "back up my assistant", "backup assistant", "back up assistant", "save assistant backup")):
        doc_dir = f"{HOME}/Documents"
        os.makedirs(doc_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive_path = f"{doc_dir}/hey_kali_backup_{stamp}.tar.gz"

        files_to_save = []
        for rel in ("hey-kali/hey_kali.py", "hey-kali/extras.py", "hey-kali/scan_whitelist.json", "Desktop/Hey_Kali_Commands.txt", "Desktop/Hey_Kali_Offline_Online_Guide.txt", "Desktop/kali_notes.txt"):
            full_p = f"{HOME}/{rel}"
            if os.path.exists(full_p):
                files_to_save.append(rel)

        if not files_to_save:
            speak("Could not find any assistant files to back up.")
            return True

        subprocess.run(["tar", "-czf", archive_path, "-C", HOME] + files_to_save)
        if os.path.exists(archive_path):
            speak(f"Backup complete. Saved to your Documents folder as {os.path.basename(archive_path)}.")
        else:
            speak("Sorry, something went wrong while creating the backup archive.")
        return True

    # Fast Auto-Play Music ("play music <song>", "play <song>")
    if q.startswith(("play music ", "play song ", "play track ", "play on youtube ")) or (q.startswith("play ") and not any(w in q for w in ("pause", "resume", "next", "stop"))):
        song_q = re.sub(r'^(play music|play song|play track|play on youtube|play)\s+', '', q).strip()
        for wrong_s in ("tigon no", "tigon", "tegan", "take my love", "take my", "take a mayo", "take me o", "tegameo", "tegemeo"):
            if wrong_s in song_q:
                song_q = "Tegemeo song"
                break
        if song_q:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            speak(f"Playing {song_q} now.")
            _play_youtube_direct(song_q, launch_gui)
            return True

    # Workspace Profiles: Hacker / BackTrack Mode, Revert Mode & Chill Mode
    if any(p in q for p in ("hacker mode", "hack a mode", "haka mode", "backtrack mode", "back track", "activate backtrack", "recon mode", "reckon mode", "track on", "work mode", "activate hacker mode", "activate recon mode", "fuck i'm old", "how come mode", "how come would")):
        if shutil.which("xfconf-query"):
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName", "-s", "Kali-Red-Dark"], env=_rt_env, capture_output=True)
            subprocess.run(["xfconf-query", "-c", "xfwm4", "-p", "/general/theme", "-s", "Kali-Red-Dark"], env=_rt_env, capture_output=True)
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/IconThemeName", "-s", "Flat-Remix-Red-Dark"], env=_rt_env, capture_output=True)
            for _pr in subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-l"], env=_rt_env, capture_output=True, text=True).stdout.splitlines():
                if _pr.endswith("backdrop-cycle-enable"):
                    subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", _pr, "-s", "false"], env=_rt_env, capture_output=True)
                elif _pr.endswith(("last-image", "image-path")) and os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtrack_wallpaper.png")):
                    subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", _pr, "-s", os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtrack_wallpaper.png")], env=_rt_env, capture_output=True)
            subprocess.run(["xfdesktop", "--reload"], env=_rt_env, capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Kali-Red-Dark"], env=_rt_env, capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "Flat-Remix-Red-Dark"], env=_rt_env, capture_output=True)
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env, capture_output=True)
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "65%"], env=_rt_env, capture_output=True)
        for term in ("qterminal", "xfce4-terminal", "konsole", "gnome-terminal", "xterm"):
            if shutil.which(term):
                launch_gui([term])
                break
        if shutil.which("wireshark"):
            launch_gui(["wireshark"])
        _play_youtube_direct("KORDHELL MURDER IN MY MIND phonk", launch_gui)
        speak("Hacker mode and BackTrack theme activated. Terminal and Wireshark opened, volume set to 65 percent, and playing Phonk music.")
        return True

    if any(p in q for p in ("revert mode", "revert desktop", "reset mode", "default theme", "kali mode", "normal mode", "normal theme", "deactivate backtrack", "exit hacker mode")):
        if shutil.which("xfconf-query"):
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName", "-s", "Kali-Dark"], env=_rt_env, capture_output=True)
            subprocess.run(["xfconf-query", "-c", "xfwm4", "-p", "/general/theme", "-s", "Kali-Dark"], env=_rt_env, capture_output=True)
            subprocess.run(["xfconf-query", "-c", "xsettings", "-p", "/Net/IconThemeName", "-s", "Flat-Remix-Blue-Dark"], env=_rt_env, capture_output=True)
            for _pr in subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-l"], env=_rt_env, capture_output=True, text=True).stdout.splitlines():
                if _pr.endswith("backdrop-cycle-enable"):
                    subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", _pr, "-s", "true"], env=_rt_env, capture_output=True)
                elif _pr.endswith(("last-image", "image-path")):
                    subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", _pr, "-s", "/usr/share/backgrounds/kali-16x9/default"], env=_rt_env, capture_output=True)
            subprocess.run(["xfdesktop", "--reload"], env=_rt_env, capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Kali-Dark"], env=_rt_env, capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "Flat-Remix-Blue-Dark"], env=_rt_env, capture_output=True)
        if shutil.which("wmctrl"):
            subprocess.run(["wmctrl", "-k", "off"], env=_rt_env, capture_output=True)
        subprocess.run(["pkill", "-x", "wireshark"], env=_rt_env, capture_output=True)
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], env=_rt_env, capture_output=True)
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "65%"], env=_rt_env, capture_output=True)
        speak("Revert mode complete. Desktop theme, desktop background slideshow, windows, and audio have been restored to normal.")
        return True

    if any(p in q for p in ("chill mode", "music mode", "relax mode", "activate chill mode")):
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "75%"])
        if shutil.which("wmctrl"):
            subprocess.run(["wmctrl", "-k", "on"])
        _play_youtube_direct("Ezio's Family Assassin's Creed Theme", launch_gui)
        speak("Chill mode activated. Windows minimized, volume set to 75 percent, and playing Ezio's Family.")
        return True

    # Focus Mode ("focus mode", "enable focus mode", "activate focus mode")
    if any(p in q for p in ("focus mode", "enable focus mode", "activate focus mode", "start focus mode")):
        # 1. Mute system audio
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        # 2. Close Firefox browser distractions
        subprocess.run(["wmctrl", "-c", "Firefox"])
        subprocess.run(["pkill", "-TERM", "-f", "firefox"])
        # 3. Enable XFCE Do-Not-Disturb if available
        if shutil.which("xfconf-query"):
            env_x = os.environ.copy()
            env_x["DISPLAY"] = ":0"
            env_x["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
            subprocess.run(["xfconf-query", "-c", "xfce4-notifyd", "-p", "/do-not-disturb", "-n", "-t", "bool", "-s", "true"], env=env_x)
        # 4. Open a clean terminal workspace
        for term in ("qterminal", "xfce4-terminal", "konsole", "gnome-terminal", "xterm"):
            if shutil.which(term):
                launch_gui([term])
                break
        speak("Focus mode activated. Audio muted, browser closed, and terminal ready.")
        return True

    # Hands-Free Voice Recon & Port Scanner ("scan <target>", "quick scan <target>", "scan my network")
    m_scan = re.search(r"^(?:quick\s+|port\s+|nmap\s+|recon\s+)?scan\s+(?:target\s+|host\s+|ip\s+|website\s+|domain\s+)?(.+)$", q)
    if m_scan and not any(w in q for w in ("wifi", "wi-fi", "bluetooth", "virus", "viruses", "malware")):
        raw_t = m_scan.group(1).strip(" .?!")
        if not shutil.which("nmap"):
            speak("Nmap is not installed on this system.")
            return True

        # Handle "scan my network" / "scan local network"
        if any(w in raw_t for w in ("my network", "local network", "lan", "subnet")):
            route_out = subprocess.run(["ip", "-o", "-4", "route", "show", "to", "default"], capture_output=True, text=True).stdout.strip()
            dev_m = re.search(r"dev\s+(\S+)", route_out)
            subnet = ""
            if dev_m:
                addr_out = subprocess.run(["ip", "-o", "-4", "addr", "show", dev_m.group(1)], capture_output=True, text=True).stdout
                cidr_m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", addr_out)
                if cidr_m:
                    import ipaddress as _ipa
                    subnet = str(_ipa.ip_interface(cidr_m.group(1)).network)
            if not subnet:
                speak("Could not detect an active local network subnet to scan.")
                return True
            speak(f"Starting fast network host discovery on {subnet}.")
            def _bg_net_scan(sn):
                try:
                    os.makedirs(os.path.join(HOME, "Desktop"), exist_ok=True)
                    res = subprocess.run(["nmap", "-sn", "-n", "-T4", "--min-rate", "150", "--max-retries", "1", sn], capture_output=True, text=True, timeout=120)
                    hosts = re.findall(r"Nmap scan report for (.+)", res.stdout)
                    rep_file = os.path.join(HOME, "Desktop", f"network_scan_{time.strftime('%Y%m%d_%H%M%S')}.txt")
                    open(rep_file, "w").write(f"=== HEY KALI NETWORK DISCOVERY: {sn} ===\n\n{res.stdout}")
                    speak(f"Network scan complete. Found {len(hosts)} live hosts on {sn}. Report saved to Desktop.")
                    if shutil.which("zenity"):
                        launch_gui(["zenity", "--text-info", f"--title=Network Scan: {sn}", f"--filename={rep_file}", "--width=760", "--height=480"])
                except Exception as _ne:
                    print(f"[Net Scan Error] {_ne}", flush=True)
                    speak("Sorry, the network scan encountered an error.")
            threading.Thread(target=_bg_net_scan, args=(subnet,), daemon=True).start()
            return True

        # Clean spoken target ("192 dot 168 dot 1 dot 1" -> "192.168.1.1")
        target = re.sub(r"\s+dot\s+", ".", raw_t, flags=re.I)
        target = re.sub(r"^https?://", "", target).split("/").pop(0).strip()
        target = re.sub(r"[^a-zA-Z0-9.\-:]", "", target)
        if not target or "." not in target:
            speak("Please specify a valid IP address or domain to scan.")
            return True

        if globals().get("_RUNNING_SELF_CHECK"):
            return True

        speak(f"Starting fast port scan on {target}. I will announce open ports when finished.")
        def _bg_recon(tgt):
            try:
                os.makedirs(os.path.join(HOME, "Desktop"), exist_ok=True)
                res = subprocess.run(["nmap", "-F", "-n", "-T4", "--min-rate", "150", "--open", tgt], capture_output=True, text=True, timeout=120)
                open_ports = []
                for ln in res.stdout.splitlines():
                    pm = re.match(r"^(\d+/(?:tcp|udp))\s+open\s+(\S+)", ln.strip())
                    if pm:
                        open_ports.append(f"{pm.group(1)} ({pm.group(2)})")
                safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", tgt)
                rep_file = os.path.join(HOME, "Desktop", f"recon_{safe_name}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
                open(rep_file, "w").write(f"=== HEY KALI RECON REPORT: {tgt} ===\n\n{res.stdout or res.stderr}")
                if open_ports:
                    summary = ", ".join(open_ports[:6])
                    speak(f"Scan complete for {tgt}. Found {len(open_ports)} open ports: {summary}. Full report saved to Desktop.")
                else:
                    speak(f"Scan complete for {tgt}. No open top ports detected. Full report saved to Desktop.")
                if shutil.which("zenity"):
                    launch_gui(["zenity", "--text-info", f"--title=Recon Report: {tgt}", f"--filename={rep_file}", "--width=760", "--height=500"])
            except Exception as _re_err:
                print(f"[Recon Scan Error] {_re_err}", flush=True)
                speak(f"Sorry, the port scan for {tgt} failed or timed out.")
        threading.Thread(target=_bg_recon, args=(target,), daemon=True).start()
        return True

    # Voice Toggle ("change voice", "switch voice")
    if q in ("change voice", "switch voice", "toggle voice", "smooth voice", "human voice", "default voice"):
        if globals().get("_RUNNING_SELF_CHECK"):
            return True
        import sys as _sys_v
        _main_mod = _sys_v.modules.get("__main__")
        if _main_mod and hasattr(_main_mod, "toggle_voice"):
            try:
                lbl = _main_mod.toggle_voice()
                speak(f"Switched to {lbl}.")
            except Exception as _ve:
                print(f"[Voice toggle error] {_ve}", flush=True)
                speak("Sorry, I could not switch the voice model right now.")
        else:
            speak("Voice toggle is ready when running Hey Kali directly.")
        return True

    # Bluetooth File/Image/Video Sender ("send <file> to my phone", "send <file> to first/second/third bluetooth")
    m_bt_send = re.search(r"\bsend\b\s+(?:the\s+|file\s+|image\s+|photo\s+|picture\s+|video\s+)?(.+?)\s+\b(?:to\s+(?:the\s+|my\s+)?(?:(first|1st|one|1|second|2nd|two|2|third|3rd|three|3|fourth|4th|four|4|fifth|5th|five|5)\s+)?(?:blue\s*tooth(?:\s+device)?|phone|device)|(?:via|on)\s+blue\s*tooth)\b", q.replace("fast", "first"))
    if m_bt_send:
        target_part = m_bt_send.group(1).strip()
        bt_ord_word = (m_bt_send.group(2) or "").strip()
        chosen_file = ""
        search_dirs = [f"{HOME}/Desktop", f"{HOME}/Downloads", f"{HOME}/Pictures", f"{HOME}/Pictures/intruders", f"{HOME}/Videos", f"{HOME}/Documents", f"{HOME}/hey-kali", f"{HOME}/kali-linux-assistant", HOME]
        if any(w in target_part for w in ("recent", "latest", "last")):
            exts = (".jpg", ".jpeg", ".png", ".webp", ".gif") if any(w in target_part for w in ("picture", "photo", "image")) else ((".mp4", ".mkv", ".webm", ".mov") if any(w in target_part for w in ("video", "recording", "mp4")) else ())
            cands = [os.path.join(d, fn) for d in search_dirs if os.path.isdir(d) for fn in os.listdir(d) if os.path.isfile(os.path.join(d, fn)) and (not exts or fn.lower().endswith(exts))]
            if cands:
                chosen_file = max(cands, key=os.path.getmtime)
        elif target_part in ("this", "what i copied", "copied file", "my clipboard", "it") and shutil.which("xclip"):
            uri_raw = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "text/uri-list"], env=_rt_env, capture_output=True, text=True).stdout.strip()
            for line in uri_raw.splitlines():
                if line.strip().startswith("file://") and os.path.isfile(urllib.parse.unquote(line.strip()[7:])):
                    chosen_file = urllib.parse.unquote(line.strip()[7:])
                    break
        if not chosen_file and target_part:
            clean_q = target_part.replace(" dot ", ".").lower()
            matches = [os.path.join(d, fn) for d in search_dirs if os.path.isdir(d) for fn in os.listdir(d) if os.path.isfile(os.path.join(d, fn)) and clean_q in fn.lower()]
            if matches:
                chosen_file = max(matches, key=os.path.getmtime)
        if not chosen_file or not os.path.exists(chosen_file):
            speak(f"I could not find a file matching {target_part}.")
            return True
        if not shutil.which("blueman-sendto") and not shutil.which("gdbus") and not shutil.which("bluetooth-sendto") and not shutil.which("bt-obex"):
            speak("Bluetooth file transfer tools are not installed.")
            return True
        subprocess.run(["rfkill", "unblock", "bluetooth"], env=_rt_env, capture_output=True)
        subprocess.run(["bluetoothctl", "power", "on"], env=_rt_env, capture_output=True)
        send_idx = {"first": 0, "1st": 0, "one": 0, "1": 0, "second": 1, "2nd": 1, "two": 1, "2": 1, "third": 2, "3rd": 2, "three": 2, "3": 2, "fourth": 3, "4th": 3, "four": 3, "4": 3, "fifth": 4, "5th": 4, "five": 4, "5": 4}.get(bt_ord_word, None)
        devs = subprocess.run(["bluetoothctl", "devices"], env=_rt_env, capture_output=True, text=True).stdout
        p_devs = [(pts[1].strip(), pts[2].strip() if len(pts) >= 3 else pts[1].strip()) for line in devs.splitlines() for pts in [line.split(" ", 2)] if len(pts) >= 2 and pts[0] == "Device"]
        if not p_devs:
            speak("Could not find any paired Bluetooth device.")
            return True
        if send_idx is not None:
            if 0 <= send_idx < len(p_devs):
                bt_mac, bt_dev_name = p_devs[send_idx]
            else:
                speak(f"Bluetooth device number {send_idx + 1} was not found.")
                return True
        else:
            bt_mac, bt_dev_name = next(((m, n) for m, n in p_devs if "gamer" in n.lower()), p_devs[0])
        speak(f"Sending {os.path.basename(chosen_file)} to {bt_dev_name} via Bluetooth now.")
        def _push_bt(f_path, mac_addr):
            env_bt = dict(_rt_env)
            env_bt.setdefault("DISPLAY", os.environ.get("DISPLAY", ":0"))
            env_bt["XAUTHORITY"] = f"{HOME}/.Xauthority"
            env_bt["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
            abs_f = os.path.abspath(os.path.expanduser(f_path))
            if shutil.which("blueman-sendto"):
                subprocess.Popen(["blueman-sendto", f"--device={mac_addr}", abs_f], env=env_bt)
            elif shutil.which("bluetooth-sendto"):
                subprocess.Popen(["bluetooth-sendto", f"--device={mac_addr}", abs_f], env=env_bt)
            elif shutil.which("bt-obex"):
                subprocess.run(["bt-obex", "-p", mac_addr, abs_f], env=env_bt)
            else:
                _obex_dbus_send(mac_addr, abs_f, env_bt)
        threading.Thread(target=_push_bt, args=(chosen_file, bt_mac), daemon=False).start()
        return True

    _cli_prefixes = (
        "what is the command for ", "what's the command for ",
        "what is the command to ", "what's the command to ",
        "what command ", "which command ",
        "give me the command to ", "show me the command to ",
        "how do i ", "command for ", "command to "
    )
    if any(q.startswith(p) for p in _cli_prefixes):
        task = ""
        for p in _cli_prefixes:
            if q.startswith(p):
                task = str(query)[len(p):].strip(" ?.").replace(" sue", " su").replace(" zoo", " su").replace(" sea", " su")
                break
        if not task:
            speak("Please tell me what command or task you need.")
            return True

        blocked_terms = ("reverse shell", "reverse tcp", "payload", "exploit", "malware", "ransomware", "trojan", "keylogger", "backdoor", "meterpreter")
        if any(b in task.lower() for b in blocked_terms):
            speak("I cannot generate payloads or exploit commands, only standard Linux and diagnostic commands.")
            return True

        stop_words = {"open", "use", "run", "execute", "start", "launch", "check", "switch", "user", "root", "the", "a", "an", "to", "in", "on", "for", "with", "linux", "kali"}
        tokens = [t.strip(".,?!") for t in task.lower().split() if t.strip(".,?!") not in stop_words]
        found_bin = ""
        for tok in tokens:
            if shutil.which(tok) or os.path.exists(f"/usr/bin/{tok}") or os.path.exists(f"/bin/{tok}") or os.path.exists(f"/usr/sbin/{tok}"):
                found_bin = tok
                break

        cmd_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_command.txt"

        if found_bin:
            man_env = os.environ.copy()
            man_env["MANWIDTH"] = "85"
            man_raw = subprocess.run(
                f"man {found_bin} 2>/dev/null | col -b | head -n 45",
                shell=True, env=man_env, capture_output=True, text=True
            ).stdout.strip()
            if not man_raw:
                man_raw = subprocess.run(
                    f"{found_bin} --help 2>&1 | head -n 35",
                    shell=True, capture_output=True, text=True
                ).stdout.strip()

            report = f"=== COMMAND & SYNTAX: {found_bin.upper()} ===\n\n{man_raw or f'Usage: {found_bin} [OPTIONS]'}\n"
            open(cmd_file, "w").write(report)
            speak(f"Displaying the command and syntax for {found_bin} on your screen.")
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", f"--title=Command Manual: {found_bin}", f"--filename={cmd_file}", "--width=780", "--height=500"])
            return True

        search_kw = tokens.pop(0) if tokens else task.split().pop(-1)
        apropos_out = subprocess.run(
            f"apropos {shlex.quote(search_kw)} 2>/dev/null | head -n 20",
            shell=True, capture_output=True, text=True
        ).stdout.strip()

        if apropos_out:
            report = f"=== MATCHING LINUX COMMANDS FOR: {task.upper()} ===\n\n{apropos_out}\n"
            open(cmd_file, "w").write(report)
            speak(f"Displaying matching commands for {task} on your screen.")
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", f"--title=Commands: {task}", f"--filename={cmd_file}", "--width=780", "--height=460"])
            return True

        ans_text = ""
        try:
            url = f"http://{chr(49)}27.0.0.1:{11000 + 434}/api/generate"
            payload = json.dumps({
                "model": "gemma3:1b",
                "system": "You are a Bash syntax cheat-sheet. Reply ONLY with the standard command syntax and 1 short line explaining its flags.",
                "prompt": f"Show standard Linux Bash syntax for: {task}",
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 80, "num_ctx": 512, "temperature": 0.1}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                ans_text = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
        except Exception:
            pass

        open(cmd_file, "w").write(f"=== COMMAND FOR: {task.upper()} ===\n\n{ans_text or 'No manual entry found.'}\n")
        speak(f"Displaying the command for {task} on your screen.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", f"--title=Command Reference: {task}", f"--filename={cmd_file}", "--width=760", "--height=420"])
        return True

    q = str(query).lower().strip()

    # 1. Stop Talking
    if q in ("stop", "stop talking", "be quiet", "shut up", "quiet", "cancel"):
        subprocess.run(["pkill", "-9", "espeak-ng"], stderr=subprocess.DEVNULL)
        return True

    # 2. Volume Controls
    if any(w in q for w in ("volume", "mute", "unmute", "louder", "quieter")):
        if "unmute" in q:
            ok = set_audio("unmute", gui_env=gui_env)
            speak("Unmuted." if ok else "No audio mixer tool found.")
        elif "mute" in q:
            ok = set_audio("mute", gui_env=gui_env)
            speak("Muted." if ok else "No audio mixer tool found.")
        elif any(w in q for w in ("up", "increase", "raise", "louder", "higher")):
            ok = set_audio("up", gui_env=gui_env)
            speak("Volume increased." if ok else "No audio mixer tool found.")
        elif any(w in q for w in ("down", "decrease", "lower", "quieter", "reduce")):
            ok = set_audio("down", gui_env=gui_env)
            speak("Volume decreased." if ok else "No audio mixer tool found.")
        else:
            m = re.search(r"\d+", q)
            if m:
                pct = min(100, max(0, int(m.group(0))))
                ok = set_audio("set", pct=pct, gui_env=gui_env)
                speak(f"Volume set to {pct} percent." if ok else "No audio mixer tool found.")
            else:
                speak("Say volume up, volume down, mute, or set volume to 50 percent.")
        return True

    # 3. Brightness Controls
    if "brightness" in q:
        up = any(w in q for w in ("up", "increase", "raise", "higher", "brighter"))
        if shutil.which("brightnessctl"):
            subprocess.run(["brightnessctl", "set", "+15%" if up else "15%-"])
            speak("Brightness increased." if up else "Brightness decreased.")
            return True
        out = subprocess.run(["xrandr", "--query"], env=gui_env, capture_output=True, text=True).stdout
        for line in out.splitlines():
            if " connected" in line:
                display_name, _, _ = line.partition(" ")
                subprocess.run(["xrandr", "--output", display_name, "--brightness", "1.0" if up else "0.6"], env=gui_env)
                speak("Brightness adjusted.")
                return True
        speak("Could not adjust brightness.")
        return True

    # 4. Screenshot
    if any(w in q for w in ("screenshot", "screen shot", "capture screen", "take a shot")):
        speak(take_screenshot(gui_env))
        return True

    # 5. Time, Date & Battery
    if "time" in q and any(w in q for w in ("what", "current", "tell")):
        speak(time.strftime("It is %I:%M %p."))
        return True
    if "date" in q and any(w in q for w in ("what", "today", "current")):
        speak(time.strftime("Today is %A, %B %d, %Y."))
        return True
    if "battery" in q:
        for bat in ("/sys/class/power_supply/BAT0/capacity", "/sys/class/power_supply/BAT1/capacity"):
            if os.path.exists(bat):
                cap = open(bat).read().strip()
                speak(f"Battery is at {cap} percent.")
                return True
        speak("No battery detected.")
        return True

    # 6. VPN & Public IP
    if "vpn" in q:
        res = subprocess.run(["ip", "addr", "show", "tun0"], capture_output=True, text=True)
        speak("VPN is connected on tun0." if res.returncode == 0 else "VPN is not connected.")
        return True
    if "public ip" in q:
        ip = subprocess.run(["curl", "-s", "--max-time", "4", "https://api.ipify.org"], capture_output=True, text=True).stdout.strip()
        speak(f"Your public IP is {ip}" if ip else "Could not reach public IP service.")
        return True

    # 7. Google & YouTube Voice Search
    if q.startswith(("search youtube for ", "youtube ")):
        _, _, term = q.partition("for ") if "for " in q else q.partition(" ")
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(term.strip())
        speak(f"Searching YouTube for {term.strip()}")
        launch_gui(["firefox", url])
        return True
    if q.startswith(("search google for ", "search for ", "google ")):
        _, _, term = q.partition("for ") if "for " in q else q.partition(" ")
        url = "https://www.google.com/search?q=" + urllib.parse.quote(term.strip())
        speak(f"Searching Google for {term.strip()}")
        launch_gui(["firefox", url])
        return True

    # 9. Kali Undercover Mode Toggle (XFCE)
    if any(w in q for w in ("undercover", "under cover", "windows mode", "disguise mode")):
        if shutil.which("kali-undercover"):
            speak("Toggling Kali undercover mode.")
            launch_gui(["kali-undercover"])
        else:
            speak("Kali undercover is not installed. Run sudo apt install kali-undercover.")
        return True

    # 10. Instant Hashing & Encoding ("hash hello", "encrypt password123")
    if any(q.startswith(p) for p in ("hash ", "encrypt ", "encode ", "make a hash of ", "generate hash for ")):
        word = ""
        for p in ("make a hash of ", "generate hash for ", "hash ", "encrypt ", "encode "):
            if q.startswith(p):
                word = str(query)[len(p):].strip(" .!?")
                break
        if not word:
            speak("Please tell me the word or text to encrypt or hash.")
            return True

        raw = word.encode("utf-8")
        out_text = (
            f"Input Text: {word}\n"
            f"{'=' * 50}\n"
            f"MD5:    {hashlib.md5(raw).hexdigest()}\n"
            f"SHA1:   {hashlib.sha1(raw).hexdigest()}\n"
            f"SHA256: {hashlib.sha256(raw).hexdigest()}\n"
            f"SHA512: {hashlib.sha512(raw).hexdigest()}\n"
            f"Base64: {base64.b64encode(raw).decode('utf-8')}\n"
        )
        hash_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        open(hash_file, "w").write(out_text)
        speak(f"Generated hashes for {word}. Displaying on screen.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", "--title=Generated Hashes & Encoding", f"--filename={hash_file}", "--width=780", "--height=420"])
        return True

    # 11. Smart Multi-Language Code & Specific Command Routing
    languages = (
        "python", "bash", "shell", "c++", "cpp", "c#", "csharp", "java",
        "javascript", "js", "typescript", "php", "go", "golang", "rust",
        "ruby", "perl", "powershell", "sql", "html", "css", "assembly", "lua"
    )
    is_cmd_req = any(q.startswith(p) for p in ("command ", "terminal command ", "linux command ", "shell command ", "give me a command "))
    is_file_op = any(w in q for w in ("create a file", "create file", "create a folder", "create folder", "create a directory"))
    is_code_req = (not is_file_op) and any(w in q for w in ("code", "script", "program", "function", "write a ", "generate ", "create a "))

    if is_cmd_req:
        _, _, task = str(query).partition("command ")
        task = task.strip() or str(query)
        cmd_out = subprocess.run(["/usr/bin/sgpt", "--shell", "--no-interaction", task], capture_output=True, text=True).stdout.strip()
        if cmd_out:
            cmd_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_command.txt"
            open(cmd_file, "w").write(cmd_out + "\n")
            speak(f"Command ready: {cmd_out}")
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", "--title=Drafted Command", f"--filename={cmd_file}", "--width=750", "--height=350"])
        else:
            speak("Could not generate that command.")
        return True

    if is_code_req:
        chosen_lang = "best matching"
        for lang in languages:
            if re.search(rf"\b{re.escape(lang)}\b", q):
                chosen_lang = lang.upper()
                break

        speak(f"Generating {chosen_lang if chosen_lang != 'best matching' else ''} code, please wait.")
        strict_prompt = (
            f"Write ONLY clean, working {chosen_lang} code for this request (do not default to Python unless requested): {query}"
            if chosen_lang != "best matching"
            else f"Write ONLY clean, working code in the most appropriate language for this request: {query}"
        )
        gen_code = subprocess.run(["/usr/bin/sgpt", "--code", strict_prompt], capture_output=True, text=True).stdout.strip()
        if gen_code:
            code_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
            open(code_file, "w").write(gen_code + "\n")
            speak("Code generated and displayed.")
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", f"--title=Generated {chosen_lang.title()} Code", f"--filename={code_file}", "--width=780", "--height=520"])
        else:
            speak("Could not generate code for that request.")
        return True

    # 12. Public OSINT Recon Helper ("gather information about <target>", "osint <target>")
    if any(q.startswith(p) for p in ("gather information about ", "gather info about ", "osint ", "investigate ", "lookup ")):
        target = str(query)
        for p in ("gather information about ", "gather info about ", "osint ", "investigate ", "lookup "):
            if q.startswith(p):
                target = str(query)[len(p):].strip()
                break

        if not target:
            speak("Please tell me the username or domain to look up.")
            return True

        clean_target = target.replace(" dot ", ".").replace(" ", "").lower()
        report_file = f"{os.path.dirname(os.path.abspath(__file__))}/osint_report.txt"

        # Find a terminal to display public OSINT output transparently
        term = None
        for t in ("qterminal", "xfce4-terminal", "gnome-terminal", "mate-terminal", "x-terminal-emulator"):
            if shutil.which(t):
                term = t
                break

        if "." in clean_target:
            # Public domain OSINT (WHOIS + DNS + theHarvester if installed)
            speak(f"Running public domain OSINT for {clean_target} in terminal.")
            harvester_cmd = f"theHarvester -d {clean_target} -b all -l 50" if shutil.which("theHarvester") else "echo 'Tip: sudo apt install theharvester for deeper domain recon'"
            shell_cmd = (
                f"echo '=== Public OSINT Report: {clean_target} ===' | tee {report_file}; "
                f"whois {clean_target} | head -n 35 | tee -a {report_file}; "
                f"echo '--- DNS Records ---' | tee -a {report_file}; "
                f"dig +short ANY {clean_target} | tee -a {report_file}; "
                f"{harvester_cmd} | tee -a {report_file}; "
                f"echo 'Saved to {report_file}'; exec bash"
            )
        else:
            # Public username OSINT (Sherlock if installed, or opens public search tabs)
            if shutil.which("sherlock"):
                speak(f"Checking public username profiles for {clean_target} with Sherlock.")
                shell_cmd = (
                    f"echo '=== Public Username OSINT: {clean_target} ===' | tee {report_file}; "
                    f"sherlock {clean_target} --timeout 5 | tee -a {report_file}; "
                    f"exec bash"
                )
            else:
                speak(f"Opening public search pages for {target}. Install sherlock for terminal username checks.")
                launch_gui(["firefox", f"https://www.google.com/search?q={urllib.parse.quote(target)}"])
                return True

        if term:
            launch_gui([term, "-e", f"bash -c \"{shell_cmd}\""])
        return True

    # 12. Passive OSINT Lookup (Username, Domain WHOIS, or Public Harvester)
    if any(q.startswith(p) for p in ("osint ", "check username ", "lookup ", "whois ", "investigate ")):
        target = ""
        for p in ("check username ", "osint ", "lookup ", "whois ", "investigate "):
            if q.startswith(p):
                target = str(query)[len(p):].strip()
                break
        if not target:
            speak("Please tell me a username or domain to check.")
            return True

        clean_target = target.replace(" dot ", ".").replace(" ", "")
        out_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"

        # Case A: Domain lookup (contains a dot, e.g., example.com)
        if "." in clean_target and "@" not in clean_target:
            speak(f"Running public WHOIS and harvester lookup for {clean_target}.")
            whois_res = subprocess.run(["whois", clean_target], capture_output=True, text=True, timeout=15).stdout
            report = f"=== PUBLIC WHOIS REPORT: {clean_target} ===\n\n{whois_res[:4000]}"
            open(out_file, "w").write(report)
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", f"--title=OSINT Report: {clean_target}", f"--filename={out_file}", "--width=780", "--height=520"])
            return True

        # Case B: Username lookup across public sites (uses sherlock if installed)
        if shutil.which("sherlock"):
            speak(f"Checking public profiles for username {clean_target}. Please wait.")
            res = subprocess.run(["sherlock", clean_target, "--timeout", "5", "--print-found"], capture_output=True, text=True, timeout=45).stdout
            report = f"=== PUBLIC USERNAME OSINT: {clean_target} ===\n\n{res if res.strip() else 'No public profiles found.'}"
            open(out_file, "w").write(report)
            speak("OSINT search complete. Displaying results.")
            if shutil.which("zenity"):
                launch_gui(["zenity", "--text-info", f"--title=Username OSINT: {clean_target}", f"--filename={out_file}", "--width=780", "--height=520"])
        else:
            speak("Sherlock is not installed. Run sudo apt install sherlock to enable username lookups.")
        return True

    # 13. Universal Passive Information Gathering ("gather information on <target>")
    gather_prefixes = (
        "gather information on ", "gather information about ",
        "gather info on ", "gather info about ",
        "find information on ", "find information about ",
        "research ", "tell me everything about "
    )
    if any(q.startswith(p) for p in gather_prefixes):
        target = ""
        for p in gather_prefixes:
            if q.startswith(p):
                target = str(query)[len(p):].strip()
                break
        if not target:
            speak("Please tell me what person, site, IP, or place to gather information on.")
            return True

        clean = target.replace(" dot ", ".").strip()
        out_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
        report_lines = [f"=== PASSIVE INFORMATION REPORT: {clean} ===", "=" * 55, ""]

        # Case 1: IPv4 Address (e.g., 8.8.8.8)
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", clean):
            speak(f"Gathering public IP intelligence for {clean}.")
            try:
                with urllib.request.urlopen(f"http://ip-api.com/json/{clean}", timeout=6) as r:
                    data = json.loads(r.read().decode("utf-8"))
                report_lines.append("[IP Geolocation & ISP]")
                for k in ("query", "country", "regionName", "city", "isp", "org", "as", "timezone"):
                    if k in data:
                        report_lines.append(f"  {k.upper()}: {data[k]}")
            except Exception as e:
                report_lines.append(f"IP lookup note: {e}")

            if shutil.which("whois"):
                w_out = subprocess.run(["whois", clean], capture_output=True, text=True, timeout=10).stdout
                report_lines.append("\n[Public WHOIS Record]\n" + w_out[:2500])

        # Case 2: Website / Domain (e.g., example.com)
        elif "." in clean and " " not in clean and "@" not in clean:
            speak(f"Gathering passive domain and DNS information for {clean}.")
            if shutil.which("dig"):
                dns_out = subprocess.run(["dig", "+short", "ANY", clean], capture_output=True, text=True, timeout=8).stdout.strip()
                report_lines.append("[Public DNS Records]\n" + (dns_out or "No records returned."))
            if shutil.which("curl"):
                hdr_out = subprocess.run(["curl", "-sI", "--max-time", "6", f"https://{clean}"], capture_output=True, text=True).stdout.strip()
                report_lines.append("\n[HTTP Response Headers]\n" + (hdr_out or "No HTTPS headers."))
            if shutil.which("whois"):
                w_out = subprocess.run(["whois", clean], capture_output=True, text=True, timeout=10).stdout
                report_lines.append("\n[Public WHOIS Summary]\n" + w_out[:2500])

        # Case 3: Single-word Username Handle (e.g., johndoe)
        elif " " not in clean and len(clean) >= 3 and shutil.which("sherlock"):
            speak(f"Checking public profiles for {clean}. Please wait.")
            s_out = subprocess.run(["sherlock", clean, "--timeout", "5", "--print-found"], capture_output=True, text=True, timeout=40).stdout
            report_lines.append("[Public Social Profiles]\n" + (s_out.strip() or "No matching public profiles found."))

        # Case 4: Place, Location, Public Figure, or General Topic
        else:
            speak(f"Gathering background information on {clean}.")
            try:
                wiki_slug = urllib.parse.quote(clean.replace(" ", "_"))
                req = urllib.request.Request(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_slug}",
                    headers={"User-Agent": "KaliVoiceAssistant/1.0"}
                )
                with urllib.request.urlopen(req, timeout=6) as r:
                    wdata = json.loads(r.read().decode("utf-8"))
                if "extract" in wdata:
                    report_lines.append("[Encyclopedia Overview]\n" + wdata["extract"] + "\n")
            except Exception:
                pass

            # Add local AI structured briefing
            try:
                ai_req = urllib.request.Request(
                    f"http://127.0.0.1:11434/api/generate",
                    data=json.dumps({
                        "model": "gemma3:1b",
                        "prompt": f"Provide a clear, structured factual overview of: {clean}",
                        "stream": False,
                        "options": {"num_predict": 220}
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(ai_req, timeout=12) as resp:
                    brief = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
                    report_lines.append("[AI Intelligence Brief]\n" + brief)
            except Exception:
                pass

        open(out_file, "w").write("\n".join(report_lines) + "\n")
        speak(f"Information report for {clean} is ready on your screen.")
        if shutil.which("zenity"):
            launch_gui(["zenity", "--text-info", f"--title=Intelligence Report: {clean}", f"--filename={out_file}", "--width=800", "--height=540"])
        return True

    # 14. Shazam-Style Music Identification ("identify music", "what song is this")
    if any(w in q for w in ("identify music", "identify song", "what song", "what music", "recognize music", "name this song")):
        speak("Listening to the music for 6 seconds.")
        wav_path = "/tmp/kali_music.wav"

        # Record 6 seconds from raw hardware mic (or default source) so laptop music isn't canceled out
        rec_cmd = ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", "6", wav_path]
        if shutil.which("parecord"):
            # Try raw hardware input first so music playing on the laptop itself is also captured
            sources = subprocess.run(["pactl", "list", "short", "sources"], env=gui_env, capture_output=True, text=True).stdout
            raw_mic = ""
            for line in sources.splitlines():
                parts = line.split()
                if len(parts) >= 2 and "alsa_input" in parts.pop(1):
                    raw_mic = line.split().pop(1)
                    break
            rec_cmd = ["parecord", "--file-format=wav", "--rate=16000", "--channels=1"]
            if raw_mic:
                rec_cmd += ["-d", raw_mic]
            rec_cmd.append(wav_path)
            p = subprocess.Popen(rec_cmd, env=gui_env)
            try:
                p.wait(timeout=6.5)
            except subprocess.TimeoutExpired:
                p.terminate()
        else:
            subprocess.run(rec_cmd)

        speak("Analyzing track...")
        try:
            from shazamio import Shazam
            async def _recognize():
                shazam = Shazam()
                return await shazam.recognize(wav_path)

            res = asyncio.run(_recognize())
            track = res.get("track") if isinstance(res, dict) else None
            if track:
                title = track.get("title", "Unknown Title")
                artist = track.get("subtitle", "Unknown Artist")
                speak(f"That song is {title} by {artist}.")
                out_file = f"{os.path.dirname(os.path.abspath(__file__))}/last_code.txt"
                open(out_file, "w").write(f"Song: {title}\nArtist: {artist}\n")
            else:
                speak("Sorry, I could not recognize that song. Try moving closer to the music.")
        except Exception as e:
            print(f"Music ID error: {e}", flush=True)
            speak("Music identification failed. Check your internet connection.")
        return True

    # 15. Restore Trashed File ("restore notes", "restore last file")
    if q.startswith(("restore ", "undelete ", "recover ")) and " " in str(query):
        _, _, target = str(query).partition(" ")
        target = target.strip().lower()
        trash_files = f"{HOME}/.local/share/Trash/files"
        trash_info = f"{HOME}/.local/share/Trash/info"
        if not os.path.exists(trash_files):
            speak("Your trash is empty.")
            return True

        matches = []
        for fname in sorted(os.listdir(trash_files), reverse=True):
            if target in ("last", "last file", "it", "file") or target in fname.lower():
                matches.append(fname)

        if not matches:
            speak(f"Could not find {target} in trash.")
            return True

        chosen = matches[0]
        src_path = os.path.join(trash_files, chosen)
        info_path = os.path.join(trash_info, f"{chosen}.trashinfo")
        orig_path = None

        if os.path.exists(info_path):
            for line in open(info_path):
                if line.startswith("Path="):
                    orig_path = urllib.parse.unquote(line.split("=", 1)[1].strip())
                    break

        if not orig_path:
            # Fallback for older trashed files without .trashinfo: restore to Desktop
            clean_name = re.sub(r"^\d+_", "", chosen)
            orig_path = os.path.join(f"{HOME}/Desktop", clean_name)

        os.makedirs(os.path.dirname(orig_path), exist_ok=True)
        shutil.move(src_path, orig_path)
        if os.path.exists(info_path):
            os.remove(info_path)
        speak(f"Restored {os.path.basename(orig_path)} to {os.path.basename(os.path.dirname(orig_path))}.")
        return True

    # 16. Fast Single-Call Online Lookup (1.2s max timeout — never stalls 6 seconds!)
    if any(q.startswith(p) for p in ("who is ", "who was ", "what is ", "what are ", "define ", "meaning of ")):
        if not any(w in q for w in ("my ip", "public ip", "time", "date", "battery", "command for", "command to")):
            topic = re.sub(r"^(who is|who was|what is|what are|define|meaning of|the|a|an)\s+", "", q).strip(" ?.")
            if topic:
                try:
                    slug = urllib.parse.quote(topic.title().replace(" ", "_"))
                    req = urllib.request.Request(
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
                        headers={"User-Agent": "KaliVoiceAssistant/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=1.2) as r:
                        data = json.loads(r.read().decode("utf-8"))
                    extract = data.get("extract", "").strip()
                    if extract and "may refer to:" not in extract:
                        short_ans = ". ".join(extract.split(". ")[:2]).strip()
                        if not short_ans.endswith("."):
                            short_ans += "."
                        speak(short_ans)
                        return True
                except Exception:
                    pass

    # 17. Refresh / Reload Desktop & Taskbar
    if any(p in q for p in ("refresh desktop", "reload desktop", "refresh taskbar", "reload taskbar", "restart panel", "refresh screen")):
        speak("Refreshing desktop and taskbar.")
        launch_gui(["xfce4-panel", "-r"])
        launch_gui(["xfdesktop", "--reload"])
        return True

    # 18. Open Specific Folders & Files (Without Confusing App Launches)
    if q.startswith(("open folder ", "open directory ", "open file ", "open document ", "open ")) and " " in str(query):
        _, _, raw_target = str(query).partition(" ")
        raw_target = raw_target.strip()
        low_target = raw_target.lower()

        explicit_item = False
        for prefix in ("folder ", "directory ", "file ", "document "):
            if low_target.startswith(prefix):
                raw_target = raw_target[len(prefix):].strip()
                low_target = raw_target.lower()
                explicit_item = True
                break

        # Known app names that must ALWAYS go to hey_kali.py's app launcher
        reserved_apps = {
            "terminal", "firefox", "chrome", "browser", "files", "file manager",
            "wireshark", "burp", "burp suite", "metasploit", "msfconsole", "nmap",
            "medusa", "hydra", "sqlmap", "vs code", "code", "text editor",
            "settings", "john", "aircrack", "zenmap", "ghidra", "zaproxy", "zap",
            "code", "command"
        }

        # Direct shortcut folders (Desktop, Downloads, Documents, Pictures, Music, Videos, Home)
        std_folders = {
            "desktop": f"{HOME}/Desktop",
            "downloads": f"{HOME}/Downloads",
            "download": f"{HOME}/Downloads",
            "documents": f"{HOME}/Documents",
            "document": f"{HOME}/Documents",
            "pictures": f"{HOME}/Pictures",
            "music": f"{HOME}/Music",
            "videos": f"{HOME}/Videos",
            "home": HOME,
            "trash": f"{HOME}/.local/share/Trash/files"
        }

        if low_target in std_folders and os.path.exists(std_folders[low_target]):
            launch_gui(["xdg-open", std_folders[low_target]])
            speak(f"Opening {low_target} folder.")
            return True

        # Search user directories if explicitly asked ("open folder X" / "open file Y") OR if not a reserved app
        if explicit_item or (low_target and low_target not in reserved_apps and not shutil.which(low_target)):
            found_path = None
            for base_dir in (f"{HOME}/Desktop", f"{HOME}/Downloads", f"{HOME}/Documents", HOME):
                if not os.path.exists(base_dir):
                    continue
                for entry in os.listdir(base_dir):
                    if entry.startswith("."):
                        continue
                    ent_low = entry.lower()
                    no_ext, _ = os.path.splitext(ent_low)
                    if low_target in (ent_low, no_ext, ent_low.replace("_", " "), no_ext.replace("_", " ")):
                        found_path = os.path.join(base_dir, entry)
                        break
                if found_path:
                    break

            if found_path:
                kind = "folder" if os.path.isdir(found_path) else "file"
                launch_gui(["xdg-open", found_path])
                speak(f"Opening {kind} {os.path.basename(found_path)}.")
                return True
            elif explicit_item:
                speak(f"I could not find a file or folder named {raw_target}.")
                return True

    # 19. Play Music Online (Bypasses YouTube Consent Wall + Opens via xdg-open)
    play_prefixes = ("play music ", "play song ", "play track ", "play ")
    if any(q.startswith(p) for p in play_prefixes) and " " in str(query):
        song = ""
        for p in play_prefixes:
            if q.startswith(p):
                song = str(query)[len(p):].strip()
                break
        if not song:
            speak("Please tell me the name of the song to play.")
            return True

        search_q = urllib.parse.urlencode({"search_query": song})
        target_url = urllib.parse.urlunparse(("https", "www.youtube.com", "/results", "", search_q, ""))

        # Bypass YouTube EU/region consent wall so the exact top video ID is always extracted
        try:
            res = _HTTP.get(
                target_url,
                cookies={"CONSENT": "YES+cb.20210328-17-p0.en+FX+417"},
                timeout=2.5
            )
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', res.text)
            if vids:
                first_id = next(iter(vids))
                watch_q = urllib.parse.urlencode({"v": first_id, "autoplay": "1"})
                target_url = urllib.parse.urlunparse(("https", "www.youtube.com", "/watch", "", watch_q, ""))
        except Exception:
            pass

        print(f"[Music URL] {target_url}", flush=True)
        # Use xdg-open so XFCE opens Firefox cleanly with the exact URL (no black window)
        launch_gui(["xdg-open", target_url])
        speak(f"Playing {song}.")
        return True

    return False
