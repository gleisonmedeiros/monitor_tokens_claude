"""
Executa UMA VEZ para configurar a chave de API da Anthropic.
Salva no arquivo .env local (nunca sobe para o git).
"""
import os
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def main():
    print("=" * 50)
    print("  Configuração — Monitoramento de Tokens Claude")
    print("=" * 50)

    chave_atual = ""
    if ENV_FILE.exists():
        for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if linha.startswith("ANTHROPIC_API_KEY="):
                chave_atual = linha.split("=", 1)[1].strip()
                break

    if chave_atual:
        print(f"\nChave atual: {chave_atual[:12]}...{chave_atual[-4:]}")
        resp = input("Deseja substituir? (s/N): ").strip().lower()
        if resp != "s":
            print("Mantida. Nada alterado.")
            return

    print("\nCole sua chave de API da Anthropic (começa com sk-ant-...)")
    chave = input("ANTHROPIC_API_KEY: ").strip()

    if not chave.startswith("sk-"):
        print("Chave inválida. Deve começar com 'sk-'.")
        return

    # Lê outras variáveis existentes para não apagar
    outras = []
    if ENV_FILE.exists():
        for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if not linha.startswith("ANTHROPIC_API_KEY"):
                outras.append(linha)

    linhas = [f"ANTHROPIC_API_KEY={chave}"] + outras
    ENV_FILE.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(f"\nChave salva em: {ENV_FILE}")
    print("Pronto! Execute 'iniciar.pyw' para abrir o overlay.")


if __name__ == "__main__":
    main()
