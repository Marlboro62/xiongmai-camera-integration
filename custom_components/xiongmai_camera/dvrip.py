"""Client du protocole DVRIP (« Sofia ») des caméras XiongMai / XMEye, port TCP 34567.

C'est le protocole qu'utilisent l'ActiveX d'Internet Explorer (NetSurveillance WEB) et le logiciel CMS.
Chaque message : un en-tête de 20 octets, puis du JSON terminé par « \\n\\0 ».

    octet 0      0xFF
    octet 1      version (0)
    octets 2-3   réservés
    octets 4-7   identifiant de session (little-endian)
    octets 8-11  numéro de séquence
    octets 12-13 réservés (paquet total / courant)
    octets 14-15 code du message
    octets 16-19 longueur des données
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
from typing import Any

_LOGGER = logging.getLogger(__name__)

HEADER = struct.Struct("<BB2xII2xHI")

# Codes des messages
LOGIN_REQ = 1000
LOGOUT_REQ = 1002
KEEPALIVE_REQ = 1006
SYSINFO_REQ = 1020
CONFIG_SET = 1040
CONFIG_GET = 1042
DEFAULT_CONFIG_GET = 1044
ABILITY_GET = 1360
SYSMANAGER_REQ = 1450  # OPMachine (redémarrage), OPTimeSetting (heure)
TIMEQUERY_REQ = 1452
NET_SNAP_REQ = 1560  # OPSNAP : une image JPEG de la caméra
GUARD_REQ = 1500  # abonnement aux alarmes (mouvement, entrées d'alarme…)
ALARM_REQ = 1504  # alarme envoyée par la caméra

# Codes de retour du firmware
RET_MESSAGES = {
    100: "OK",
    101: "Erreur inconnue",
    102: "Version non prise en charge",
    103: "Demande non autorisée par la caméra",
    104: "Utilisateur déjà connecté",
    105: "Utilisateur non connecté",
    106: "Nom d'utilisateur ou mot de passe incorrect",
    107: "Droits insuffisants",
    108: "Délai dépassé",
    109: "Recherche sans résultat",
    110: "Recherche réussie, tout est renvoyé",
    111: "Recherche réussie, une partie est renvoyée",
    112: "Utilisateur déjà existant",
    113: "Utilisateur inexistant",
    114: "Groupe déjà existant",
    115: "Groupe inexistant",
    117: "Format du message incorrect",
    118: "Protocole PTZ non configuré",
    119: "Pas de fichier trouvé",
    120: "Configuration activée",
    121: "Interface PTZ non configurée",
    150: "Réussi, la caméra doit redémarrer",
    203: "Mot de passe incorrect",
    204: "Utilisateur inexistant",
    205: "Utilisateur verrouillé (trop d'essais)",
    206: "Utilisateur sur liste noire",
    603: "Réussi, la caméra doit redémarrer pour appliquer le réglage",
}
OK_CODES = {100, 110, 111, 120, 150, 515, 603}


class DvripError(Exception):
    """Erreur de communication ou réponse refusée par la caméra."""

    def __init__(self, message: str, ret: int | None = None) -> None:
        super().__init__(message)
        self.ret = ret


def sofia_hash(password: str) -> str:
    """Empreinte du mot de passe attendue par le firmware (MD5 replié sur 8 caractères)."""
    digest = hashlib.md5(password.encode("utf-8")).digest()
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(chars[(digest[2 * i] + digest[2 * i + 1]) % 62] for i in range(8))


def ret_message(ret: int | None) -> str:
    return RET_MESSAGES.get(ret or 0, f"refusé par la caméra (code {ret})")


class DvripClient:
    """Une connexion à une caméra, partagée et protégée par un verrou (une requête à la fois)."""

    def __init__(self, host: str, port: int = 34567, username: str = "admin", password: str = "", timeout: float = 8.0) -> None:
        self.host, self.port, self.username, self.password, self.timeout = host, port, username, password, timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._session = 0
        self._seq = 0
        self._lock = asyncio.Lock()
        self.alive_interval = 20

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def _sid(self) -> str:
        return f"0x{self._session:08X}"

    async def _send(self, msg: int, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\x0a\x00"
        assert self._writer is not None
        self._writer.write(HEADER.pack(0xFF, 0, self._session, self._seq, msg, len(payload)) + payload)
        self._seq += 1
        await self._writer.drain()

    async def _recv_raw(self) -> tuple[int, bytes]:
        assert self._reader is not None
        head = await asyncio.wait_for(self._reader.readexactly(HEADER.size), self.timeout)
        magic, _version, session, _seq, msg, length = HEADER.unpack(head)
        if magic != 0xFF:
            raise DvripError("Réponse illisible (ce n'est pas une caméra XiongMai ?)")
        if length > 4 * 1024 * 1024:
            raise DvripError("Réponse trop volumineuse")
        body = await asyncio.wait_for(self._reader.readexactly(length), self.timeout) if length else b""
        if session:
            self._session = session
        return msg, body

    async def _recv_raw_nolimit(self) -> tuple[int, bytes]:
        assert self._reader is not None
        head = await self._reader.readexactly(HEADER.size)
        magic, _version, session, _seq, msg, length = HEADER.unpack(head)
        if magic != 0xFF or length > 4 * 1024 * 1024:
            raise DvripError("Réponse illisible")
        body = await self._reader.readexactly(length) if length else b""
        return msg, body

    async def _recv(self) -> tuple[int, dict[str, Any]]:
        msg, body = await self._recv_raw()
        text = body.rstrip(b"\x00").rstrip(b"\x0a").rstrip(b"\x00").decode("utf-8", errors="replace").strip()
        if not text:
            return msg, {}
        try:
            return msg, json.loads(text)
        except json.JSONDecodeError as err:
            raise DvripError(f"JSON illisible renvoyé par la caméra : {err}") from err

    async def _request(self, msg: int, data: dict[str, Any]) -> dict[str, Any]:
        await self._send(msg, data)
        _msg, resp = await self._recv()
        return resp

    async def connect(self) -> dict[str, Any]:
        """Connexion et identification ; renvoie la réponse du login."""
        await self.close()
        try:
            self._reader, self._writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), self.timeout)
        except (OSError, TimeoutError) as err:
            raise DvripError(f"Caméra injoignable sur {self.host}:{self.port} ({type(err).__name__})") from err
        self._session, self._seq = 0, 0
        resp = await self._request(LOGIN_REQ, {
            "EncryptType": "MD5", "LoginType": "DVRIP-Web", "PassWord": sofia_hash(self.password), "UserName": self.username,
        })
        ret = resp.get("Ret")
        if ret not in OK_CODES:
            await self.close()
            raise DvripError(f"Connexion refusée : {ret_message(ret)}", ret)
        sid = resp.get("SessionID")
        if isinstance(sid, str):
            try:
                self._session = int(sid, 16)
            except ValueError:
                pass
        self.alive_interval = int(resp.get("AliveInterval") or 20)
        return resp

    async def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), 2)
            except Exception:  # noqa: BLE001 - fermeture au mieux
                pass
        self._reader = self._writer = None

    async def call(self, msg: int, name: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Requête avec reconnexion automatique (une fois) si la session est perdue."""
        async with self._lock:
            for attempt in (1, 2):
                try:
                    if not self.connected:
                        await self.connect()
                    data = {"Name": name, "SessionID": self._sid(), **(extra or {})}
                    resp = await self._request(msg, data)
                    if resp.get("Ret") == 105 and attempt == 1:  # session perdue
                        await self.close()
                        continue
                    return resp
                except (OSError, asyncio.IncompleteReadError, TimeoutError, ConnectionError) as err:
                    await self.close()
                    if attempt == 2:
                        raise DvripError(f"Liaison perdue avec la caméra ({type(err).__name__})") from err
            raise DvripError("Session refusée par la caméra")

    @staticmethod
    def _check(resp: dict[str, Any], what: str) -> dict[str, Any]:
        ret = resp.get("Ret")
        if ret not in OK_CODES:
            raise DvripError(f"{what} : {ret_message(ret)}", ret)
        return resp

    async def get_config(self, name: str) -> Any:
        resp = self._check(await self.call(CONFIG_GET, name), f"Lecture de {name}")
        return resp.get(name)

    async def get_default(self, name: str) -> Any:
        resp = self._check(await self.call(DEFAULT_CONFIG_GET, name), f"Valeurs d'usine de {name}")
        return resp.get(name)

    async def set_config(self, name: str, value: Any) -> int:
        """Écrit une section ; renvoie le code (603 : redémarrage nécessaire)."""
        resp = self._check(await self.call(CONFIG_SET, name, {name: value}), f"Écriture de {name}")
        return int(resp.get("Ret") or 100)

    async def system_info(self) -> dict[str, Any]:
        resp = self._check(await self.call(SYSINFO_REQ, "SystemInfo"), "Informations système")
        return resp.get("SystemInfo") or {}

    async def ability(self, name: str = "SystemFunction") -> Any:
        resp = self._check(await self.call(ABILITY_GET, name), f"Capacités {name}")
        return resp.get(name)

    async def get_time(self) -> str | None:
        resp = self._check(await self.call(TIMEQUERY_REQ, "OPTimeQuery"), "Lecture de l'heure")
        return resp.get("OPTimeQuery")

    async def set_time(self, value: str) -> int:
        """Heure au format « AAAA-MM-JJ HH:MM:SS » (heure locale de la caméra)."""
        resp = self._check(await self.call(SYSMANAGER_REQ, "OPTimeSetting", {"OPTimeSetting": value}), "Réglage de l'heure")
        return int(resp.get("Ret") or 100)

    async def reboot(self) -> None:
        resp = await self.call(SYSMANAGER_REQ, "OPMachine", {"OPMachine": {"Action": "Reboot"}})
        await self.close()
        if resp and resp.get("Ret") not in OK_CODES:
            raise DvripError(f"Redémarrage : {ret_message(resp.get('Ret'))}", resp.get("Ret"))

    async def snapshot(self, channel: int = 0) -> bytes:
        """Image JPEG prise par la caméra (OPSNAP). Selon le firmware, une réponse JSON peut précéder l'image."""
        async with self._lock:
            for attempt in (1, 2):
                try:
                    if not self.connected:
                        await self.connect()
                    await self._send(NET_SNAP_REQ, {"Name": "OPSNAP", "OPSNAP": {"Channel": channel}, "SessionID": self._sid()})
                    for _ in range(3):
                        _msg, body = await self._recv_raw()
                        start = body.find(b"\xff\xd8")
                        if start >= 0:
                            return body[start:]
                        text = body.rstrip(b"\x00").rstrip(b"\x0a").rstrip(b"\x00").decode("utf-8", "replace").strip()
                        try:
                            ret = json.loads(text).get("Ret") if text else None
                        except (json.JSONDecodeError, AttributeError):
                            ret = None
                        if ret == 105 and attempt == 1:
                            break
                        if ret is not None and ret not in OK_CODES:
                            raise DvripError(f"Image : {ret_message(ret)}", ret)
                    else:
                        raise DvripError("La caméra n'a pas renvoyé d'image")
                    await self.close()  # session perdue : on recommence
                except (OSError, asyncio.IncompleteReadError, TimeoutError, ConnectionError) as err:
                    await self.close()
                    if attempt == 2:
                        raise DvripError(f"Liaison perdue avec la caméra ({type(err).__name__})") from err
            raise DvripError("La caméra n'a pas renvoyé d'image")

    async def keepalive(self) -> None:
        if self.connected:
            await self.call(KEEPALIVE_REQ, "KeepAlive")


