"""Constantes de l'intégration Caméra XiongMai."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "xiongmai_camera"
DEFAULT_PORT = 34567
DEFAULT_USERNAME = "admin"
SCAN_INTERVAL = timedelta(seconds=60)
# remise à zéro du mouvement si la caméra n'envoie pas la fin de l'événement
MOTION_TIMEOUT = 60

# sections du firmware lues à chaque mise à jour
SECTIONS = ("Detect.MotionDetect", "Camera.Param", "NetWork.Nat")

DAY_NIGHT = {0: "auto", 1: "color", 2: "black_white"}
