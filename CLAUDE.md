# Légua (antes "AdaptLoRa")

Biblioteca LoRa P2P (sem LoRaWAN) para rádios Semtech SX12xx, com adaptação negociada de modo
(PROPOSE/VOTE/COMMIT), troca em instante combinado, janela de validação, âncora em NVM e rollback.
Referência de hardware: Heltec WiFi LoRa 32 V4 (ESP32-S3 + SX1262, até 28 dBm), faixa 915 MHz.

Leia `docs/` antes de mudar protocolo, perfil regulatório ou plano de testes.

## Estado atual
- `simsuite/` (Python): suíte de simulação, referência executável do protocolo.
- `core/` (C99): **Fase 0** pronta: codec do pacote v0, tempo no ar, DATA/ACK com retransmissão, simulador de dois
  nós, contratos de rádio e de porte. **Ainda não existem:** negociação PROPOSE/VOTE/COMMIT, driver SX1262, porte
  ESP32, exemplos Arduino/ESP-IDF, cripto real (só MIC de teste).
- Formato do pacote: `docs/07`; interfaces: `docs/08`. `simsuite/protocol/wire.py` e `core/src/frame.c` devem
  concordar (vetores em `core/tests/vectors/`; `make -C core vectors` regenera).
- **Escopo (docs/09):** este repositório é só **simulação, protocolo e especificação**. Os experimentos práticos com as
  Heltec e o firmware (drivers SX1262, portes ESP32-S3, exemplos, bancada) vão para um repositório separado, a criar
  depois com `/anthropic-skills:aiclp-kit-bancada-vm`. Não criar drivers, portes nem scripts de bancada aqui. Os
  resultados daqui valem só para comparar e dimensionar até a bancada devolver a calibração (docs/09, §4).
  Onde o `core/` mora no fim é decisão pendente.
- **Site de resultados** (`site/`, GitHub Pages, publicado por `.github/workflows/pages.yml`): mostra as escalas rápida
  (`simsuite/results/`) e longa (`simsuite/results_full/`, ignorada pelo git), com seletor de escala, aba de comparação,
  orçamento de tempo e aba de **Estimativas** (estimador analítico no navegador, `site/estimator.js`, com referência
  Python em `simsuite/analysis/estimator.py` e teste de paridade). Gerar dados: `~/.venvs/legua/bin/python tools/build_site.py`
  (precisa do venv: importa numpy). Abrir `site/index.html` direto também funciona.
- Próximo passo (simulação): Fase 2 no núcleo C com teste de equivalência contra `endpoint.py`; validação sim×sim
  (docs/09, §8). A escala `full` já foi rodada (66 min, `--procs 1`); repetir se o protocolo mudar.

## Comandos
```bash
python3 -m venv ~/.venvs/legua && ~/.venvs/legua/bin/pip install -r requirements.txt   # o pip do sistema é bloqueado (PEP 668)
PYTHONPATH=. python3 -m pytest -q simsuite/tests                    # 26 testes (inclui núcleo C e site), ~20 s
make -j1 -C core test                                               # núcleo C99: codec, simulador de 2 nós
~/.venvs/legua/bin/python tools/build_site.py                       # atualiza site/data.js (após rodar a suíte)
PYTHONPATH=. python3 -m simsuite.analysis.orcamento                 # orçamento de tempo da escala full
PYTHONPATH=. python3 -m simsuite.run_suite --escala full --procs 1  # escala longa em results_full/; veja docs/09 para o tempo
tools/ci_local.sh [--suite]                                         # tudo, em 1 job e baixa prioridade
PYTHONPATH=. ~/.venvs/legua/bin/python tools/validar_estimador.py   # estimador x simulador (~3 min)
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick           # ~40 s, gera simsuite/results/
```

## Mapa do código
`core/`: `include/legua/{legua,port,radio}.h`, `src/{frame,toa,endpoint}.c`, `tests/` (codec, simulador, tabela de ToA).

### `simsuite/`
- `core/` rádio (ToA, sensibilidade, LDRO, Doppler), canais, mobilidade, regulação BR-2026, simulador de eventos (DES).
- `protocol/endpoint.py` máquina de estados do protocolo (BASE/DATA/NEGOCIANDO/AGUARDA_COMMIT/VALIDANDO/RECUPERACAO).
  É o modelo do que o núcleo C99 deve fazer. `protocol/modes.py` tem a tabela de modos.
- `formal/checker.py` verificação de estados explícita (propriedades P1 a P3, ablações) e cadeia de Markov.
- `scenarios/` bancada (B2–B11), campo (F1–F6), mobilidade (M1–M7). `baselines/` modelos de malha de terceiros.
- `analysis/` estatística, telemetria JSONL, relatório. `run_suite.py` orquestra tudo.

## Regras do projeto
- Idioma: documentos e respostas em português do Brasil; código, API e nomes de símbolos em inglês.
- **Nome:** ler "AdaptLoRa" como "Légua" (docs/00). "AdapLoRa" (um só "t") é outro trabalho (ICNP 2020).
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
