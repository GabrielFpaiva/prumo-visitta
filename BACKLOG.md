# Backlog — Prumo Visitta

Estado em 16/10/2026: motor da Fase 0 na `main`, imagem `ghcr.io/gabrielfpaiva/visitta-engine:latest`
pública, R2 (`visitta-spike`, conta Cloudflare pessoal) e conta Vast.ai prontos.

## Agora: spike da Fase 0

- [ ] **Segurança:** apagar no painel da Cloudflare o 1º token R2 (o de "All R2 buckets", que vazou num print).
- [ ] Conferir que o bucket `visitta-spike` tem a regra de ciclo de vida de 14 dias.
- [ ] Capturar 3 imóveis (até ~150 m²) seguindo o spec §10, **com vídeo HDR desligado**:
      2 com vídeo e 1 só com fotos. Uma pasta por imóvel em `~/visitta-capturas/<imovel>/`.
- [ ] 1º job em `rapida` pelo `docs/spike/RUNBOOK.md` (as variáveis `R2_*` são exportadas no terminal, nunca em arquivo).
- [ ] Rodar os outros presets e preencher `docs/spike/resultados.md`; escrever o veredito.
- [ ] Marca no Pencil (em paralelo).

## O 1º job na GPU responde

- O leitor de COLMAP do gsplat aceita o modelo gerado pelo pycolmap 4.2.1?
- O `splat-transform` roda sem tela dentro do container?
- O `--disable-video` mantém o PSNR do último passo (`stats/val_step*.json`)?

## Depois do veredito

- [ ] Planos das Fases 1–4 (spec em `docs/superpowers/specs/2026-10-15-prumo-visitta-design.md`).

## Ajustes adiados do motor (revisões da Fase 0)

- Cota de quadros dividida igual entre vídeos, mesmo quando um vídeo rende menos.
- EXIF se perde ao normalizar as fotos.
- Transferências: espera depois da última tentativa; erro 4xx é repetido.
- Nada vai para o stdout (só stderr).
- Dockerfile: não usa o `uv.lock`; base cudnn redundante; smoke não testa `gsplat.csrc`; sem cache no buildx.
- `test_every=8` do trainer deixa 1/8 das vistas fora do treino.
- RUNBOOK usa `:latest`; fixar pelo SHA quando o spike começar a comparar rodadas.
