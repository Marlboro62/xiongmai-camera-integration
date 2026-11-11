"""Caméra XiongMai simulée (protocole DVRIP) pour les tests et la démo.

    python3 fake_camera.py [port]     # identifiants : admin / (mot de passe vide) ou admin / demo

Les valeurs reprennent la forme renvoyée par les firmwares V4.02 (NetSurveillance WEB) ; elles sont fictives.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from datetime import datetime

from custom_components.xiongmai_camera.dvrip import (ALARM_REQ, GUARD_REQ, CONFIG_GET, CONFIG_SET, DEFAULT_CONFIG_GET, HEADER, KEEPALIVE_REQ, LOGIN_REQ, SYSINFO_REQ,
                   SYSMANAGER_REQ, TIMEQUERY_REQ, ABILITY_GET, NET_SNAP_REQ, sofia_hash)
from pathlib import Path

PASSWORDS = {sofia_hash(""), sofia_hash("demo")}

CONFIG = {
    "General.General": {"AutoLogout": 0, "FontSize": 24, "IranCalendarEnable": 0, "LocalNo": 0, "MachineName": "Caméra-Exemple",
                        "OverWrite": "OverWrite", "ScreenAutoShutdown": 10, "ScreenSaveTime": 0, "VideoOutPut": "Auto"},
    "General.Location": {"DSTEnd": {"Day": 0, "Hour": 3, "Minute": 0, "Month": 10, "Week": 5, "Year": 2027},
                         "DSTRule": "On", "DSTStart": {"Day": 0, "Hour": 2, "Minute": 0, "Month": 3, "Week": 5, "Year": 2027},
                         "DateFormat": "DDMMYY", "DateSeparator": "/", "IranCalendar": 0, "Language": "English", "TimeFormat": "24",
                         "VideoFormat": "PAL", "WorkDay": 62},
    "Camera.Param": [{"AeSensitivity": 5, "ApertureMode": "0x00000001", "BLCMode": "0x00000000", "DayNightColor": "0x00000000",
                      "Day_nfLevel": 3, "DncThr": 30, "ElecLevel": 50, "EsShutter": "0x00000000",
                      "ExposureParam": {"LeastTime": "0x00000100", "Level": 0, "MostTime": "0x00010000"},
                      "GainParam": {"AutoGain": 1, "Gain": 50}, "IRCUTMode": 0, "IrcutSwap": 0, "Night_nfLevel": 3,
                      "PictureFlip": "0x00000000", "PictureMirror": "0x00000000", "RejectFlicker": "0x00000000", "WhiteBalance": "0x00000000"}] * 16,
    "Camera.ParamEx": [{"AeMeansure": 0, "BroadTrends": {"AutoGain": 0, "Gain": 50}, "CorridorMode": 0, "Dis": 0,
                        "ExposureTime": "0x100", "LightRestrainLevel": 16, "LowLuxMode": 0, "PreventOverExpo": 0,
                        "SoftPhotosensitivecontrol": 0, "Style": "typedefault", "Ldc": 0}],
    "AVEnc.VideoColor": [[{"Enable": True, "TimeSection": "1 00:00:00-24:00:00",
                           "VideoColorParam": {"Acutance": 15, "Brightness": 50, "Contrast": 50, "Gain": 0, "Hue": 50, "Saturation": 50, "Whitebalance": 128}},
                          {"Enable": False, "TimeSection": "0 00:00:00-24:00:00",
                           "VideoColorParam": {"Acutance": 15, "Brightness": 50, "Contrast": 50, "Gain": 0, "Hue": 50, "Saturation": 50, "Whitebalance": 128}}]] * 16,
    "Simplify.Encode": [{"ExtraFormat": {"AudioEnable": False, "Video": {"BitRate": 512, "BitRateControl": "VBR", "Compression": "H.264", "FPS": 15, "GOP": 2, "Quality": 4, "Resolution": "D1"}, "VideoEnable": True},
                         "MainFormat": {"AudioEnable": False, "Video": {"BitRate": 2048, "BitRateControl": "VBR", "Compression": "H.264", "FPS": 25, "GOP": 2, "Quality": 4, "Resolution": "1080P"}, "VideoEnable": True}}],
    "AVEnc.VideoWidget": [{"ChannelTitle": {"Name": "Entrée", "SerialNo": ""}, "ChannelTitleAttribute": {"BackColor": "0x00000000", "EncodeBlend": True, "FrontColor": "0xF0FFFFFF", "PreviewBlend": True, "RelativePos": [7521, 0, 255, 24]},
                           "Covers": [{"BackColor": "0x00000000", "EncodeBlend": True, "FrontColor": "0x00000000", "PreviewBlend": True, "RelativePos": [0, 0, 0, 0]}] * 4, "CoversNum": 0,
                           "TimeTitleAttribute": {"BackColor": "0x00000000", "EncodeBlend": True, "FrontColor": "0xF0FFFFFF", "PreviewBlend": True, "RelativePos": [6144, 6144, 0, 0]}}],
    "Detect.MotionDetect": [{"Enable": True, "Level": 3, "Region": ["0x003FFFFF"] * 18 + ["0x00000000"] * 14,
                             "EventHandler": {"AlarmOutEnable": False, "AlarmOutLatch": 10, "BeepEnable": False, "EventLatch": 1, "FTPEnable": False,
                                              "MailEnable": False, "MessageEnable": True, "RecordEnable": True, "RecordLatch": 30, "ShowInfo": False,
                                              "SnapEnable": False, "TimeSection": [["1 00:00:00-24:00:00"] + ["0 00:00:00-24:00:00"] * 5] * 7,
                                              "RecordMask": "0x" + "0" * 31 + "1", "SnapShotMask": "0x" + "0" * 32, "AlarmOutMask": "0x" + "0" * 32,
                                              "PtzEnable": False, "PtzLink": [["None", 0]] * 16}}],
    "Detect.BlindDetect": [{"Enable": False, "Level": 3, "EventHandler": {"MessageEnable": False, "RecordEnable": False}}],
    "Detect.LossDetect": [{"Enable": False, "EventHandler": {"MessageEnable": False}}],
    "Alarm.AlarmIn": [{"Enable": False, "SensorType": "NO", "EventHandler": {"MessageEnable": False}}, {"Enable": False, "SensorType": "NO", "EventHandler": {"MessageEnable": False}}],
    "Alarm.AlarmOut": [{"AlarmOutStatus": "CLOSE", "AlarmOutType": "AUTO"}],
    "NetWork.NetCommon": {"GateWay": "0x0101A8C0", "HostIP": "0x6401A8C0", "HostName": "camera", "HttpPort": 80, "MAC": "00:12:34:56:78:9a",
                          "MaxBps": 0, "MonMode": "TCP", "SSLPort": 8443, "Submask": "0x00FFFFFF", "TCPMaxConn": 10, "TCPPort": 34567,
                          "TransferPlan": "Quality", "UDPPort": 34568, "UseHSDownLoad": False},
    "NetWork.NetDHCP": [{"Enable": False, "Interface": "eth0"}],
    "NetWork.NetDNS": {"Address": "0x0101A8C0", "SpareAddress": "0x08080808"},
    "NetWork.NetNTP": {"Enable": True, "Server": {"Address": "0x00000000", "Anonymity": False, "Name": "fr.pool.ntp.org", "Password": "", "Port": 123, "UserName": ""},
                       "TimeZone": 13, "UpdatePeriod": 60},
    "NetWork.RTSP": {"Client": {"Address": "0x00000000", "Anonymity": False, "Name": "", "Password": "", "Port": 554, "UserName": ""},
                     "IsClient": False, "IsServer": True, "Server": {"Address": "0x00000000", "Anonymity": False, "Name": "", "Password": "", "Port": 554, "UserName": ""}},
    "NetWork.Nat": {"Addr": "xmsecu.com", "DnsServer1": "0x08080808", "DnsServer2": "0x00000000", "MTU": 1280, "NatEnable": True, "Port": 8765, "XMeyeMTU": 0},
}
DEFAULTS = copy.deepcopy(CONFIG)
SYSINFO = {"AlarmInChannel": 2, "AlarmOutChannel": 1, "BuildTime": "2017-07-20 09:03:15", "DeviceRunTime": "0x0000A1B2",
           "DigChannel": 0, "EncryptVersion": "Unknown", "ExtraChannel": 0, "HardWare": "IPC_EXEMPLE", "HardWareVersion": "Unknown",
           "SerialNo": "0000000000000000", "SoftWareVersion": "V4.02.R11.00000000.10012.000000.00000", "TalkInChannel": 1,
           "TalkOutChannel": 1, "UpdataTime": "", "UpdataType": "0x00000000", "VideoInChannel": 1, "VideoOutChannel": 1}


LANGS = ["English", "SimpChinese", "French", "German"]
SNAPSHOT = Path(__file__).parent / "demo-snapshot.jpg"  # image fictive
SUBSCRIBERS: list = []  # connexions abonnées aux alarmes (GUARD)


def reset() -> None:
    """Remet la caméra simulée dans son état d'usine (entre deux tests)."""
    CONFIG.clear()
    CONFIG.update(copy.deepcopy(DEFAULTS))
    SUBSCRIBERS.clear()


