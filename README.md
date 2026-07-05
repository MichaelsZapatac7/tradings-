# tradings — Bot BTC 5m Polymarket

Bot propio para los mercados **BTC Up/Down de 5 minutos** de Polymarket, con
dos estrategias:

- **`fair_value` (la nuestra, por defecto)**: modelo de volatilidad que calcula
  la probabilidad justa de UP/DOWN y solo entra cuando el mercado está mal
  valorado por un margen mínimo. Diseño completo en
  [ESTRATEGIA.md](ESTRATEGIA.md), incluido el plan por fases para validarla
  con datos antes de arriesgar dinero.
- **`threshold`**: la estrategia "momentum into close" del repo viral
  [Novals83/5min-btc-polymarket](https://github.com/Novals83/5min-btc-polymarket)
  (analizado en [ANALISIS.md](ANALISIS.md)), implementada correctamente y
  autocontenida, para comparar contra la nuestra.

> ⚠️ Ninguna estrategia tiene rentabilidad garantizada. El modo por defecto es
> simulación (sin dinero real); el flujo de trabajo es: grabar datos →
> evaluar ventaja → paper trading → (solo si todo es positivo) live con
> importes mínimos.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Flujo de trabajo

### 1. Grabar datos de calibración ($0 en riesgo)

```bash
python -m btc5m.record --hours 24    # dejar corriendo días (288 intervalos/día)
```

### 2. Evaluar si hay ventaja

```bash
python -m btc5m.evaluate
```

Imprime la calibración del modelo (Brier score vs. mercado) y el PnL
hipotético por nivel de `min_edge`. **Si el modelo no bate al mercado, no hay
ventaja y no se deposita dinero.**

### 3. Paper trading (por defecto, sin dinero)

```bash
# Nuestra estrategia
python -m btc5m --profile fair_value --session-minutes 480

# Variante exigente (menos entradas, más ventaja mínima)
python -m btc5m --profile fair_value_strict

# Comparar contra el estilo del repo viral
python -m btc5m --profile conservative
python -m btc5m --profile novals83_original
```

Cada operación simulada se registra en `runtime/trades.jsonl` con señal,
precio de entrada (ask real del libro), motivo de salida y P&L según la
resolución real del mercado. El P&L diario acumulado y el contador de
operaciones viven en `runtime/risk_state.json`.

Cada operación simulada queda en `runtime/trades.jsonl`; los límites diarios
en `runtime/risk_state.json`. Perfiles en
[`config/profiles.yaml`](config/profiles.yaml).

### 4. Modo live (dinero real) — solo tras validar, bajo tu responsabilidad

Requiere `pip install py-clob-client`, una wallet de Polygon con USDC en
Polymarket y un `.env` basado en [`.env.example`](.env.example):

```bash
set -a && source .env && set +a
python -m btc5m --profile conservative --stake-usd 2 --execute
```

Empieza con importes mínimos ($1–2). El código de ejecución live está escrito
pero **no ha podido probarse con órdenes reales** desde este entorno; valida
primero una orden pequeña manualmente.

## Estructura

```
btc5m/
  data.py       # Gamma API, libro de órdenes CLOB, precio BTC (Kraken)
  model.py      # modelo de probabilidad (fair value del binario)
  strategy.py   # señales: fair_value (nuestra) y threshold (repo viral)
  runner.py     # bucle principal, stop-loss, salidas, registro
  executor.py   # ejecución paper (default) y live (py-clob-client)
  risk.py       # límites diarios persistentes
  record.py     # grabador de datos de calibración (python -m btc5m.record)
  evaluate.py   # Brier score y PnL hipotético (python -m btc5m.evaluate)
config/profiles.yaml
ESTRATEGIA.md   # diseño de nuestra estrategia y plan de validación por fases
ANALISIS.md     # revisión del repo viral y de sus promesas
```
