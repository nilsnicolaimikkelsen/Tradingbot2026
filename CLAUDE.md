# Trading Bot – Prosjektplan

## Mål
Boten skal **ikke** maksimere avkastning per dag. Målet er stabil, positiv avkastning over en lengre periode, med kontrollert risiko og begrenset drawdown. Kapitalbevaring og robusthet prioriteres over høy avkastning.

---

## 1. Overordnet arkitektur

Systemet deles i uavhengige lag. Samme strategikode skal kunne kjøre i backtest, paper trading og live – kun execution-laget byttes ut mellom modiene. Dette unngår "funker i backtest, feiler live"-problemer.

```
┌─────────────────┐
│   Data-lag        │  Henter og lagrer markedsdata (pris, volum, historikk)
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Strategi/signal   │  Ren logikk: data inn → signal (kjøp/selg/hold) ut
│   -lag             │  Ingen ordre-kall her
└────────┬─────────┘
         ▼
┌─────────────────┐
│   Risiko-lag       │  Gatekeeper: sjekker posisjonsstørrelse, maks
│                    │  eksponering, daglig tapsgrense. Kan overstyre
│                    │  og blokkere strategien uansett hva den vil.
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Execution-lag     │  Eneste sted som snakker med børs/megler-API.
│                    │  Byttes ut avhengig av modus (backtest/paper/live).
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Overvåking/logging │  Egen prosess. Varsler ved feil, store drawdowns,
│                    │  eller at boten har stoppet (Telegram/e-post).
└─────────────────┘
```

**Kritiske tekniske krav:**
- **State persistence:** posisjoner og åpne ordre lagres i databasen, slik at restart ikke dupliserer noe
- **Idempotente ordre:** bruk client-order-ID slik at samme ordre aldri sendes to ganger ved retry/feil
- **Kill switch:** en uavhengig watchdog-prosess som kan stoppe execution-laget umiddelbart, separat fra hovedloopen

---

## 2. Strategi

Ingen enkelt statisk strategi – markeder skifter mellom trend, range og ulike volatilitetsregimer, og en strategi optimalisert for ett regime svekkes når regimet skifter ("alpha decay").

**Løsning:**
- Kjør 2–4 ukorrelerte delstrategier samtidig, f.eks.:
  - Trendfølging
  - Mean-reversion
  - Volatilitetsbasert modell
- En enkel **regimedetektor** (basert på volatilitet/trendstyrke) styrer *vektingen* mellom delstrategiene – ikke logikken inni dem
- Når én delstrategi går dårlig i sitt regime, kompenserer ofte en annen

**Justering av strategien over tid:**
- Boten skal **ikke** justere egne parametre kontinuerlig i sanntid basert på egne siste resultater – stor overfitting-risiko, vanskelig å kontrollere
- I stedet: periodisk, offline **walk-forward reoptimalisering** (f.eks. månedlig)
  1. Reoptimaliser parametre på ny historisk data
  2. Test ut-of-sample
  3. Godkjennes manuelt før det rulles ut til live-boten
- Kjernelogikk/regler holdes stabile. Det som justeres er terskler, vekting mellom delstrategier, og posisjonsstørrelse

---

## 3. Risikostyring

Dette er viktigere enn selve strategivalget for målet om stabil, langsiktig pluss.

- Fast, konservativ posisjonsstørrelse – volatilitetsjustert, ikke fast kronebeløp
- Maks tap per dag og per uke, med automatisk stopp ved brudd
- Kill switch som stopper all handel umiddelbart ved behov
- Diversifisering på tvers av instrumenter, ikke bare på tvers av strategier
- Realistisk modellering av gebyrer og slippage i all backtesting (dreper ofte strategier som ser lønnsomme ut på papiret)

---

## 4. Teknisk stack

