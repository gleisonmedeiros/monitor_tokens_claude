import tkinter as tk
import json
import time
import threading
from pathlib import Path
from datetime import datetime

TOKENS_FILE  = Path.home() / ".claude_monitor" / "tokens.json"
CREDS_FILE   = Path.home() / ".claude" / ".credentials.json"
UPDATE_MS    = 1000
POLL_COTA_S  = 120  # consulta a cota real a cada 2min


# ── Leitura do tokens.json local ───────────────────────────────────────────────

def load_data():
    try:
        with open(TOKENS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Consulta cota real via API ─────────────────────────────────────────────────

_cota = {
    "pct_5h":    None,   # 0.0 a 1.0
    "reset_5h":  None,   # timestamp unix
    "pct_7d":    None,
    "status":    "...",
    "erro":      None,
    "ultima":    0,
}
_cota_lock = threading.Lock()


def _obter_token_oauth():
    try:
        with open(CREDS_FILE, encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def _consultar_cota():
    import urllib.request
    token = _obter_token_oauth()
    if not token:
        with _cota_lock:
            _cota["erro"] = "sem token"
        return

    body = b'{"model":"claude-haiku-4-5","max_tokens":1,"messages":[{"role":"user","content":"x"}]}'
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type":    "application/json",
            "Authorization":   f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "anthropic-beta":  "oauth-2025-04-20",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            h = dict(resp.headers)
    except urllib.error.HTTPError as e:
        h = dict(e.headers)
    except Exception as ex:
        with _cota_lock:
            _cota["erro"] = str(ex)
        return

    def hf(key, default=None):
        for k, v in h.items():
            if k.lower() == key.lower():
                return v
        return default

    try:
        pct_5h   = float(hf("anthropic-ratelimit-unified-5h-utilization",  "0"))
        pct_7d   = float(hf("anthropic-ratelimit-unified-7d-utilization",  "0"))
        reset_5h = int(hf("anthropic-ratelimit-unified-5h-reset", "0"))
        status   = hf("anthropic-ratelimit-unified-status", "?")
        with _cota_lock:
            _cota["pct_5h"]   = pct_5h
            _cota["pct_7d"]   = pct_7d
            _cota["reset_5h"] = reset_5h
            _cota["status"]   = status
            _cota["erro"]     = None
            _cota["ultima"]   = time.time()
    except Exception as ex:
        with _cota_lock:
            _cota["erro"] = str(ex)


def _loop_cota():
    while True:
        _consultar_cota()
        time.sleep(POLL_COTA_S)


# ── Overlay ────────────────────────────────────────────────────────────────────

class TokenOverlay:
    def __init__(self):
        t = threading.Thread(target=_loop_cota, daemon=True)
        t.start()

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.90)
        self.root.configure(bg="#111111")
        self.root.resizable(False, False)

        self.drag_x = self.drag_y = 0

        f = tk.Frame(self.root, bg="#1a1a1a", padx=10, pady=6)
        f.pack()

        # ── Botão fechar ──
        header = tk.Frame(f, bg="#1a1a1a")
        header.pack(fill="x")
        tk.Button(header, text="✕", font=("Consolas", 8), fg="#666666",
                  bg="#1a1a1a", activebackground="#ff4444", activeforeground="#ffffff",
                  bd=0, cursor="hand2", command=self.root.destroy).pack(side="right")

        # ── Cota da conta (uso total: browser + IDE + CLI + scripts) ──
        tk.Label(f, text="COTA DA CONTA  (5h)", font=("Consolas", 7, "bold"),
                 fg="#666666", bg="#1a1a1a").pack(anchor="w")

        self.bar_frame = tk.Frame(f, bg="#333333", height=8, width=160)
        self.bar_frame.pack(fill="x", pady=(2, 0))
        self.bar_fill = tk.Frame(self.bar_frame, bg="#00ff88", height=8, width=0)
        self.bar_fill.place(x=0, y=0)

        self.lbl_pct   = tk.Label(f, text="consultando...",
                                  font=("Consolas", 9, "bold"),
                                  fg="#00ff88", bg="#1a1a1a")
        self.lbl_pct.pack(anchor="w")

        self.lbl_reset = tk.Label(f, text="",
                                  font=("Consolas", 8),
                                  fg="#555555", bg="#1a1a1a")
        self.lbl_reset.pack(anchor="w")

        # ── Separador ──
        tk.Frame(f, bg="#333333", height=1).pack(fill="x", pady=6)

        # ── Scripts Python ──
        tk.Label(f, text="SEUS SCRIPTS", font=("Consolas", 7, "bold"),
                 fg="#666666", bg="#1a1a1a").pack(anchor="w")

        self.lbl_scripts = tk.Label(f, text="0 tokens  •  0 req",
                                    font=("Consolas", 9),
                                    fg="#888888", bg="#1a1a1a")
        self.lbl_scripts.pack(anchor="w")

        # Posição: canto superior direito
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{sw - 200}+10")

        for w in f.winfo_children():
            w.bind("<ButtonPress-1>", self.start_drag)
            w.bind("<B1-Motion>",     self.do_drag)
            w.bind("<Button-3>",      self.menu_direito)
        for w in [self.root, f, self.bar_frame]:
            w.bind("<ButtonPress-1>", self.start_drag)
            w.bind("<B1-Motion>",     self.do_drag)
            w.bind("<Button-3>",      self.menu_direito)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Atualizar agora",   command=lambda: threading.Thread(target=_consultar_cota, daemon=True).start())
        self.menu.add_command(label="Zerar scripts",     command=self.zerar_scripts)
        self.menu.add_separator()
        self.menu.add_command(label="Fechar",            command=self.root.destroy)

        self.atualizar()
        self.root.mainloop()

    # ── Drag ──────────────────────────────────────────────────────────────────

    def start_drag(self, event):
        self.drag_x = event.x_root - self.root.winfo_x()
        self.drag_y = event.y_root - self.root.winfo_y()

    def do_drag(self, event):
        self.root.geometry(f"+{event.x_root - self.drag_x}+{event.y_root - self.drag_y}")

    def menu_direito(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def zerar_scripts(self):
        d = load_data()
        d.update({"tokens": 0, "input_tokens": 0, "output_tokens": 0,
                  "cache_read": 0, "cache_created": 0, "requests": 0})
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)

    # ── Loop de atualização ────────────────────────────────────────────────────

    def atualizar(self):
        self._atualizar_cota()
        self._atualizar_scripts()
        self.root.after(UPDATE_MS, self.atualizar)

    def _atualizar_cota(self):
        with _cota_lock:
            pct      = _cota["pct_5h"]
            reset_ts = _cota["reset_5h"]
            status   = _cota["status"]
            erro     = _cota["erro"]

        if erro:
            self.lbl_pct.config(text=f"erro: {erro[:20]}", fg="#ff4444")
            self.lbl_reset.config(text="")
            return

        if pct is None:
            self.lbl_pct.config(text="consultando...", fg="#888888")
            return

        usado    = round(pct * 100)
        restante = 100 - usado

        # Cor por urgência
        if restante <= 10:
            cor = "#ff4444"
        elif restante <= 30:
            cor = "#ffaa00"
        else:
            cor = "#00ff88"

        self.lbl_pct.config(text=f"{restante}% restante  ({usado}% usado)", fg=cor)

        # Barra de progresso (largura 160px)
        bar_w = max(1, int(160 * pct))
        self.bar_fill.config(bg=cor, width=bar_w)

        # Contagem regressiva
        if reset_ts:
            secs = int(reset_ts - time.time())
            if secs > 0:
                h, m = divmod(secs // 60, 60)
                self.lbl_reset.config(text=f"reseta em {h}h{m:02d}min")
            else:
                self.lbl_reset.config(text="resetando...")

    def _atualizar_scripts(self):
        d = load_data()
        tokens = d.get("tokens", 0)
        reqs   = d.get("requests", 0)
        inp    = d.get("input_tokens", 0)
        out    = d.get("output_tokens", 0)
        if reqs > 0:
            self.lbl_scripts.config(
                text=f"{tokens:,} tokens  •  {reqs} req\n↑{inp:,} entrada  ↓{out:,} saída".replace(",", ".")
            )
        else:
            self.lbl_scripts.config(text="nenhum script rodou ainda")


if __name__ == "__main__":
    TokenOverlay()
