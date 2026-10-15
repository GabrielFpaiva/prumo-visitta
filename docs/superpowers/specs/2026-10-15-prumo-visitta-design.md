# Prumo Visitta — design v1

**Data:** 2026-10-15 · **Estado:** aguardando revisão do Gabriel
**Slogan:** "A visita começa antes da visita"

## 1. O que é

SaaS que transforma vídeo ou fotos de um imóvel num tour 3D navegável (Gaussian Splatting), em que o
cliente final anda pela cena no navegador. Público: corretores e imobiliárias.

**Prumo** é a marca-mãe de um portfólio para imobiliárias. O CRM Prumo é outro produto, em outro repo,
feito por outro agente: este projeto **não mexe nele**.

**Sucesso da v1:** piloto com 3 corretores reais, em que pelo menos 2 compartilham um tour com cliente
e a taxa de geração bem-sucedida passa de 80%.

## 2. Decisões travadas

| Tema | Decisão |
|---|---|
| Teste grátis | **1 geração por conta** (por e-mail), sem link compartilhável. Nunca volta para a cota |
| Entrada | **Vídeo (caminho principal) + fotos** (alternativa) |
| Conta | Independente do CRM: login por código no e-mail + Stripe. Ponte com o CRM depois (seção 9) |
| Fim da assinatura | Link **pausa** (mesmo link volta ao renovar); tour apagado **90 dias** após pausar |
| Avulso | **Qualquer pessoa** compra (R$ 6,90): 1 geração + link por **30 dias** |
| Qualidade | Preset único **"boa"** (~30 min de GPU) |
| Orquestração | **Cloudflare Queues + Workflows + Vast.ai**, atrás da interface `GpuProvider` |
| Ilimitado | **Uso justo**: 100 gerações/mês com prioridade normal, depois prioridade baixa; até 2 simultâneas |
| Marca | Nasce **neste repo**, em duas camadas (núcleo Prumo + destaque Visitta); o CRM reaproveita depois |
| Repo | `gabrielfpaiva/prumo-visitta`, novo e independente, licença MIT |

## 3. Preços e custo

| Plano | Preço | Inclui |
|---|---|---|
| Padrão | R$ 20/mês | 15 gerações por ciclo + links enquanto ativa |
| Ilimitado | R$ 100/mês | uso justo de 100/ciclo, depois prioridade baixa |
| Avulso | R$ 6,90 (pagamento único) | 1 geração + link por 30 dias |

Custo de GPU estimado: RTX 4090 a ~US$ 0,38/h, preset "boa" ~30 min → ~R$ 1,03 por geração (a medir
na Fase 0). O Ilimitado empata em ~100 gerações/mês, daí o uso justo.

## 4. Domínio

- **Conta**: e-mail, login por código. Tem direito a 1 geração grátis (`gratis_usada_em`).
- **Assinatura**: plano `padrao | ilimitado`, estado vindo só do webhook do Stripe. Cota por ciclo
  (`current_period_start`), não por mês do calendário.
- **Crédito**: compra avulsa paga. Saldo por conta. Não expira até ser usado.
- **Tour**: um imóvel. Estado `rascunho → enviando → na_fila → processando → pronto | falhou`.
- **Captura**: arquivos de entrada do tour (vídeo e/ou fotos) e o resultado da checagem prévia.
- **Geração**: uma execução do motor para um tour. Guarda a origem consumida (`cota | credito | gratis`),
  o `reservationId`, as tentativas e o código de falha.
- **Tentativa**: uma instância de GPU. Guarda host, oferta, preço/hora, início, fim, custo em centavos e
  código de saída.
- **Link**: `/t/<slug>` de um tour. Estado `ativo | pausado`; origem `assinatura | avulso` (avulso com
  `expira_em`).

### Regras

- **R1.** Ordem de consumo ao gerar: cota do plano → crédito avulso → grátis. Sem nenhum → paywall.
- **R2.** Falha **não consome**: a reserva volta para a origem de onde saiu (cota para cota, crédito
  para crédito, grátis para grátis). Nunca vira dinheiro.
- **R3.** A geração grátis nunca tem link.
- **R4.** Link ativo ⇔ assinatura ativa (incluindo 48h de carência em `past_due`) **ou** origem avulso com
  `expira_em > agora`.
- **R5.** Tour com link pausado há 90 dias é apagado (splat e metadados de arquivo). Tour que nunca teve
  link é apagado 90 dias depois do que vier por último: `pronto` ou o fim da assinatura da conta.
  Enquanto a assinatura estiver ativa, nenhum tour é apagado.
- **R6.** Entradas (vídeo/fotos) são apagadas 7 dias depois de o tour ficar `pronto`. Só o splat fica.
- **R7.** Uma geração em andamento por conta (duas no Ilimitado).
- **R8.** Ilimitado acima de 100 gerações no ciclo entra na fila com prioridade baixa, nunca bloqueia.
- **R9.** Nada é cobrado sem clique da pessoa. Cota no teto **oferece** o avulso.