| Komponent | Valg | Kommentar |
|---|---|---|
| Språk | Python | Dominerende økosystem, ikke behov for lav-latency-språk |
| Exchange/broker-API | `ccxt` (krypto) / `ib_insync` (Interactive Brokers) / Alpaca SDK (aksjer) | Velges ut fra hvilket marked |
| Backtesting | [Nautilus Trader](https://nautilustrader.io) | Event-drevet, samme kode for backtest og live. Alternativ: `vectorbt` eller `backtrader` for enklere oppsett |
| Database | PostgreSQL / TimescaleDB | Handelsdata og botens tilstand |
| Orkestrering | Langkjørende `asyncio`-prosess | Ikke cron-jobber som starter/stopper |
| Containerisering | Docker | Reproduserbar deploy |
| Hosting | Liten, stabil VPS | Uptime kritisk – ikke egen PC |
| Secrets | Miljøvariabler / vault | Aldri API-nøkler i kode |

**Kostnad:** de fleste komponentene er gratis/open source. Reell kostnad er VPS (ca. 50–150 kr/mnd), eventuelt sanntids tick-data, og handelsgebyrer (som løper uavhengig av bot). Handelsgebyrer relativt til handelsfrekvens er det som faktisk påvirker lønnsomheten mest – ikke verktøykostnadene.

---

## 5. Utviklingsprosess

1. **Backtest** med walk-forward-validering (ikke bare én lang sammenhengende periode – unngå curve-fitting)
2. **Paper trading** i minst noen uker/måneder på testnett/sandbox
3. **Start med minimal reell kapital**, skaler opp gradvis basert på faktiske resultater
4. Løpende logging og overvåking av metrikker: drawdown, Sharpe-ratio, treffrate

---

## 6. Oppstart – første oppgave til Claude Code (tomt repo)

Utgangspunkt: et tomt GitHub-repo, ingen filer. Dette er det Claude Code bør gjøre **før** noen strategi- eller handelslogikk skrives.

**Rekkefølge ved oppstart:**

1. **Opprett `CLAUDE.md`** i rot av repoet, med hele arkitekturen fra dette dokumentet (lag-strukturen, strategi-tilnærming, risikoprinsipper). Dette blir prosjektets "spec" som Claude Code leser automatisk ved starten av hver ny økt, slik at kontekst ikke går tapt mellom sesjoner.
2. **Sett opp grunnleggende prosjektstruktur** som speiler lag-arkitekturen:
   ```
   /data          – henting/lagring av markedsdata
   /strategy      – signallogikk, én fil per delstrategi
   /risk          – posisjonsgrenser, kill switch
   /execution     – ordre-håndtering (backtest/paper/live-varianter)
   /monitoring    – logging, varsling
   /tests         – tester per lag
   ```
3. **Initialiser Python-prosjekt**: `pyproject.toml` eller `requirements.txt`, virtuelt miljø, avhengigheter (ccxt/ib_insync, Nautilus Trader eller vectorbt, asyncpg/psycopg for databasen, pytest)
4. **`.gitignore`**: sørg for at `.env`, `__pycache__`, virtuelle miljøer og credentials aldri kan committes ved et uhell
5. **`.env.example`**: mal for miljøvariabler (API-nøkler, database-URL) uten faktiske verdier – de faktiske hemmelighetene settes lokalt/i secrets-vault, aldri i repoet
6. **Grunnleggende `README.md`**: kort beskrivelse, hvordan sette opp lokalt, hvordan kjøre tester
7. **Docker-skjelett**: `Dockerfile` + `docker-compose.yml` med tjenester for boten og databasen, selv om innholdet fylles ut senere
8. **Tom test-oppsett**: `pytest` konfigurert og kjørbar, selv om den kun tester en placeholder til å begynne med – bekreft at CI-løpet fungerer før ekte logikk legges til
9. **Første commit**: alt over committes samlet som "Initial project scaffolding" før noe strategi- eller execution-kode skrives

**Første prompt du kan bruke i Claude Code (etter at repoet er valgt):**

> Sett opp prosjektstruktur for en trading-bot i Python basert på arkitekturen i CLAUDE.md (data/strategi/risiko/execution/monitoring-lag). Opprett mappestruktur, pyproject.toml med relevante avhengigheter, .gitignore, .env.example, README.md, og et enkelt Docker-oppsett. Ikke skriv strategi- eller handelslogikk ennå – kun skjelettet. Bruk Plan-modus og vis meg forslaget før du oppretter filene.

Bruk **Plan**-modus for denne første oppgaven, slik at du kan godkjenne strukturen før noe opprettes.

---

## 7. Rekkefølge for videre implementasjon

Etter oppstart bygges lag for lag, ikke alt på én gang:

1. Data-lag (henting + lagring av historisk og sanntidsdata)
2. Strategi/signal-lag (start med én enkel strategi, f.eks. trendfølging, for å få hele pipelinen til å virke ende-til-ende)
3. Risiko-lag (posisjonsgrenser, tapsgrenser, kill switch)
4. Backtesting-oppsett med walk-forward-validering
5. Execution-lag – **kun mot testnett/sandbox-API i starten**
6. Legg til flere delstrategier + regimedetektor for vekting
7. Overvåking/logging + varsling (Telegram/e-post)
8. Paper trading over tid, evaluering, ev. justering
9. Gradvis overgang til reell (liten) kapital

**Sikkerhetsregler underveis:**
- Ingen ordre-kall mot ekte handelskonto før execution-laget er grundig gjennomgått manuelt
- Bruk **Plan**-modus (ikke Accept edits) i Claude Code for alt som gjelder execution-laget og API-nøkkel-håndtering
- Skriv tester for hvert lag før man går videre til neste
