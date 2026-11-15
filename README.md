# Légua

**Acordo de modo, validação e rollback para enlaces LoRa ponto a ponto.**
*Mode agreement, validation and rollback for peer-to-peer LoRa links.*

> Nome de trabalho; antes "AdaptLoRa". "Légua" é a medida de distância do sertão.
> "LoRa" é marca da Semtech e aparece aqui só como descrição técnica do uso.

## O que é

Biblioteca LoRa P2P (sem LoRaWAN) para rádios Semtech SX12xx, com adaptação negociada de modo
(PROPOSE / VOTE / COMMIT), troca em instante combinado, janela de validação, âncora persistida em memória
não volátil e rollback. Ciente da regulação brasileira (perfil BR-2026, em verificação).

## Status

Pré-alfa, em pesquisa. Hoje o repositório contém a **suíte de simulação** (`simsuite/`) que
valida o protocolo e o plano de testes. O núcleo em C99, o driver SX1262 e a camada de porte ainda
não foram escritos.

> **Aviso regulatório.** A conformidade é do produto homologado, não desta biblioteca. As regras do perfil BR-2026
> vêm de fonte secundária e ainda precisam ser confirmadas com um organismo de certificação (OCD).

## Como rodar a simulação

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=. python3 -m pytest -q simsuite/tests          # 11 testes
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick  # ~40 s; gera simsuite/results/
```

Detalhes em [`simsuite/README.md`](simsuite/README.md) e em [`docs/`](docs/).

## Licença e contribuição

Código sob Apache-2.0 (ver `LICENSE`). Contribuições com assinatura DCO: veja `CONTRIBUTING.md`.
Falhas de segurança: veja `SECURITY.md`.

## Como citar

Veja `CITATION.cff`.