## 5. Componentes

```
prumo-visitta/
  apps/web/            Astro em Cloudflare Workers: site, entrar, painel, upload, Minha assinatura,
                       página pública do tour
  apps/orquestrador/   Worker: consumidor da Queue, Workflow por geração, webhook da GPU,
                       webhook do Stripe, cron ceifador e disjuntor
  packages/core/       núcleo copiado do microsaaas + domínio do Visitta
  packages/marca/      tokens em duas camadas: núcleo Prumo e destaque Visitta
  engine/              imagem Docker (CUDA, ffmpeg, COLMAP, gsplat, splat-transform) + pipeline Python
```

Banco: Neon (Postgres, São Paulo) via Hyperdrive, Drizzle. Arquivos: R2. E-mail: Cloudflare Email.

### Reaproveitado do microsaaas (cópia, sem dependência)

Login por código, sessão, rate limit, e-mail; `BillingGateway` + Stripe com webhook assinado e
idempotente e checkout com claim; `reserveQuota`/`refundQuota`; `lock`; `stored_files` com prazo;
URL assinada direta para o R2 com CORS e CSP vindos da config; `jobs` idempotente; `money`/`time`;
`parseEnv`; testes com PGlite; componentes do kit (Layout, Paywall, contador, Minha assinatura).

### Adaptado

- Período **mensal** pelo ciclo do Stripe (lá era semanal); sai trial de 24h e preview diário.
- **Pagamento único** e saldo de créditos (lá a invariante 8 proibia cobrança extra).
- Arquivos com prazo longo e apagamento por regra (R5, R6), não por TTL de horas.
- Upload **multipart** de muitos arquivos.
- Motor em GPU externa (lá era Cloudflare Container).
- Coluna `product` sai: o repo é de um produto só.
- Troca de plano, cartão e recibos pelo **Stripe Customer Portal**.

## 6. Fluxo

1. **Upload.** O navegador pede URLs assinadas e sobe direto ao R2 em multipart (vídeo até ~2 GB e
   10 min; até 300 fotos). O Worker nunca carrega o arquivo. Ao concluir, HEAD no R2 confere tamanho e tipo.
2. **Checagem prévia** no navegador: bloqueia só o absurdo (vídeo < 1 min, < 40 fotos, resolução baixa);
   o resto vira aviso.
3. **Gerar.** O servidor aplica R1, reserva, aplica R7, cria a Geração e envia à Queue.
4. **Workflow** (id = id da Geração; mensagem repetida não duplica):
   1. busca a oferta (seção 7) e cria a instância com rótulo da Geração;
   2. espera `iniciou` (prazo 15 min);
   3. espera `concluiu` ou `falhou` (prazo 90 min); progresso a cada ~2 min vai ao Neon para a tela;
   4. **concluiu**: HEAD do splat no R2, destrói a instância, registra custo, confirma a reserva,
      e-mail de "tour pronto";
   5. **falha de captura** (`CAPTURE_INSUFFICIENT`, `CAPTURE_TOO_FEW`): sem nova tentativa, devolve (R2),
      mostra o guia sob medida;
   6. **falha de host** (`HOST_*`, prazo estourado, batimento ausente): destrói e tenta outro host,
      excluindo a máquina que falhou, até 2 novas tentativas; esgotou, devolve (R2).
5. **Compartilhar.** Só cria link com plano ativo ou crédito avulso consumido nesse tour (R3, R4).
6. **Página pública.** A cada acesso o Worker confere R4. Ativo: entrega o visualizador com URL assinada
   do splat válida por 1h. Pausado: "tour indisponível". O splat nunca é público.

**Visualizador:** SuperSplat Viewer (PlayCanvas, MIT) embutido. O editor SuperSplat fica fora da v1.

## 7. Vast.ai: operação, falhas e segurança

**Oferta:** RTX 4090, confiabilidade ≥ 0,98, download ≥ 500 Mbps, disco ≥ 60 GB, CUDA ≥ 12,
≤ US$ 0,50/h, **só hosts verificados/datacenter**, mais barata primeiro. Sem oferta: 3090/4080. Sem
nada: espera e tenta de novo em 5 min.

**Imagem:** GHCR, só código aberto, **sem segredo**; enxuta (o pull é cobrado e cabe nos 15 min).

**Host não confiável** (vê o interior da casa; dado pessoal pela LGPD):
- a instância recebe só o do job: URLs assinadas de leitura das entradas e de escrita da saída
  (expiram em 3h) e um segredo HMAC derivado do id da Geração para assinar os callbacks;
