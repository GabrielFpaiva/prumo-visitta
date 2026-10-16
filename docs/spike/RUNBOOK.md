# Spike do motor na Vast.ai — roteiro

Objetivo: rodar o motor em 3 imóveis reais e medir tempo, custo e qualidade (spec §12, Fase 0).
**Regra de ouro: toda instância criada é destruída no fim, mesmo quando der erro.**

## Uma vez só (Gabriel)

1. R2: `wrangler r2 bucket create visitta-spike` e, no painel da Cloudflare, uma regra de ciclo de vida
   apagando objetos com mais de 14 dias. Criar um **R2 API token** só com leitura e escrita nesse bucket.
   Exportar no terminal (não salvar em arquivo do repo):
   `export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=...`
2. Vast.ai: criar conta, pôr US$ 10 de crédito, `uv tool install vastai` e `vastai set api-key <chave>`.
   A chave fica só na máquina do Gabriel.

## Captura

Seguir o guia do spec §10. Por imóvel, uma pasta `~/visitta-capturas/<imovel>/` com os vídeos e/ou fotos.
Pelo menos um dos 3 imóveis só com fotos, para medir o caminho alternativo.

## Por job (um imóvel × um preset)

    cd engine
    uv run --group tools python tools/make_manifest.py --dir ~/visitta-capturas/apto-01 --job apto-01 --preset boa

Guarde a linha `VISITTA_MANIFEST_URL=...` e as URLs das saídas.

    vastai search offers 'gpu_name=RTX_4090 num_gpus=1 reliability>0.98 inet_down>500 disk_space>=60 cuda_vers>=12.4 verified=true dph<=0.5' -o 'dph'

Escolha o `ID` da primeira linha e anote o `$/hr`.

    vastai create instance <ID> \
      --image ghcr.io/gabrielfpaiva/visitta-engine:latest \
      --disk 60 \
      --label visitta-spike-apto-01-boa \
      --env '-e VISITTA_MANIFEST_URL=<url do manifesto>' \
      --args run

Se o `create` recusar `--args`, confira `vastai create instance --help` e use o modo que roda o
`ENTRYPOINT` da imagem com o argumento `run`.

Acompanhar:

    vastai show instances
    vastai logs <INSTANCE_ID> --tail 50

Quando o log mostrar o fim do processo (`falhou: ...` ou saída sem erro) **ou** passar de 90 min:

    vastai destroy instance <INSTANCE_ID>
    vastai show instances   # tem que voltar vazio

## Medir

Baixe `report.json` e `viewer.html` pelas URLs impressas. Abra o `viewer.html` no navegador do celular
e do computador. Preencha uma linha em `resultados.md`. Custo = `$/hr` × (tempo de vida da instância em
horas, de `vastai show instances` antes de destruir) × 5,40.
