# Tradingbot2026

Lagdelt trading-bot (data / strategi / risiko / execution / monitoring). Se [`CLAUDE.md`](./CLAUDE.md) for full arkitektur og prosjektplan.

## Lokalt oppsett

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fyll inn egne verdier
```

## Kjøre tester

```bash
pytest
```

## Kjøre med Docker

```bash
docker compose up
```
