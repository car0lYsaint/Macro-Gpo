"""Visão computacional: template matching e leitura do contador de doces."""
from pathlib import Path
import re

import cv2
import numpy as np

# Regiões relativas (x0, y0, x1, y1) da tela onde procurar cada coisa.
CANDY_REGION = (0.38, 0.78, 0.62, 0.84)   # "114/500 Candies", acima da hotbar
KNOCK_REGION = (0.30, 0.25, 0.70, 0.60)   # aviso "E / Knock" perto do personagem

_backend = None   # "tesseract" | "rapidocr" | "none"
_rapid = None


def crop_rel(frame, region):
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = region
    X0, Y0, X1, Y1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
    return frame[Y0:Y1, X0:X1], (X0, Y0)


def load_template(path):
    p = Path(path)
    return cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) if p.exists() else None


def find_template(frame, tpl, region=None, threshold=0.80):
    """Retorna (cx, cy, score) em coordenadas do frame inteiro, ou None."""
    if tpl is None:
        return None
    img, (ox, oy) = (frame, (0, 0)) if region is None else crop_rel(frame, region)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.shape[0] < tpl.shape[0] or gray.shape[1] < tpl.shape[1]:
        return None
    res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < threshold:
        return None
    th, tw = tpl.shape
    return ox + loc[0] + tw // 2, oy + loc[1] + th // 2, float(score)


def _pick_backend():
    global _backend, _rapid
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _backend = "tesseract"
        return
    except Exception:
        pass
    try:
        from rapidocr_onnxruntime import RapidOCR
        _rapid = RapidOCR()
        _backend = "rapidocr"
    except Exception:
        _backend = "none"


def _ocr(gray):
    if _backend is None:
        _pick_backend()
    if _backend == "tesseract":
        import pytesseract
        return pytesseract.image_to_string(
            gray, config="--psm 7 -c tessedit_char_whitelist=0123456789/Candies ")
    if _backend == "rapidocr":
        res, _ = _rapid(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
        return " ".join(r[1] for r in res) if res else ""
    return ""


def read_candies(frame):
    """Lê 'N/MAX Candies' do HUD. Retorna (atual, máximo) ou None."""
    crop, _ = crop_rel(frame, CANDY_REGION)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (5, 90, 150), (25, 255, 255))   # texto laranja
    mask = cv2.dilate(mask, np.ones((2, 2), np.uint8))
    gray = cv2.bitwise_not(cv2.resize(mask, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
    m = re.search(r"(\d{1,3})\s*/\s*(\d{2,4})", _ocr(gray))
    if not m:
        return None
    cur, cap = int(m.group(1)), int(m.group(2))
    return (cur, cap) if cur <= cap else None


def ocr_backend():
    if _backend is None:
        _pick_backend()
    return _backend
