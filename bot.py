"""Motor do macro: captura de tela, rota gravada, portas (Knock) e compra do Rare Fruit Chest."""
import json
import threading
import time
from pathlib import Path

import cv2
import mss
import numpy as np
import pydirectinput
from pynput import keyboard as pk
from pynput import mouse as pm

import vision

pydirectinput.PAUSE = 0
BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "config.json"
TPL_DIR = BASE / "templates"
ROUTE_DIR = BASE / "routes"
TPL_DIR.mkdir(exist_ok=True)
ROUTE_DIR.mkdir(exist_ok=True)

DEFAULTS = {
    "monitor": 1,                 # monitor onde o Roblox está (1 = principal)
    "basket_slot": 1,             # slot da cesta de doces
    "equip_basket": True,         # apertar o slot da cesta ao iniciar (NÃO deixe equipada antes)
    "chest_price": 250,
    "buy_when_candies": 250,      # confere no fim de cada volta; compra se doces >= isso
    "max_chests_per_visit": 2,
    "door_wait": 2.0,             # segundos esperando depois de apertar E
    "knock_cooldown": 3.0,        # não apertar E de novo antes disso
    "knock_threshold": 0.80,
    "template_threshold": 0.75,
    "scroll_tries": 20,
    "step_wait": 0.8,             # espera entre cliques da compra
}

TEMPLATES = {   # nome -> descrição mostrada na interface
    "knock": "Aviso da porta (ícone E / Knock)",
    "shop_title": "Título 'Halloween Shop' (loja aberta)",
    "rare_chest": "Card do Rare Fruit Chest (na loja)",
    "confirm": "Botão de confirmar compra (opcional)",
    "shop_close": "Botão de fechar a loja (opcional)",
}
ROUTES = {
    "farm": "Volta do farm (começa e termina no mesmo ponto)",
    "to_shop": "Do fim da volta até a bruxa (opcional)",
    "from_shop": "Da bruxa até o início da volta (opcional)",
}

REC_KEYS = {"w", "a", "s", "d"}
SPECIAL = {pk.Key.space: "space", pk.Key.shift: "shift",
           pk.Key.shift_l: "shift", pk.Key.shift_r: "shift"}


def load_cfg():
    cfg = dict(DEFAULTS)
    if CFG_PATH.exists():
        try:
            cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_cfg(cfg):
    CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def route_path(name):
    return ROUTE_DIR / f"{name}.json"


def load_route(name):
    p = route_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


class Grabber:
    """Captura de tela (uma instância do mss por thread)."""

    def __init__(self, monitor=1):
        self.monitor = monitor
        self.local = threading.local()

    def grab(self):
        sct = getattr(self.local, "sct", None)
        if sct is None:
            sct = self.local.sct = mss.mss()
        mon = sct.monitors[min(self.monitor, len(sct.monitors) - 1)]
        shot = np.asarray(sct.grab(mon))
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR), (mon["left"], mon["top"])


class Recorder:
    """Grava WASD/espaço/shift com tempo, para repetir depois."""

    def __init__(self):
        self.listener = None
        self.events, self.held, self.t0 = [], set(), 0.0

    @staticmethod
    def _name(k):
        if isinstance(k, pk.KeyCode) and k.char and k.char.lower() in REC_KEYS:
            return k.char.lower()
        return SPECIAL.get(k)

    def _on_press(self, k):
        n = self._name(k)
        if n and n not in self.held:
            self.held.add(n)
            self.events.append([round(time.perf_counter() - self.t0, 3), n, "down"])

    def _on_release(self, k):
        n = self._name(k)
        if n and n in self.held:
            self.held.discard(n)
            self.events.append([round(time.perf_counter() - self.t0, 3), n, "up"])

    def start(self):
        self.events, self.held = [], set()
        self.t0 = time.perf_counter()
        self.listener = pk.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()

    def stop(self, name):
        self.listener.stop()
        dur = round(time.perf_counter() - self.t0, 3)
        for n in list(self.held):
            self.events.append([dur, n, "up"])
        route_path(name).write_text(
            json.dumps({"events": self.events, "duration": dur}), encoding="utf-8")
        return len(self.events), dur


