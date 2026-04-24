"""
Tracker global de tokens Claude.
Instalado em ~/.claude_monitor/ — acessível de qualquer projeto.

Uso em qualquer projeto:
    from claude_tracker import cliente

    r = cliente.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Olá!"}],
    )
    print(r.content[0].text)
"""

import json
import time
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

MONITOR_DIR = Path.home() / ".claude_monitor"
TOKENS_FILE = MONITOR_DIR / "tokens.json"
CREDS_FILE  = Path.home() / ".claude" / ".credentials.json"

_lock = threading.Lock()
_client_cache = {"client": None, "token": None}


# ── Credenciais OAuth ──────────────────────────────────────────────────────────

def _ler_creds() -> dict:
    try:
        with open(CREDS_FILE, encoding="utf-8") as f:
            return json.load(f).get("claudeAiOauth", {})
    except Exception:
        return {}


def _token_expirado(creds: dict) -> bool:
    exp = creds.get("expiresAt", 0)
    # expiresAt é timestamp em milissegundos
    return (exp / 1000) < (time.time() + 60)


def _renovar_token(creds: dict) -> str:
    """Usa o refresh_token para obter novo access_token."""
    refresh = creds.get("refreshToken", "")
    if not refresh:
        raise RuntimeError("Sem refresh token disponível.")

    dados = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": "9d1c250a-e61b-48ad-ad52-4cce87dfe5b1",  # Claude Code client_id
    }).encode()

    req = urllib.request.Request(
        "https://auth.anthropic.com/oauth/token",
        data=dados,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        novo = json.loads(resp.read())

    # Salva credenciais atualizadas
    try:
        with open(CREDS_FILE, encoding="utf-8") as f:
            arq = json.load(f)
        arq["claudeAiOauth"]["accessToken"]  = novo["access_token"]
        arq["claudeAiOauth"]["expiresAt"]    = int(time.time() * 1000) + novo.get("expires_in", 3600) * 1000
        if "refresh_token" in novo:
            arq["claudeAiOauth"]["refreshToken"] = novo["refresh_token"]
        with open(CREDS_FILE, "w", encoding="utf-8") as f:
            json.dump(arq, f, indent=2)
    except Exception:
        pass

    return novo["access_token"]


def _obter_token() -> str:
    creds = _ler_creds()
    if _token_expirado(creds):
        return _renovar_token(creds)
    return creds.get("accessToken", "")


# ── Cliente Anthropic ──────────────────────────────────────────────────────────

def _criar_client():
    import anthropic
    token = _obter_token()
    client = anthropic.Anthropic(
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )
    _client_cache["token"]  = token
    _client_cache["client"] = client
    return client


def _get_client():
    """Retorna o cliente, renovando token se necessário."""
    creds = _ler_creds()
    if _token_expirado(creds) or _client_cache["client"] is None:
        return _criar_client()
    return _client_cache["client"]


# ── Registro de uso ────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        with open(TOKENS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _registrar(uso) -> None:
    with _lock:
        d = _load()
        entrada      = getattr(uso, "input_tokens",              0) or 0
        saida        = getattr(uso, "output_tokens",             0) or 0
        cache_lido   = getattr(uso, "cache_read_input_tokens",   0) or 0
        cache_criado = getattr(uso, "cache_creation_input_tokens", 0) or 0

        d["tokens"]        = d.get("tokens",        0) + entrada + saida
        d["input_tokens"]  = d.get("input_tokens",  0) + entrada
        d["output_tokens"] = d.get("output_tokens", 0) + saida
        d["cache_read"]    = d.get("cache_read",    0) + cache_lido
        d["cache_created"] = d.get("cache_created", 0) + cache_criado
        d["requests"]      = d.get("requests",      0) + 1
        d["ultima_atualizacao"] = datetime.now().isoformat(timespec="seconds")
        d.setdefault("limite", 0)
        _save(d)


# ── Wrapper do cliente ─────────────────────────────────────────────────────────

class _ClienteRastreado:
    @property
    def messages(self):
        return _MessagesRastreado()

    def __getattr__(self, name):
        return getattr(_get_client(), name)


class _MessagesRastreado:
    def create(self, **kwargs):
        r = _get_client().messages.create(**kwargs)
        if hasattr(r, "usage") and r.usage:
            _registrar(r.usage)
        return r

    def stream(self, **kwargs):
        return _StreamRastreado(_get_client().messages.stream(**kwargs))

    def __getattr__(self, name):
        return getattr(_get_client().messages, name)


class _StreamRastreado:
    def __init__(self, ctx):
        self._ctx    = ctx
        self._stream = None

    def __enter__(self):
        self._stream = self._ctx.__enter__()
        return self._stream

    def __exit__(self, *args):
        res = self._ctx.__exit__(*args)
        try:
            msg = self._stream.get_final_message()
            if hasattr(msg, "usage") and msg.usage:
                _registrar(msg.usage)
        except Exception:
            pass
        return res

    def __getattr__(self, name):
        return getattr(self._ctx, name)


# ── Utilitários públicos ───────────────────────────────────────────────────────

def resetar_tokens(manter_limite: bool = True) -> None:
    with _lock:
        d = _load()
        _save({
            "tokens": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read": 0, "cache_created": 0, "requests": 0,
            "limite": d.get("limite", 0) if manter_limite else 0,
            "ultima_atualizacao": datetime.now().isoformat(timespec="seconds"),
        })


def definir_limite(limite: int) -> None:
    with _lock:
        d = _load()
        d["limite"] = limite
        _save(d)


# Instância pronta para uso
cliente = _ClienteRastreado()
