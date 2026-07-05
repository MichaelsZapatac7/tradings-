# Análisis: bot "BTC 5 minutos" de Polymarket (tweets + repo Novals83)

Revisión hecha el 2026-07-05 de los dos posts de X mencionados y del repositorio
[Novals83/5min-btc-polymarket](https://github.com/Novals83/5min-btc-polymarket).

## 1. Los posts de X

Los dos enlaces (@karlarboledas y @igus_ai) no son accesibles sin sesión de X
(la API pública los bloquea), pero por las búsquedas asociadas corresponden a la
ola viral de posts sobre bots de trading en los mercados "BTC Up/Down 5 minutos"
de Polymarket, y el segundo apunta al repo de Novals83 (~460 estrellas en GitHub).
Es contenido promocional: **ninguna de estas fuentes publica un historial de
resultados verificable** (P&L auditado, dirección de wallet con historial, etc.).

## 2. Qué hace realmente el repositorio

El mercado: cada 5 minutos Polymarket abre un mercado binario "¿BTC cerrará por
encima o por debajo del precio de apertura de esta ventana?". Las acciones UP y
DOWN cotizan entre $0 y $1 y la ganadora se liquida a $1.

La estrategia declarada en su README ("momentum into close"):
1. Entrar ~2 minutos antes del cierre.
2. Confirmar que BTC ya se movió ~$70–$100 en el intervalo.
3. Entrar al lado favorecido por el flujo (skew), con stop-loss del 25–30%,
   y salir 20 segundos antes del cierre.

## 3. Hallazgos de la revisión del código (importantes)

1. **El repo NO puede operar por sí solo.** La colocación real de órdenes se
   delega a `pm-hl-conservative-plus-repo/src/live/pm_live_trade_runner.py`,
   un repositorio **privado del autor que no está publicado**. El repo viral
   es solo el envoltorio (señal, reintentos, informes). Quien lo clona no
   puede ejecutarlo sin construir ese motor él mismo.

2. **El código no implementa la estrategia que anuncia.** El runner real
   (`test_btc_5m_session_exit_sl.py`) solo comprueba una cosa: que el *ask*
   de un lado sea ≥ 0.70. El filtro de impulso de "$70–$100 de movimiento de
   BTC" que promociona el README **no existe en el código**. En la práctica
   el bot original compra al favorito caro, sin confirmar momentum.

3. **Asume Binance como fuente de precio**, que está geobloqueada (HTTP 451)
   desde muchos servidores/países. Verificado desde este entorno.

4. Sin backtest, sin historial, sin métricas. El propio README dice:
   *"educational/operational infrastructure, not financial advice"* y no hace
   ninguna afirmación de rentabilidad.

## 4. ¿La estrategia tiene esperanza matemática positiva?

Esto es lo esencial. Comprar el favorito a 0.70–0.95 cerca del cierre gana solo
si el precio del mercado **subestima** la probabilidad real de que el movimiento
se mantenga. En un mercado con arbitrajistas profesionales (los hay: hay bots
que explotan el retraso del oráculo con datos de exchange en tiempo real), el
precio a 2 minutos del cierre ya incorpora esa información. Sin una ventaja
informacional, el valor esperado por operación es ≈ 0 **antes** de costes, y
negativo después de:

- **Spread**: compras al ask y (si sales antes del cierre) vendes al bid.
  Con spreads de 1–3 centavos y precios de ~0.75, son ~1.5–4% por vuelta.
- **Stop-loss sobre binarios**: un stop del 25% en un activo que oscila
  violentamente en los últimos 2 minutos se dispara con ruido constantemente;
  convierte operaciones que habrían ganado en pérdidas realizadas.
- **Selección adversa**: tus órdenes FAK se llenan más fácilmente justo cuando
  el precio está a punto de girarse en tu contra.

Con $500 y el perfil "conservador" (~$5–8 por operación, 12 operaciones/día),
un drift negativo de 2–3% por operación significa perder ~$1.5–3/día de forma
esperada. No es una ruina inmediata, pero la dirección esperada es hacia abajo.

## 5. Qué se integró en este repositorio

Una versión **autocontenida y honesta** del bot (paquete `btc5m/`):

- No depende del repo privado: ejecución directa contra el CLOB de Polymarket
  con `py-clob-client` (modo live) — el eslabón que al repo viral le falta.
- **Implementa el filtro de impulso que el original solo anunciaba**
  (movimiento de BTC ≥ $70 en la dirección de la entrada, vía Kraken, que
  no está geobloqueada y sirve velas en tiempo real).
- **Modo simulación (paper) por defecto**: registra entradas al ask real,
  stop-loss contra el bid real y liquidación según la resolución real del
  mercado. Permite medir la estrategia semanas enteras **con $0 en riesgo**.
- Límites de riesgo aplicados en código (pérdida máxima diaria, máximo de
  operaciones/día), persistentes entre ejecuciones.
- Perfil `novals83_original` que replica el comportamiento real del repo viral
  (solo umbral 0.70, sin filtro de impulso), para comparar ambos en simulación.

## 6. Respuesta a tu pregunta de los $500

**No.** No puedo prometerte que este bot (ni ningún otro) te haga ganar dinero,
y no debes pagarle a nadie que te lo prometa — esa promesa es exactamente el
modelo de negocio de quienes venden estos bots por Twitter/Whop. Los hechos:

- El repo viral no publica ni un solo resultado verificable y ni siquiera
  incluye el código necesario para operar.
- La estrategia no tiene una ventaja demostrada; los costes de fricción son
  reales y juegan en contra.
- Los mercados de 5 minutos son de suma cero **entre traders**: para que tú
  ganes, otro (a menudo un bot profesional con datos más rápidos) tiene que
  perder contra ti.

Lo responsable con tus $500: **no los deposites todavía.** Corre el modo
simulación 2–4 semanas (`python -m btc5m --profile conservative`), compara
perfiles, y mira el P&L acumulado en `runtime/trades.jsonl`. Si la simulación
pierde dinero (lo más probable), habrás ahorrado $500. Si sorprende al alza de
forma consistente, empieza con $50–100, nunca con una cifra que duela perder.
