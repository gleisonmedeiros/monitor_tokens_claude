# Monitoramento de Tokens Claude

Overlay visual para Windows que monitora em tempo real o uso de tokens da API Claude — tanto a **cota da conta** (browser + IDE + CLI + scripts) quanto os tokens consumidos pelos **seus scripts Python**.

---

## Como funciona

O projeto tem duas partes independentes que trabalham juntas:

### 1. `claude_tracker.py` — Rastreador global
Um wrapper sobre o cliente oficial da Anthropic que intercepta cada chamada à API e registra o uso de tokens em `~/.claude_monitor/tokens.json`.

- Autentica via **OAuth** (reutiliza o token do Claude Code, sem precisar de `ANTHROPIC_API_KEY`)
- Renova o token automaticamente quando expira
- Thread-safe (usa `threading.Lock`)
- Suporta chamadas normais (`create`) e streaming (`stream`)

### 2. `monitor_tokens.py` — Overlay visual (Tkinter)
Janela flutuante sem bordas que fica sempre no topo da tela. Atualiza a cada 1 segundo.

Exibe duas seções:

| Seção | O que mostra |
|-------|--------------|
| **COTA DA CONTA (5h)** | Uso percentual da cota da Anthropic (todos os clientes) + tempo para reset |
| **SEUS SCRIPTS** | Tokens e requisições feitas pelos seus scripts Python |

A cota real é consultada diretamente nos **headers HTTP de rate limit** da API (`anthropic-ratelimit-unified-5h-utilization`, etc.), fazendo uma requisição mínima de 1 token a cada **2 minutos** (120s) para reduzir o consumo.

---

## Estrutura de arquivos

```
Monitoramento_tokens_claude/
├── claude_tracker.py   # wrapper do cliente + registro de tokens
├── monitor_tokens.py   # overlay visual (Tkinter)
├── iniciar.pyw         # ponto de entrada — duplo clique para abrir
├── configurar.py       # configuração inicial da chave de API (opcional, não necessário com OAuth)
├── exemplo_uso.py      # exemplo de uso do claude_tracker
└── tokens.json         # dados locais de uso (sincronizados com ~/.claude_monitor/)
```

**Arquivo global:** `~/.claude_monitor/tokens.json` — compartilhado entre todos os projetos que usam `claude_tracker`.

---

## Instalação e uso

### Pré-requisitos
- Python 3.8+
- Biblioteca `anthropic`: `pip install anthropic`
- Claude Code instalado (fornece o token OAuth em `~/.claude/.credentials.json`)

### Abrir o overlay

**Opção 1: Duplo clique em `iniciar.pyw`**
- Abre sem janela de console, sem pedir chave de API

**Opção 2: Executar em background (Windows) — use `iniciar_no_windows.vbs`**
- Duplo clique em `iniciar_no_windows.vbs` para abrir o overlay totalmente hidden
- Não mostra nenhuma janela, roda completamente em background
- Ideal para inicialização automática no boot

**Opção 3: Linha de comando**
```bash
python iniciar.pyw
```

### Usar o rastreador nos seus scripts

```python
from claude_tracker import cliente

resposta = cliente.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Olá!"}],
)
print(resposta.content[0].text)
# tokens são registrados automaticamente
```

Com streaming:

```python
with cliente.messages.stream(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Conte de 1 a 5."}],
) as stream:
    for texto in stream.text_stream:
        print(texto, end="", flush=True)
```

### Funções utilitárias

```python
from claude_tracker import resetar_tokens, definir_limite

definir_limite(100_000)   # define um limite de referência
resetar_tokens()          # zera contadores (mantém o limite)
resetar_tokens(manter_limite=False)  # zera tudo
```

---

## Inicialização automática no Windows

### Via Task Scheduler (Recomendado)

1. Abre **Task Scheduler** (Agendador de Tarefas)
2. **Create Basic Task**
3. Nome: `Monitor de Tokens Claude`
4. Trigger: `At startup`
5. Action: 
   - Program: `C:\Windows\System32\wscript.exe`
   - Arguments: `"C:\caminho\para\rodar.vbs"`
   - Start in: `C:\caminho\para\pasta\do\projeto`
6. **OK**

### Via atalho na pasta Startup

1. Cria atalho para `rodar.vbs`
2. Move para: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
3. Pronto — roda automaticamente no boot

---

## Dados registrados (`tokens.json`)

```json
{
  "tokens": 1500,
  "input_tokens": 1200,
  "output_tokens": 300,
  "cache_read": 0,
  "cache_created": 0,
  "requests": 5,
  "limite": 50000,
  "ultima_atualizacao": "2026-04-23T14:30:00"
}
```

---

## Interface do overlay

```
┌─────────────────────────┐
│ COTA DA CONTA  (5h)     │
│ ████████░░░░░░░░░░░░░░  │
│ 65% restante (35% usado)│
│ reseta em 3h42min       │
│ ─────────────────────── │
│ SEUS SCRIPTS            │
│ 1.500 tokens  •  5 req  │
│ ↑1.200 entrada ↓300 saída│
└─────────────────────────┘
```

- **Clique e arraste** para mover
- **Botão direito** para menu de opções (atualizar, zerar scripts, fechar)
- Cor da barra muda conforme a cota restante: verde → amarelo → vermelho

---

## Autenticação OAuth

O projeto usa o token OAuth do Claude Code armazenado em `~/.claude/.credentials.json` — **não é necessária `ANTHROPIC_API_KEY`**. O token é renovado automaticamente via `refresh_token` quando expira (margem de 60 segundos).
