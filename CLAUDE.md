# Légua

Biblioteca LoRa P2P (sem LoRaWAN) para rádios Semtech SX12xx, com adaptação negociada de modo
(PROPOSE/VOTE/COMMIT), troca em instante combinado, janela de validação, âncora em NVM e rollback.
Referência de hardware: Heltec WiFi LoRa 32 V4 (ESP32-S3 + SX1262, até 28 dBm), faixa 915 MHz.

Leia `docs/` antes de mudar protocolo, perfil regulatório ou plano de testes.

## Estado atual
- `simsuite/` (Python): suíte de simulação, referência executável do protocolo.
- `core/` (C99): **Fases 0 e 2** prontas: codec do pacote v0 (controle de 16 B), tempo no ar, DATA/ACK, descoberta,
  negociação PROPOSE/VOTE/COMMIT, validação, âncora, rollback, escada, silêncio, potência, perfil móvel, `fade_k`,
  registro de NVM (âncora, bloco do contador, piso do par), teto de TX do par nos controles (margem do pior sentido). É **equivalente a `simsuite/protocol/endpoint.py`**: o
  teste de equivalência compara os rastros byte a byte nos quatro pares Py/C. **Ainda não existem:** driver SX1262,
  porte ESP32, exemplos Arduino/ESP-IDF, guarda das chaves no porte, CAD/LBT.
- **MIC v0:** AES-128-CMAC truncado a 4 B (docs/07 §6). Referência opcional em `core/src/mic_cmac.c` e
  `simsuite/protocol/mic.py`, vetores em `core/tests/vectors/mic.txt`. A simulação e a equivalência usam o MIC de
  teste (FNV-1a), que não é segurança. `mic()` devolve <0 sem chave e o codec recusa. Limite de falhas de MIC
  (`mic_fail_n`/`_window`/`_hold`): congela a negociação, mantém o modo. Chaves (docs/07 §6.1 e §6.2): uma por
  enlace; rotação em ciclo pelo `key_id` (`legua_key_rotate`, `Endpoint.rotate_key`), estado no registro de NVM.
- Formato do pacote: `docs/07`; interfaces: `docs/08`. `simsuite/protocol/wire.py` e `core/src/frame.c` devem
  concordar (vetores em `core/tests/vectors/`; `make -C core vectors` regenera, junto com a tabela de modos
  `core/profiles/br2026.h` gerada por `tools/gen_modetab.py`).
- **Mexeu em `endpoint.py` ou `endpoint.c`?** Os dois têm de continuar equivalentes: rode
  `PYTHONPATH=. python3 -m pytest -q simsuite/tests/test_equivalencia.py` (`LEGUA_EQUIV_SEEDS=200` para varrer mais) e
  `make -C core fuzz`. Parâmetro novo no protocolo = campo em `Config` **e** em `legua_params` (e no `pyshim.c`).
- **Escopo (docs/09):** este repositório é só **simulação, protocolo e especificação**. Os experimentos práticos com as
  Heltec e o firmware (drivers SX1262, portes ESP32-S3, exemplos, bancada) vão para um repositório separado, a criar
  depois com `/anthropic-skills:aiclp-kit-bancada-vm`. Não criar drivers, portes nem scripts de bancada aqui. Os
  resultados daqui valem só para comparar e dimensionar até a bancada devolver a calibração (docs/09, §4).
  **`core/` fica aqui** até o protocolo congelar; a bancada usa como submódulo numa tag `core-vX.Y.Z` (docs/09 §5).
  Depois vai para um repositório próprio (`legua-core`).
- **Site de resultados** (`site/`, GitHub Pages, publicado por `.github/workflows/pages.yml`): mostra as escalas rápida
  (`simsuite/results/`) e longa (`simsuite/results_full/`, ignorada pelo git), com seletor de escala, aba de comparação,
  orçamento de tempo e aba de **Estimativas** (estimador analítico no navegador, `site/estimator.js`, com referência
  Python em `simsuite/analysis/estimator.py` e teste de paridade). Gerar dados: `~/.venvs/legua/bin/python tools/build_site.py`
  (precisa do venv: importa numpy). Abrir `site/index.html` direto também funciona. A aba Estimativas guarda o estado no
  fragmento da URL (`#estimativas?d=2&sf=9...`), copia resumo e link e exporta CSV/JSON; tudo local, sem rede
  (`test_site_dom.py`, precisa de node+jsdom). `site/enlace.html` = testador de enlaces (perfil digitado, Fresnel, Bullington, margem por modo;
  `propagacao.js`, `terreno.js`, `enlace.js`; referência Python `simsuite/analysis/enlace.py`, docs/09 §7.1). Plano das
  próximas fases (elevação, mapa, calibração): `reports/` (local, fora do git).
- Site: `site/explica.js` tem as explicações em linguagem simples (uma por cartão, casada pelo título), os diagramas SVG, o guia
  interativo da aba "Comece aqui" e o glossário. Cartão novo no `app.js` = entrada nova em `EX` (o teste `test_explica.py` confere).
- Validação sim×sim: LoRaSim e Meshtasticator com os **originais executados** (docs/09 §9.1; clones em `~/.cache/ext/`,
  `simpy==3.0.10` opcional). Rascunho de artigo em `docs/10`. Licença: Apache-2.0 (`LICENSE`). Cenário `P` = varredura de potência de TX; `V` e `S` = varreduras da janela de validação e do silêncio; `X` = estresses (erro de relógio × cristal, perda assimétrica, teto × `fade_k`). Roteamento por
  inundação do Meshtastic: decidido não comparar (docs/09 §9.1). Próximo: ressincronização autenticada do contador do par (desenho em docs/07 §6.3; implementar após decisão do autor, muda o formato de fio). A escala `full` leva ~1 h 10 min com `--procs 1`; repetir se o protocolo mudar.

