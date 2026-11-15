# Légua (antes "AdaptLoRa")

Biblioteca LoRa P2P (sem LoRaWAN) para rádios Semtech SX12xx, com adaptação negociada de modo
(PROPOSE/VOTE/COMMIT), troca em instante combinado, janela de validação, âncora em NVM e rollback.
Referência de hardware: Heltec WiFi LoRa 32 V4 (ESP32-S3 + SX1262, até 28 dBm), faixa 915 MHz.

Leia `docs/` antes de mudar protocolo, perfil regulatório ou plano de testes.

## Estado atual
- Existe só a suíte de simulação em `simsuite/` (Python). Ela é a referência executável do protocolo.
- **Não existem ainda:** núcleo C99, driver SX1262, camada de porte, exemplos Arduino/ESP-IDF.
- Próximo passo: Fase 0 do `docs/03-parecer-multidisciplinar-e-plano-de-implementacao.md` (especificação do
  pacote, orçamento dos 24 bytes, interface de rádio e de porte, simulador mínimo).

## Comandos
```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=. python3 -m pytest -q simsuite/tests                    # 11 testes, ~5 s
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick           # ~40 s, gera simsuite/results/
PYTHONPATH=. python3 -m simsuite.run_suite --escala full --procs 8  # horas; só na máquina local
```

## Mapa do código (`simsuite/`)
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
