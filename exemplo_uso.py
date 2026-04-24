"""
Exemplo de uso do claude_tracker.
Execute este script enquanto o overlay (iniciar.pyw) está aberto
para ver os tokens atualizando em tempo real.
"""

from claude_tracker import cliente, resetar_tokens, definir_limite

# Define limite para mostrar barra de progresso no overlay (opcional)
definir_limite(100_000)

print("Fazendo chamada à API da Claude...")

resposta = cliente.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Explique em uma frase o que são tokens de LLM."}],
)

print("\nResposta:", resposta.content[0].text)
print(f"\nTokens usados nesta chamada:")
print(f"  Input:  {resposta.usage.input_tokens}")
print(f"  Output: {resposta.usage.output_tokens}")

print("\nFazendo chamada com streaming...")

with cliente.messages.stream(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Conte de 1 a 5 em português, um por linha."}],
) as stream:
    for texto in stream.text_stream:
        print(texto, end="", flush=True)

print("\n\nVerifique o overlay — os totais foram atualizados!")

# Para zerar quando quiser começar uma nova sessão:
# resetar_tokens()