class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.stop_event = threading.Event()
        self.grabber = Grabber(cfg["monitor"])
        self.mouse = pm.Controller()
        self.tpl = {n: vision.load_template(TPL_DIR / f"{n}.png") for n in TEMPLATES}
        self.state = "Parado"
        self.doors = 0
        self.purchases = 0
        self.candies = None          # (atual, máximo)
        self.t_start = None
        self.last_knock = 0.0
        self.last_scan = 0.0

    # ---------- utilidades ----------
    def set_state(self, s):
        self.state = s

    def sleep(self, secs):
        """Dorme em fatias curtas para poder parar rápido."""
        end = time.perf_counter() + secs
        while time.perf_counter() < end and not self.stop_event.is_set():
            time.sleep(0.02)

    def grab(self):
        return self.grabber.grab()

    def find(self, name, region=None, thr=None):
        frame, (ox, oy) = self.grab()
        hit = vision.find_template(frame, self.tpl.get(name), region,
                                   thr or self.cfg["template_threshold"])
        return None if hit is None else (hit[0] + ox, hit[1] + oy)

    def wait_for(self, name, timeout):
        end = time.perf_counter() + timeout
        while time.perf_counter() < end and not self.stop_event.is_set():
            hit = self.find(name)
            if hit:
                return hit
            time.sleep(0.2)
        return None

    def read_candies(self):
        frame, _ = self.grab()
        c = vision.read_candies(frame)
        if c:
            self.candies = c
        return c

    def click(self, x, y):
        self.mouse.position = (x, y)
        self.sleep(0.15)
        self.mouse.press(pm.Button.left)
        self.sleep(0.05)
        self.mouse.release(pm.Button.left)

    # ---------- portas ----------
    def knock_visible(self):
        now = time.perf_counter()
        if now - self.last_scan < 0.12 or now - self.last_knock < self.cfg["knock_cooldown"]:
            return False
        self.last_scan = now
        frame, _ = self.grab()
        return vision.find_template(frame, self.tpl.get("knock"), vision.KNOCK_REGION,
                                    self.cfg["knock_threshold"]) is not None

    def handle_door(self):
        self.set_state("Abrindo porta")
        pydirectinput.press("e")
        self.last_knock = time.perf_counter()
        self.doors += 1
        self.sleep(self.cfg["door_wait"])
        self.read_candies()

    # ---------- rota ----------
    def play_route(self, name, check_doors=True):
        route = load_route(name)
        if not route:
            return False
        events, held, i = route["events"], set(), 0
        virtual, last = 0.0, time.perf_counter()
        try:
            while not self.stop_event.is_set():
                now = time.perf_counter()
                virtual += now - last
                last = now
                while i < len(events) and events[i][0] <= virtual:
                    _, key, kind = events[i]
                    if kind == "down":
                        pydirectinput.keyDown(key)
                        held.add(key)
                    else:
                        pydirectinput.keyUp(key)
                        held.discard(key)
                    i += 1
                if i >= len(events) and virtual >= route["duration"]:
                    break
                if check_doors and self.knock_visible():
                    for k in list(held):
                        pydirectinput.keyUp(k)
                    self.handle_door()
                    for k in held:
                        pydirectinput.keyDown(k)
                    self.set_state("Farmando")
                    last = time.perf_counter()   # tempo parado não conta na rota
                time.sleep(0.01)
        finally:
            for k in list(held):
                pydirectinput.keyUp(k)
        return True

    # ---------- loja ----------
    def buy(self, n):
        """Com o personagem ao lado da bruxa: abre a loja, compra n baús, fecha."""
        cfg = self.cfg
        self.set_state("Abrindo loja")
        pydirectinput.press("e")
        if not self.wait_for("shop_title", 6):
            self.set_state("Loja não detectada (capture 'shop_title')")
            return False
        frame, (ox, oy) = self.grab()
        h, w = frame.shape[:2]
        self.mouse.position = (ox + w // 2, oy + h // 2)   # mouse sobre a loja p/ rolar
        card = None
        for _ in range(cfg["scroll_tries"]):
            if self.stop_event.is_set():
                return False
            card = self.find("rare_chest")
            if card:
                break
            self.mouse.scroll(0, -3)
            self.sleep(0.3)
        if not card:
            self.set_state("Rare Fruit Chest não encontrado na loja")
            return False
        self.set_state(f"Comprando {n}x Rare Fruit Chest")
        for _ in range(n):
            self.click(*card)
            if self.tpl.get("confirm") is not None:
                ok = self.wait_for("confirm", 2.5)
                if ok:
                    self.click(*ok)
            self.sleep(cfg["step_wait"])
            self.purchases += 1
        close = self.find("shop_close") if self.tpl.get("shop_close") is not None else None
        if close:
            self.click(*close)
        self.sleep(0.5)
        return True

    def test_buy(self):
        """Botão 'Test buying': compra 1 baú com o personagem já perto da bruxa."""
        self.stop_event.clear()
        self.t_start = time.perf_counter()
        try:
            self.sleep(4)   # tempo para você trazer o jogo para frente
            ok = self.buy(1)
            self.set_state("Teste OK" if ok else self.state)
        finally:
            self.t_start = None

    # ---------- ciclo principal ----------
    def run(self):
        cfg = self.cfg
        self.stop_event.clear()
        self.t_start = time.perf_counter()
        try:
            if load_route("farm") is None:
                self.set_state("Grave a rota 'farm' primeiro (aba Setup)")
                return
            if self.tpl.get("knock") is None:
                self.set_state("Falta o template 'knock' (aba Setup)")
                return
            self.set_state("Começando em 3s (foque o jogo)")
            self.sleep(3)
            if cfg["equip_basket"]:
                pydirectinput.press(str(cfg["basket_slot"]))
                self.sleep(0.5)
            while not self.stop_event.is_set():
                self.set_state("Farmando")
                self.play_route("farm")
                c = self.read_candies()
                if self.stop_event.is_set():
                    break
                if c and c[0] >= cfg["buy_when_candies"]:
                    n = min(c[0] // cfg["chest_price"], cfg["max_chests_per_visit"])
                    if n > 0:
                        self.set_state("Indo à loja")
                        self.play_route("to_shop", check_doors=False)
                        self.buy(n)
                        self.play_route("from_shop", check_doors=False)
        finally:
            for k in ("w", "a", "s", "d", "shift", "space"):
                pydirectinput.keyUp(k)
            if not self.state.startswith(("Grave", "Falta", "Loja", "Rare")):
                self.set_state("Parado")
            self.t_start = None

    def stop(self):
        self.stop_event.set()
