import sys
import json
import time
import threading
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QPushButton, QMenu, QProgressBar,
)
from PyQt5.QtCore import Qt, QTimer, QPoint

TOKENS_FILE = Path.home() / ".claude_monitor" / "tokens.json"
CREDS_FILE  = Path.home() / ".claude" / ".credentials.json"
UPDATE_MS   = 1000
POLL_COTA_S = 120

_cota = {
    "pct_5h": None, "reset_5h": None, "pct_7d": None,
    "status": "...", "erro": None, "ultima": 0,
}
_cota_lock = threading.Lock()


def load_data():
    try:
        with open(TOKENS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _obter_token_oauth():
    try:
        with open(CREDS_FILE, encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def _consultar_cota():
    import urllib.request
    import urllib.error
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
            "Content-Type":      "application/json",
            "Authorization":     f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "oauth-2025-04-20",
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
        pct_5h   = float(hf("anthropic-ratelimit-unified-5h-utilization", "0"))
        pct_7d   = float(hf("anthropic-ratelimit-unified-7d-utilization", "0"))
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


_FONT_MONO = "Consolas"
_BG        = "#1a1a1a"

def _label(parent, text, size, bold=False, color="#888888"):
    lbl = QLabel(text, parent)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"color: {color}; font-family: {_FONT_MONO}; font-size: {size}pt; font-weight: {weight};"
    )
    return lbl

def _bar_style(cor):
    return (
        f"QProgressBar {{ background: #333333; border: none; border-radius: 2px; }}"
        f"QProgressBar::chunk {{ background: {cor}; border-radius: 2px; }}"
    )


class TokenOverlay(QWidget):
    def __init__(self):
        threading.Thread(target=_loop_cota, daemon=True).start()

        app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(0.90)
        self.setStyleSheet(f"background-color: {_BG};")

        self._drag_pos = QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(2)

        # Header
        header = QHBoxLayout()
        header.addStretch()
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(16, 16)
        btn_close.setStyleSheet(
            "QPushButton { color: #666666; background: transparent; border: none; font-size: 10px; }"
            "QPushButton:hover { color: #ffffff; background: #ff4444; border-radius: 2px; }"
        )
        btn_close.clicked.connect(self.close)
        header.addWidget(btn_close)
        layout.addLayout(header)

        # Cota section
        layout.addWidget(_label(self, "COTA DA CONTA  (5h)", 7, bold=True, color="#666666"))

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(_bar_style("#00ff88"))
        layout.addWidget(self.bar)

        self.lbl_pct   = _label(self, "consultando...", 9, bold=True)
        self.lbl_reset = _label(self, "", 8, color="#555555")
        layout.addWidget(self.lbl_pct)
        layout.addWidget(self.lbl_reset)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333333;")
        layout.addWidget(sep)

        # Scripts section
        layout.addWidget(_label(self, "SEUS SCRIPTS", 7, bold=True, color="#666666"))
        self.lbl_scripts = _label(self, "nenhum script rodou ainda", 9)
        layout.addWidget(self.lbl_scripts)

        # Position top-right
        screen = QApplication.primaryScreen().geometry()
        self.adjustSize()
        self.move(screen.width() - self.width() - 10, 10)

        self.timer = QTimer()
        self.timer.timeout.connect(self.atualizar)
        self.timer.start(UPDATE_MS)

        self.show()
        app.exec_()

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1a1a1a; color: #cccccc; border: 1px solid #333333; }"
            "QMenu::item:selected { background: #333333; }"
        )
        menu.addAction("Atualizar agora",
                       lambda: threading.Thread(target=_consultar_cota, daemon=True).start())
        menu.addAction("Zerar scripts", self.zerar_scripts)
        menu.addSeparator()
        menu.addAction("Fechar", self.close)
        menu.exec_(event.globalPos())

    def zerar_scripts(self):
        d = load_data()
        d.update({"tokens": 0, "input_tokens": 0, "output_tokens": 0,
                  "cache_read": 0, "cache_created": 0, "requests": 0})
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)

    # ── Update loop ────────────────────────────────────────────────────────────

    def atualizar(self):
        self._atualizar_cota()
        self._atualizar_scripts()

    def _atualizar_cota(self):
        with _cota_lock:
            pct      = _cota["pct_5h"]
            reset_ts = _cota["reset_5h"]
            erro     = _cota["erro"]

        if erro:
            self.lbl_pct.setStyleSheet(
                f"color: #ff4444; font-family: {_FONT_MONO}; font-size: 9pt; font-weight: bold;"
            )
            self.lbl_pct.setText(f"erro: {erro[:20]}")
            self.lbl_reset.setText("")
            return

        if pct is None:
            return

        usado    = round(pct * 100)
        restante = 100 - usado
        cor = "#ff4444" if restante <= 10 else "#ffaa00" if restante <= 30 else "#00ff88"

        self.lbl_pct.setStyleSheet(
            f"color: {cor}; font-family: {_FONT_MONO}; font-size: 9pt; font-weight: bold;"
        )
        self.lbl_pct.setText(f"{restante}% restante  ({usado}% usado)")
        self.bar.setValue(usado)
        self.bar.setStyleSheet(_bar_style(cor))

        if reset_ts:
            secs = int(reset_ts - time.time())
            if secs > 0:
                h, m = divmod(secs // 60, 60)
                self.lbl_reset.setText(f"reseta em {h}h{m:02d}min")
            else:
                self.lbl_reset.setText("resetando...")

    def _atualizar_scripts(self):
        d = load_data()
        tokens = d.get("tokens", 0)
        reqs   = d.get("requests", 0)
        inp    = d.get("input_tokens", 0)
        out    = d.get("output_tokens", 0)
        if reqs > 0:
            self.lbl_scripts.setText(
                f"{tokens:,} tokens  •  {reqs} req\n↑{inp:,} entrada  ↓{out:,} saída".replace(",", ".")
            )
        else:
            self.lbl_scripts.setText("nenhum script rodou ainda")


if __name__ == "__main__":
    TokenOverlay()
