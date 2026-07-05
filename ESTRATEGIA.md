# Nuestra estrategia: fair value (valor justo) en binarios de 5 minutos

## La idea

Cada mercado "BTC Up/Down 5m" es una **opción binaria a punto de vencer**: la
acción ganadora paga $1. Para este tipo de instrumento existe un precio justo
matemático. Si BTC lleva una ventaja (`lead`) de +$40 sobre el precio de
apertura del intervalo y quedan `s` segundos, la probabilidad de que esa
ventaja sobreviva depende solo de la volatilidad reciente:

```
P(UP) = Φ( lead / (σ_1m · √(s/60)) )
```

donde `σ_1m` es la desviación típica de los movimientos de BTC por minuto
(estimada en vivo con las últimas ~30 velas de Kraken) y Φ la CDF normal.

**Regla de entrada**: comprar un lado solo cuando
`probabilidad_modelo − ask_mercado ≥ min_edge` (6–10 puntos), con guardas de
spread, liquidez y precio máximo 0.97. Mantener hasta la resolución (no se
paga spread de salida; la ganadora liquida a $1).

## Por qué esto sí es una estrategia y lo del repo viral no

| | Repo viral (Novals83) | Nuestra `fair_value` |
|---|---|---|
| Señal | "el ask ya está ≥ 0.70" (compra al favorito caro) | desajuste entre probabilidad modelada y precio |
| Dirección | solo sigue a la multitud | simétrica: compra lo que esté barato |
| Ventaja esperada | ninguna demostrada; paga el spread siempre | positiva **si** el modelo calibra mejor que el mercado |
| Falsable | no (no mide nada) | sí: Brier score + PnL hipotético en `evaluate.py` |

El punto crítico y honesto: la estrategia gana **solo si** nuestro modelo de
probabilidad es mejor que el precio del mercado en algunos momentos (p. ej.
cuando el retail sobrepaga el favorito tras un movimiento brusco, o cuando el
libro tarda segundos en ajustarse al precio spot). Eso no se puede asumir —
**se mide**, y este repo incluye la maquinaria para medirlo antes de arriesgar
un dólar.

## Plan por fases (con criterios de abandono)

**Fase 1 — Recolección (1–2 semanas, $0 en riesgo).**
`python -m btc5m.record --hours 24` corriendo en un servidor/PC 24/7.
Graba cada intervalo: probabilidad del modelo, libros de órdenes y resolución
real. Objetivo: 1.000+ intervalos resueltos (hay 288/día).

**Fase 2 — Evaluación (`python -m btc5m.evaluate`).**
- Si el Brier score del modelo **no** mejora al del mercado → no hay ventaja
  → **no depositar dinero. Fin.** (Habremos perdido $0.)
- Si mejora, mirar el PnL hipotético por nivel de `min_edge` y elegir el nivel
  con mejor ratio ganancia/número de operaciones.

**Fase 3 — Paper trading en vivo (1–2 semanas).**
`python -m btc5m --profile fair_value` — misma lógica pero simulando fills
contra el libro real. Confirma que la ventaja sobrevive al timing real.

**Fase 4 — Live con dinero mínimo.**
Solo si las fases 2 y 3 son positivas: $50–100 de banca, `--stake-usd 1-2`,
límite de pérdida diaria activo. Subir tamaño solo tras 2+ semanas en verde.

**Criterios de parada permanentes**: pérdida diaria máxima (en código),
2 semanas consecutivas en rojo en live → volver a fase 2, y nunca operar
tamaño que no puedas perder entero.

## Qué necesito de ti (por fase)

- **Fases 1–3: nada.** Todo usa APIs públicas sin claves. Solo una máquina
  encendida (un VPS de $5/mes o tu PC).
- **Fase 4 (live)**: cuenta de Polymarket con USDC en Polygon y la clave
  privada/credenciales en un `.env` local (nunca en GitHub, nunca me la
  compartas por chat en texto plano). Ten en cuenta que el acceso a Polymarket
  depende de tu jurisdicción — verifica que es legal donde vives.

## Mejoras futuras con potencial real de ventaja

1. **Feed más rápido**: websocket de Kraken/Coinbase (ticks de ~100ms en vez
   de velas) — la ventaja de este juego es en gran parte de latencia.
2. **Drift/momentum en el modelo**: añadir un término de deriva a la Browniana
   cuando hay momentum fuerte (calibrable con los datos de fase 1).
3. **Vol intradía**: σ estimada con EWMA en vez de ventana fija.
4. **Maker en vez de taker**: cotizar dentro del spread con órdenes GTC para
   cobrar el spread en vez de pagarlo (más complejo, requiere gestión de
   inventario).
