# tradings — Bot BTC 5m Polymarket (versión autocontenida)

Bot para los mercados **BTC Up/Down de 5 minutos** de Polymarket, basado en la
estrategia "momentum into close" del repo viral
[Novals83/5min-btc-polymarket](https://github.com/Novals83/5min-btc-polymarket),
pero **autocontenido** (el original depende de un motor de ejecución privado no
publicado) y con el filtro de impulso de BTC realmente implementado.

> ⚠️ **Lee [ANALISIS.md](ANALISIS.md) antes de usar esto.** No hay ninguna
> evidencia de que esta estrategia sea rentable. El modo por defecto es
> simulación (sin dinero real) — úsalo durante semanas antes de plantearte
> siquiera el modo live.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Uso — modo simulación (por defecto, sin dinero)

```bash
# Sesión de 1h con el perfil conservador
python -m btc5m --profile conservative

# Perfil que replica el comportamiento real del repo original (sin filtro de impulso)
python -m btc5m --profile novals83_original

# Sesión más larga
python -m btc5m --profile conservative --session-minutes 480
```

Cada operación simulada se registra en `runtime/trades.jsonl` con señal,
precio de entrada (ask real del libro), motivo de salida y P&L según la
resolución real del mercado. El P&L diario acumulado y el contador de
operaciones viven en `runtime/risk_state.json`.

## Estrategia

Por cada ventana de 5 minutos:

1. **Ventana de entrada**: entre 150s y 60s antes del cierre.
2. **Señal**: el ask de un lado (UP/DOWN) ≥ 0.70 **y** BTC ya se movió ≥ $70
   en esa misma dirección dentro del intervalo (precio de Kraken en tiempo real).
3. **Guardas**: spread ≤ 0.03, liquidez mínima en el ask, límites diarios de
   pérdida y de número de operaciones.
4. **Gestión**: stop-loss (25–30% desde la entrada) contra el bid; salida por
   resolución (`hold`, por defecto) o venta 20s antes del cierre
   (`before_close`, como el repo original).

Perfiles configurables en [`config/profiles.yaml`](config/profiles.yaml).

## Modo live (dinero real) — bajo tu responsabilidad

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
  strategy.py   # señal: umbral + filtro de impulso + guardas de liquidez
  runner.py     # bucle principal, stop-loss, salidas, registro
  executor.py   # ejecución paper (default) y live (py-clob-client)
  risk.py       # límites diarios persistentes
config/profiles.yaml
ANALISIS.md     # revisión completa del repo viral y de la estrategia
```