- **a chave da API da Vast nunca vai ao host**; quem destrói é sempre o orquestrador;
- R6 limita o tempo de vida das entradas; termos de uso citam o processamento por terceiro.

**Custo:**
- **ceifador** a cada 10 min destrói instância com nosso rótulo sem Geração `processando` ou com mais de 2h;
- **disjuntor diário**: custo do dia acima do teto (config, ex. US$ 30) para de criar instâncias e alerta;
- **alerta de saldo** da conta pré-paga.

**`GpuProvider`:** `criar(oferta, job)`, `destruir(id)`, `listar(rotulo)`, `buscarOfertas(filtro)`.
Adaptador Vast na v1; RunPod é o plano B.

## 8. Motor (engine/)

Entrada: manifesto JSON com URLs assinadas. Passos: baixar → extrair quadros do vídeo (ffmpeg, ~2 fps,
o mais nítido de cada janela, até 300) → COLMAP (modelo de câmera único por lente) → gsplat (preset
"boa") → `splat-transform` para formato comprimido (alvo ~20 MB) → subir → callback.

Códigos de saída: `CAPTURE_TOO_FEW`, `CAPTURE_INSUFFICIENT` (COLMAP registrou < 60% das imagens),
`HOST_DOWNLOAD`, `HOST_CUDA`, `HOST_DISK`, `HOST_UPLOAD`, `ENGINE_ERROR`.

## 9. Marca e CRM

**Marca:** `packages/marca` em duas camadas: **núcleo Prumo** (wordmark, tipografia, neutros, tom de
voz) e **destaque Visitta** (cor de acento). O CRM copia o núcleo depois e escolhe o próprio acento.
Telas e marca desenhadas no Pencil na Fase 0.

**Ponte com o CRM (fora da v1):** conta por e-mail nos dois; o CRM (Better Auth) pode virar provedor
OIDC e o Visitta ganha "Entrar com Prumo". O imóvel do CRM guarda só o link `/t/<slug>`. Cobrança
continua separada (Stripe aqui, Asaas lá).

## 10. Guia de captura

Tela curta antes do primeiro upload (6 regras + vídeo de 30 s), checklist ao lado do botão de enviar,
e guia sob medida depois de falha de captura.

- **Vídeo:** horizontal, lente 1x, 4K30 ou 1080p60; travar foco e exposição; luzes acesas, sem contraluz;
  andar devagar (meio passo por segundo), câmera no peito, **nunca girar parado**; contornar cada
  cômodo olhando para o centro; atravessar portas devagar; sem pessoas ou pets no quadro; espelhos e
  vidros geram aviso; 1–2 min por cômodo, até 10 min.
- **Fotos:** 60–200, cada uma cobrindo ~2/3 da anterior, um passo entre fotos; sem zoom, sem modo
  retrato, mesma lente.
- **Limite v1:** imóvel até ~150 m².

## 11. Testes

- **Domínio** (PGlite + migrações reais): R1–R9.
- **Orquestração** com `FakeGpu`: host que não sobe, host mudo, falha de captura, sucesso, evento
  repetido. Afirma que a instância foi destruída em todos os casos e que o ceifador pega a órfã.
- **Webhooks** Stripe e GPU: assinatura válida, inválida, repetida.
- **Motor:** teste local sem GPU (quadros, nitidez, códigos de saída); smoke numa 4090 real com captura
  de referência antes de cada versão da imagem.

## 12. Fases

0. **Spike do motor + marca.** 3 imóveis reais gravados no celular, pipeline rodado à mão na Vast.
   Mede tempo, custo e se a qualidade vende. **Se não vender, para aqui.** Marca e telas no Pencil.
1. **Base:** repo, núcleo copiado, conta, Stripe (3 preços), cota, créditos.
2. **Motor + orquestração:** upload multipart, Queue, Workflow, `GpuProvider` Vast, webhooks, ceifador,
   disjuntor.
3. **Tour:** visualizador, link, paywall, página pública, e-mail de pronto.
4. **Lançamento:** guia de captura, termos (LGPD), domínio, piloto com 3 corretores.

## 13. Fora da v1

App nativo de captura com guia em tempo real · escolha de qualidade · editor SuperSplat · conta por
imobiliária com vários corretores · login unificado com o CRM · fatura única · locação/plantas.

## 14. Riscos

- **Qualidade da captura amadora** é o maior risco; a Fase 0 decide se o produto existe.
- **Confiabilidade da Vast**: mitigada por novas tentativas, ceifador e `GpuProvider`.
- **LGPD** com host de terceiro: mitigada na seção 7; termos precisam de revisão.
- **Workflows e Queues no plano pago** da Cloudflare: conferir limites do plano grátis antes da Fase 2.
- **Pix no Checkout de pagamento único**: confirmar disponibilidade na conta Stripe.
- **Domínio**: a definir na Fase 4.