async def push_alarm(active: bool, event: str = "VideoMotion") -> None:
    """Envoie une alarme à toutes les connexions abonnées."""
    body = json.dumps({"AlarmInfo": {"Channel": 0, "Event": event, "StartTime": "2026-11-11 08:00:00",
                                     "Status": "Start" if active else "Stop"}, "Name": "AlarmInfo", "SessionID": "0x0000002A"}).encode() + b"\x0a\x00"
    for w in list(SUBSCRIBERS):
        try:
            w.write(HEADER.pack(0xFF, 1, 0x2A, 0, ALARM_REQ, len(body)) + body)
            await w.drain()
        except (ConnectionError, RuntimeError):
            SUBSCRIBERS.remove(w)


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    session = 0
    state = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "logged": False}
    try:
        while True:
            head = await reader.readexactly(HEADER.size)
            _m, _v, _sess, seq, msg, length = HEADER.unpack(head)
            body = await reader.readexactly(length)
            data = json.loads(body.rstrip(b"\x00").rstrip(b"\x0a").decode("utf-8") or "{}")
            name = data.get("Name")
            if msg == LOGIN_REQ:
                if data.get("UserName") == "admin" and data.get("PassWord") in PASSWORDS:
                    session = 0x2A
                    state["logged"] = True
                    resp = {"AliveInterval": 21, "ChannelNum": 1, "DeviceType ": "IPC", "ExtraChannel": 0, "Ret": 100, "SessionID": f"0x{session:08X}"}
                else:
                    resp = {"Ret": 106, "SessionID": "0x00000000"}
            elif not state["logged"]:
                resp = {"Ret": 105, "SessionID": "0x00000000"}
            elif msg in (CONFIG_GET, DEFAULT_CONFIG_GET):
                src = CONFIG if msg == CONFIG_GET else DEFAULTS
                resp = {"Name": name, name: src[name], "Ret": 100} if name in src else {"Name": name, "Ret": 607}
            elif msg == CONFIG_SET:
                if name not in CONFIG:
                    resp = {"Name": name, "Ret": 607}
                else:
                    new = data.get(name)
                    if name == "General.Location" and new.get("Language") not in LANGS:  # comme une vraie caméra : ignoré sans erreur
                        new["Language"] = CONFIG[name]["Language"]
                    CONFIG[name] = new
                    resp = {"Name": name, "Ret": 603 if name.startswith("NetWork.") else 100}
            elif msg == SYSINFO_REQ:
                resp = {"Name": "SystemInfo", "SystemInfo": SYSINFO, "Ret": 100}
            elif msg == ABILITY_GET and name == "MultiLanguage":
                resp = {"Name": name, name: LANGS + ["Hungarian"], "Ret": 100}
            elif msg == ABILITY_GET and name == "MotionArea":
                resp = {"Name": name, name: {"GridColumn": 22, "GridRow": 18}, "Ret": 100}
            elif msg == ABILITY_GET:
                resp = {"Name": name, name: {"EncodeFunction": {"DoubleStream": True}}, "Ret": 100}
            elif msg == NET_SNAP_REQ:
                jpeg = SNAPSHOT.read_bytes()
                writer.write(HEADER.pack(0xFF, 1, session, seq, msg + 1, len(jpeg)) + jpeg)
                await writer.drain()
                continue
            elif msg == TIMEQUERY_REQ:
                resp = {"Name": "OPTimeQuery", "OPTimeQuery": state["time"], "Ret": 100}
            elif msg == SYSMANAGER_REQ and name == "OPTimeSetting":
                state["time"] = data.get("OPTimeSetting")
                resp = {"Name": name, "Ret": 100}
            elif msg == SYSMANAGER_REQ and name == "OPMachine":
                resp = {"Name": name, "Ret": 100}
            elif msg == GUARD_REQ:
                SUBSCRIBERS.append(writer)
                resp = {"Name": "", "Ret": 100}
            elif msg == KEEPALIVE_REQ:
                resp = {"Name": "", "Ret": 100}
            else:
                resp = {"Name": name, "Ret": 103}
            resp.setdefault("SessionID", f"0x{session:08X}")
            out = json.dumps(resp, ensure_ascii=False).encode("utf-8") + b"\x0a\x00"
            writer.write(HEADER.pack(0xFF, 1, session, seq, msg + 1, len(out)) + out)
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionError):
        pass
    finally:
        if writer in SUBSCRIBERS:
            SUBSCRIBERS.remove(writer)
        writer.close()


async def main(port: int = 34567) -> None:
    server = await asyncio.start_server(handle, "127.0.0.1", port)
    print(f"Caméra simulée sur 127.0.0.1:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 34567))
