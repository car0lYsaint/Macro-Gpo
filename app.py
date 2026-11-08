"""GPO Halloween Macro — interface. Rode com:  python app.py"""
import ctypes
import queue
import threading
import time
import tkinter as tk

try:  # coordenadas reais de pixel no Windows (evita erro com escala de 125%/150%)
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
from pynput import keyboard as pk

import bot as B

GREEN, RED, GRAY = "#3ddc97", "#f0606d", "#3a3a3a"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("GPO Halloween")
        self.geometry("400x640")
        self.attributes("-topmost", True)
        self.cfg = B.load_cfg()
        self.bot = None
        self.recorder = B.Recorder()
        self.recording = None
        self.cmds = queue.Queue()
        self.msg = "Pronto"

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self._farm_tab(tabs.add("Farm"))
        self._setup_tab(tabs.add("Setup"))

        pk.GlobalHotKeys({"<f3>": lambda: self.cmds.put("toggle"),
                          "<f4>": lambda: self.cmds.put("record")}).start()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(150, self._tick)

    # ---------- abas ----------
    def _row(self, parent, label, widget_factory):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=3)
        ctk.CTkLabel(f, text=label, anchor="w").pack(side="left")
        w = widget_factory(f)
        w.pack(side="right")
        return w

    def _entry(self, parent, key):
        e = ctk.CTkEntry(parent, width=70, justify="center")
        e.insert(0, str(self.cfg[key]))
        return e

    def _farm_tab(self, tab):
        self.lbl_candies = ctk.CTkLabel(tab, text="— / — candies", anchor="e")
        self.lbl_candies.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(tab, text="Item da loja: Rare Fruit Chest — 250 candies",
                     anchor="w").pack(fill="x", pady=3)
        self.e_buy = self._row(tab, "Comprar quando doces ≥",
                               lambda p: self._entry(p, "buy_when_candies"))
        self.e_max = self._row(tab, "Máx. baús por visita",
                               lambda p: self._entry(p, "max_chests_per_visit"))
        self.m_slot = self._row(tab, "Basket slot", lambda p: ctk.CTkOptionMenu(
            p, values=[str(i) for i in range(1, 10)], width=70))
        self.m_slot.set(str(self.cfg["basket_slot"]))
        self.btn_start = ctk.CTkButton(tab, text="Start · F3", height=42, fg_color=GREEN,
                                       text_color="black", hover_color="#2fb67c",
                                       command=lambda: self.cmds.put("toggle"))
        self.btn_start.pack(fill="x", pady=(14, 6))
        ctk.CTkButton(tab, text="Test buying (compra 1 baú)", fg_color=GRAY,
                      command=self._test_buy).pack(fill="x", pady=3)
        self.lbl_stats = ctk.CTkLabel(tab, text="00:00:00 · 0 doors · 0 compras", anchor="w")
        self.lbl_stats.pack(fill="x", pady=(12, 0))
        self.lbl_state = ctk.CTkLabel(tab, text="Pronto", anchor="w", wraplength=340,
                                      justify="left")
        self.lbl_state.pack(fill="x", pady=4)

    def _setup_tab(self, tab):
        ctk.CTkLabel(tab, text="1) Templates (capturados da SUA tela)", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x")
        self.tpl_status = {}
        for name, desc in B.TEMPLATES.items():
            f = ctk.CTkFrame(tab, fg_color="transparent")
            f.pack(fill="x", pady=2)
            st = ctk.CTkLabel(f, text="", width=18)
            st.pack(side="left")
            ctk.CTkLabel(f, text=desc, anchor="w", wraplength=210,
                         justify="left").pack(side="left")
            ctk.CTkButton(f, text="Capturar", width=70, fg_color=GRAY,
                          command=lambda n=name: self._capture(n)).pack(side="right")
            self.tpl_status[name] = st

        ctk.CTkLabel(tab, text="2) Rotas (F4 inicia/para a gravação no jogo)", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x", pady=(14, 0))
        self.m_route = ctk.CTkOptionMenu(tab, values=list(B.ROUTES), command=lambda _: self._refresh())
        self.m_route.pack(fill="x", pady=3)
        self.lbl_route = ctk.CTkLabel(tab, text="", anchor="w", wraplength=340, justify="left")
        self.lbl_route.pack(fill="x")

        ctk.CTkLabel(tab, text="3) Ajustes", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x", pady=(14, 0))
        self.e_door = self._row(tab, "Espera após E (s)", lambda p: self._entry(p, "door_wait"))
        self.e_cool = self._row(tab, "Intervalo entre portas (s)",
                                lambda p: self._entry(p, "knock_cooldown"))
        self._refresh()

    def _refresh(self):
        for n, lbl in self.tpl_status.items():
            ok = (B.TPL_DIR / f"{n}.png").exists()
            lbl.configure(text="✓" if ok else "✗", text_color=GREEN if ok else RED)
        r = B.load_route(self.m_route.get())
        desc = B.ROUTES[self.m_route.get()]
        info = f"{len(r['events'])} eventos, {r['duration']:.1f}s" if r else "ainda não gravada"
        self.lbl_route.configure(text=f"{desc}\nStatus: {info}")

    # ---------- ações ----------
    def _read_settings(self):
        try:
            self.cfg["buy_when_candies"] = int(self.e_buy.get())
            self.cfg["max_chests_per_visit"] = int(self.e_max.get())
            self.cfg["basket_slot"] = int(self.m_slot.get())
            self.cfg["door_wait"] = float(self.e_door.get())
            self.cfg["knock_cooldown"] = float(self.e_cool.get())
        except ValueError:
            self.msg = "Valor inválido num dos campos"
            return False
        B.save_cfg(self.cfg)
        return True

    def _running(self):
        return self.bot is not None and self.bot.t_start is not None

    def _toggle(self):
        if self._running():
            self.bot.stop()
            return
        if self.recording or not self._read_settings():
            return
        self.bot = B.Bot(self.cfg)
        threading.Thread(target=self.bot.run, daemon=True).start()

    def _test_buy(self):
        if self._running() or self.recording or not self._read_settings():
            return
        self.bot = B.Bot(self.cfg)
        self.bot.set_state("Teste em 4s: deixe o jogo à frente, perto da bruxa")
        threading.Thread(target=self.bot.test_buy, daemon=True).start()

    def _toggle_record(self):
        if self._running():
            return
        if self.recording:
            n, dur = self.recorder.stop(self.recording)
            self.msg = f"Rota '{self.recording}' salva ({n} eventos, {dur:.1f}s)"
            self.recording = None
            self._refresh()
        else:
            self.recording = self.m_route.get()
            self.recorder.start()
            self.msg = f"GRAVANDO '{self.recording}' — ande no jogo e aperte F4 para parar"

    # ---------- captura de template ----------
    def _capture(self, name):
        self.msg = f"Capturando '{name}' em 5s: deixe o jogo mostrando isso"
        self.lbl_state.configure(text=self.msg)
        self.update()
        self.withdraw()
        self.after(5000, lambda: self._select_region(name))

    def _select_region(self, name):
        frame, _ = B.Grabber(self.cfg["monitor"]).grab()
        self.deiconify()
        top = tk.Toplevel(self)
        top.attributes("-fullscreen", True, "-topmost", True)
        h, w = frame.shape[:2]
        img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        cv = tk.Canvas(top, width=w, height=h, highlightthickness=0, cursor="cross")
        cv.pack()
        cv.create_image(0, 0, image=img, anchor="nw")
        cv.image = img
        st = {"x": 0, "y": 0, "r": None}

        def down(e):
            st["x"], st["y"] = e.x, e.y
            st["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="#00ff88", width=2)

        def move(e):
            cv.coords(st["r"], st["x"], st["y"], e.x, e.y)

        def up(e):
            x0, x1 = sorted((st["x"], e.x))
            y0, y1 = sorted((st["y"], e.y))
            top.destroy()
            if x1 - x0 > 5 and y1 - y0 > 5:
                cv2.imwrite(str(B.TPL_DIR / f"{name}.png"), frame[y0:y1, x0:x1])
                self.msg = f"Template '{name}' salvo"
            self._refresh()

        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        top.bind("<Escape>", lambda e: top.destroy())

    # ---------- laço de atualização ----------
    def _tick(self):
        try:
            while True:
                cmd = self.cmds.get_nowait()
                self._toggle() if cmd == "toggle" else self._toggle_record()
        except queue.Empty:
            pass
        b, running = self.bot, self._running()
        if b:
            if running:
                el = int(time.perf_counter() - b.t_start)
                self.lbl_stats.configure(
                    text=f"{el // 3600:02d}:{el % 3600 // 60:02d}:{el % 60:02d} · "
                         f"{b.doors} doors · {b.purchases} compras")
            if b.candies:
                self.lbl_candies.configure(text=f"{b.candies[0]}/{b.candies[1]} candies")
            self.lbl_state.configure(text=b.state if (running or b.state != "Parado") else self.msg)
        else:
            self.lbl_state.configure(text=self.msg)
        if self.recording:
            self.lbl_state.configure(text=self.msg)
        self.btn_start.configure(text="Stop · F3" if running else "Start · F3",
                                 fg_color=RED if running else GREEN)
        self.after(200, self._tick)

    def _close(self):
        if self.bot:
            self.bot.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