class DvripEvents:
    """Connexion dédiée aux alarmes : la caméra pousse un message à chaque début et fin d'événement.

    on_alarm(event, channel, active) est appelé, par exemple ("VideoMotion", 0, True).
    """

    def __init__(self, host: str, port: int, username: str, password: str, on_alarm, timeout: float = 8.0) -> None:
        self.client = DvripClient(host, port, username, password, timeout)
        self.on_alarm = on_alarm

    async def run(self) -> None:
        """Boucle : connexion, abonnement, lecture ; reconnexion après une coupure (de 5 s à 5 min)."""
        delay = 5
        while True:
            try:
                await self._session()
                delay = 5
            except (DvripError, OSError, asyncio.IncompleteReadError, TimeoutError, ConnectionError) as err:
                _LOGGER.debug("Alarmes de %s : %s", self.client.host, err)
            finally:
                await self.client.close()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)

    async def _session(self) -> None:
        c = self.client
        await c.connect()
        await c._send(GUARD_REQ, {"Name": "", "SessionID": c._sid()})
        alive = max(5, c.alive_interval)
        loop = asyncio.get_running_loop()
        next_alive = loop.time() + alive
        while True:
            try:
                msg, body = await asyncio.wait_for(c._recv_raw_nolimit(), max(1.0, next_alive - loop.time()))
            except TimeoutError:
                await c._send(KEEPALIVE_REQ, {"Name": "KeepAlive", "SessionID": c._sid()})
                next_alive = loop.time() + alive
                continue
            if msg != ALARM_REQ:
                continue
            text = body.rstrip(b"\x00").rstrip(b"\x0a").rstrip(b"\x00").decode("utf-8", "replace").strip()
            try:
                info = json.loads(text).get("AlarmInfo") or {}
            except (json.JSONDecodeError, AttributeError):
                continue
            self.on_alarm(str(info.get("Event") or ""), int(info.get("Channel") or 0), str(info.get("Status") or "").lower() == "start")

    async def close(self) -> None:
        await self.client.close()