## Comandos
```bash
python3 -m venv ~/.venvs/legua && ~/.venvs/legua/bin/pip install -r requirements.txt   # o pip do sistema é bloqueado (PEP 668)
PYTHONPATH=. python3 -m pytest -q simsuite/tests                    # 69 testes (inclui núcleo C, MIC e site), ~20 s
make -j1 -C core test                                               # núcleo C99: codec, simulador de 2 nós, biblioteca de teste
make -j1 -C core fuzz                                               # robustez com ASan e UBSan (~1 min)
~/.venvs/legua/bin/python tools/build_site.py                       # atualiza site/data.js (após rodar a suíte)
python3 tools/build_consolidado.py                                  # atualiza site/consolidado.html (resultados, discussões, trabalhos futuros)
PYTHONPATH=. python3 -m simsuite.analysis.orcamento                 # orçamento de tempo da escala full
PYTHONPATH=. python3 -m simsuite.run_suite --escala full --procs 1  # escala longa em results_full/ (~66 min); recusa se a estimativa passar de 8 h (--limite-horas, --forcar)
tools/ci_local.sh [--suite]                                         # tudo, em 1 job e baixa prioridade
PYTHONPATH=. ~/.venvs/legua/bin/python tools/validar_estimador.py   # estimador x simulador (~3 min)
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick           # ~40 s, gera simsuite/results/
```

## Mapa do código
`core/`: `include/legua/{legua,port,radio}.h`, `src/{frame,toa,endpoint,mic_cmac}.c`, `include/legua/mic_cmac.h`, `profiles/br2026.h` (gerado), `tests/` (codec,
simulador, tabela de ToA, fuzz, `pyshim.c` = ponte ctypes para o teste de equivalência).

### `simsuite/`
- `core/` rádio (ToA, sensibilidade, LDRO, Doppler), canais, mobilidade, regulação BR-2026, simulador de eventos (DES).
- `protocol/endpoint.py` máquina de estados do protocolo (BASE/DATA/NEGOCIANDO/AGUARDA_COMMIT/VALIDANDO/RECUPERACAO).
  É o modelo do que o núcleo C99 deve fazer. `protocol/modes.py` tem a tabela de modos.
- `formal/checker.py` verificação de estados explícita (propriedades P1 a P4, ablações) e cadeia de Markov.
  P4 (âncora de um modo em que o par já esteve) é a que separa a validação e a âncora tardia; P1 e P3 não as justificam.
- `protocol/perfis.py` perfis nomeados da sintonia F7 (`padrao`, `estavel`, `cauteloso`), iguais em `legua_params_profile`.
- `scenarios/` bancada (B2–B11), campo (F1–F6), mobilidade (M1–M7). `baselines/` modelos de malha de terceiros.
- `analysis/` estatística, telemetria JSONL, relatório. `run_suite.py` orquestra tudo.

## Regras do projeto
- Idioma: documentos e respostas em português do Brasil; código, API e nomes de símbolos em inglês.
- **Nome:** o projeto é "Légua" (docs/00). "AdapLoRa" (um só "t") é outro trabalho (ICNP 2020); não confundir.
  Não usar "LoRa" como parte do nome de pacote ou produto; usar `legua` (sem acento) em registros.
- **Regulação:** o perfil BR-2026 vem de fonte secundária. Marque sempre como `nao_verificado`; nunca afirme
  que a biblioteca é "conforme" ou "homologada". A conformidade é do produto; a biblioteca respeita o teto do integrador.
- **Resultados de simulação** têm parâmetros estimados (canal, corrente do PA, deriva). Sirvam para comparar e
  dimensionar; não apresente como previsão de campo. Rotule a escala (quick/full) e a semente.
- **Núcleo futuro:** C99, sem alocação dinâmica, sem biblioteca de terceiros, sem E/S no núcleo (máquina de estados pura:
  recebe eventos, devolve ações). Drivers: SX1262 primeiro; SX127x só depois do protocolo congelado.
- **Segurança:** sem chave padrão, sem chave derivada do MAC; controle sempre autenticado; contador anti-replay em NVM.
- **Privacidade:** nunca commitar chaves, dados brutos de campo com GNSS, nem dados pessoais.
- Não alegar novidade que a literatura já cobre. A contribuição defensável é acordo + validação + âncora + rollback,
  com verificação formal, dentro de um envelope regulatório executável (docs/05).

## Git
- Identidade local: `Isaac Miranda <19537105+isaacmiranda@users.noreply.github.com>`. Não usar o e-mail pessoal.
- Commits com `-s` (DCO). Confira `git log -1 --format='%an <%ae>'` antes de enviar.
- **Não rodar `git push` sem pedido explícito.** Não reescrever histórico já enviado.
- Mensagens de commit curtas, em português, no imperativo.

## Antes de dar uma tarefa por concluída
1. Rodar os testes (`pytest`) e, se tocou no protocolo, a suíte rápida.
2. Se mudou `protocol/` ou `formal/`, rodar o verificador (cenário `formal` da suíte) e checar P1 e P3.
3. Atualizar `docs/` quando uma decisão de protocolo ou de regulação mudar.
