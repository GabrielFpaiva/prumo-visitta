# CLAUDE.md — Prumo Visitta

Tour 3D navegável (Gaussian Splatting) para corretores. Fonte da verdade:
`docs/superpowers/specs/2026-10-15-prumo-visitta-design.md` → planos em `docs/superpowers/plans/`.

## Estado
Fase 0: só existe `engine/` (motor Python + imagem Docker) e o roteiro do spike em `docs/spike/`.

## Comandos
cd engine && uv sync --extra colmap && uv run pytest

## Invariantes
1. Imagem Docker sem segredo. A chave da Vast nunca vai ao host; quem cria a instância destrói.
2. O host recebe só URLs assinadas daquele job (expiram em 3h) e, opcionalmente, um segredo HMAC do job.
3. Códigos de erro só os do spec §8 (+ MANIFEST_INVALID). Só HOST_* é repetível.
4. Arquivo ilegível no meio de entradas boas é pulado e contado, nunca derruba o job.
5. Testes rodam sem GPU, sem rede externa e sem segredo.

## Convenções
Código e identificadores em inglês; docs e mensagens para humanos em português.
Commits em inglês, atômicos, sem Co-Authored-By.
