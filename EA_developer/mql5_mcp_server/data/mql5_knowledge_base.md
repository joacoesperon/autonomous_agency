# MQL5 Knowledge Base — Coder Agent Reference

> Este documento es la referencia absoluta para generar código MQL5 correcto.
> REGLA FUNDAMENTAL: Todo el código generado debe seguir MQL5 estrictamente.
> Cualquier función, variable o patrón de MQL4 está PROHIBIDO.

---

## BLOQUE 1 — Lista Negra MQL4 (PROHIBICIONES ABSOLUTAS)

Las siguientes construcciones son MQL4 y NO EXISTEN en MQL5.
Si las usas, el código NO compilará. No hay excepciones.

### Variables globales eliminadas en MQL5

| ❌ MQL4 PROHIBIDO | ✅ MQL5 CORRECTO |
|---|---|
| `Bid` | `SymbolInfoDouble(_Symbol, SYMBOL_BID)` |
| `Ask` | `SymbolInfoDouble(_Symbol, SYMBOL_ASK)` |
| `Point` | `_Point` |
| `Digits` | `_Digits` |
| `Bars` | `Bars(_Symbol, _Period)` |

### Funciones de cuenta eliminadas

| ❌ MQL4 PROHIBIDO | ✅ MQL5 CORRECTO |
|---|---|
| `AccountBalance()` | `AccountInfoDouble(ACCOUNT_BALANCE)` |
| `AccountEquity()` | `AccountInfoDouble(ACCOUNT_EQUITY)` |
| `AccountFreeMargin()` | `AccountInfoDouble(ACCOUNT_MARGIN_FREE)` |
| `AccountLeverage()` | `AccountInfoInteger(ACCOUNT_LEVERAGE)` |
| `AccountProfit()` | `AccountInfoDouble(ACCOUNT_PROFIT)` |

### Funciones de órdenes eliminadas

| ❌ MQL4 PROHIBIDO | ✅ MQL5 CORRECTO |
|---|---|
| `OrderSend(...)` (10 params) | `CTrade::Buy()` / `CTrade::Sell()` |
| `OrderSelect(i, SELECT_BY_POS)` | `PositionGetSymbol(i)` |
| `OrdersTotal()` | `PositionsTotal()` |
| `OrderClose(...)` | `CTrade::PositionClose(symbol)` |
| `OrderLots()` | `PositionGetDouble(POSITION_VOLUME)` |
| `OrderProfit()` | `PositionGetDouble(POSITION_PROFIT)` |
| `OrderSymbol()` | `PositionGetString(POSITION_SYMBOL)` |
| `OrderType()` | `PositionGetInteger(POSITION_TYPE)` |
| `OrderMagicNumber()` | `PositionGetInteger(POSITION_MAGIC)` |
| `OrderOpenPrice()` | `PositionGetDouble(POSITION_PRICE_OPEN)` |
| `OrderStopLoss()` | `PositionGetDouble(POSITION_SL)` |
| `OrderTakeProfit()` | `PositionGetDouble(POSITION_TP)` |
| `OrderTicket()` | `PositionGetInteger(POSITION_TICKET)` |
| `OrderComment()` | `PositionGetString(POSITION_COMMENT)` |

### Funciones de mercado eliminadas

| ❌ MQL4 PROHIBIDO | ✅ MQL5 CORRECTO |
|---|---|
| `MarketInfo(sym, MODE_BID)` | `SymbolInfoDouble(sym, SYMBOL_BID)` |
| `MarketInfo(sym, MODE_ASK)` | `SymbolInfoDouble(sym, SYMBOL_ASK)` |
| `MarketInfo(sym, MODE_SPREAD)` | `SymbolInfoInteger(sym, SYMBOL_SPREAD)` |
| `MarketInfo(sym, MODE_POINT)` | `SymbolInfoDouble(sym, SYMBOL_POINT)` |
| `MarketInfo(sym, MODE_DIGITS)` | `SymbolInfoInteger(sym, SYMBOL_DIGITS)` |
| `MarketInfo(sym, MODE_LOTSIZE)` | `SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE)` |
| `MarketInfo(sym, MODE_MINLOT)` | `SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN)` |
| `MarketInfo(sym, MODE_MAXLOT)` | `SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX)` |
| `MarketInfo(sym, MODE_LOTSTEP)` | `SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP)` |
| `RefreshRates()` | (no existe ni es necesario en MQL5) |

### Funciones de indicadores — sintaxis completamente diferente

En MQL4 los indicadores devuelven un valor directamente.
En MQL5 primero creas un **handle** en `OnInit()`, luego copias los datos con `CopyBuffer()`.

| ❌ MQL4 PROHIBIDO | ✅ MQL5 CORRECTO |
|---|---|
| `iMA(NULL, 0, 50, 0, MODE_EMA, PRICE_CLOSE, 0)` | `handle = iMA(...)` + `CopyBuffer(handle, 0, 0, 3, buffer)` |
| `iRSI(NULL, 0, 14, PRICE_CLOSE, 0)` | `handle = iRSI(...)` + `CopyBuffer(handle, 0, 0, 3, buffer)` |
| `iMACD(NULL, 0, 12, 26, 9, PRICE_CLOSE, MODE_MAIN, 0)` | `handle = iMACD(...)` + `CopyBuffer(handle, 0, ...)` |
| `iBands(NULL, 0, 20, 2, 0, PRICE_CLOSE, MODE_UPPER, 0)` | `handle = iBands(...)` + `CopyBuffer(handle, 0, ...)` |
| `iATR(NULL, 0, 14, 0)` | `handle = iATR(...)` + `CopyBuffer(handle, 0, 0, 3, buffer)` |
| `iStochastic(...)` | `handle = iStochastic(...)` + `CopyBuffer(...)` |
| `iCCI(...)` | `handle = iCCI(...)` + `CopyBuffer(...)` |

---

## BLOQUE 2 — Plantilla Base EA Swing Trading H4

Esta es la estructura base que SIEMPRE debe usarse como punto de partida.
Contiene todos los includes, estructuras y funciones obligatorias correctas.

```cpp
//+------------------------------------------------------------------+
//|                                                   EA_Template.mq5 |
//|                                     Sistema Trading Algoritmico   |
//+------------------------------------------------------------------+
#property copyright "Sistema Trading Algoritmico"
#property version   "1.00"
#property strict

// Includes obligatorios para trading en MQL5
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Parámetros externos (configurables por el usuario)
input group "=== Gestión de Riesgo ==="
input double RiesgoPorc       = 1.0;    // Riesgo por operación (% del balance)
input double LoteMinimo       = 0.01;   // Lote mínimo si el cálculo es menor

input group "=== Filtros ==="
input int    SpreadMaximo     = 20;     // Spread máximo permitido (puntos)
input bool   SoloLunesJueves  = true;   // Operar solo Lun-Jue

input group "=== Identificación ==="
input int    MagicNumber      = 123456; // Número mágico único del EA

//--- Objetos globales
CTrade         trade;          // Objeto para ejecutar operaciones
CPositionInfo  posInfo;        // Objeto para leer posiciones
CAccountInfo   accountInfo;    // Objeto para leer cuenta

//--- Handles de indicadores (se crean en OnInit, se usan en OnTick)
int handleEMA_rapida = INVALID_HANDLE;
int handleEMA_lenta  = INVALID_HANDLE;

//--- Variables de control
datetime ultimaVela = 0; // Timestamp de la última vela procesada

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Configurar el objeto de trading
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_FOK);

   // Crear handles de indicadores
   // IMPORTANTE: siempre usar _Symbol y _Period o los valores explícitos
   handleEMA_rapida = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);
   handleEMA_lenta  = iMA(_Symbol, PERIOD_H4, 200, 0, MODE_EMA, PRICE_CLOSE);

   // Validar que los handles se crearon correctamente
   if(handleEMA_rapida == INVALID_HANDLE || handleEMA_lenta == INVALID_HANDLE)
     {
      Print("ERROR: No se pudieron crear los handles de indicadores");
      return(INIT_FAILED);
     }

   Print("EA iniciado correctamente en ", _Symbol);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // OBLIGATORIO: liberar todos los handles al cerrar el EA
   if(handleEMA_rapida != INVALID_HANDLE) IndicatorRelease(handleEMA_rapida);
   if(handleEMA_lenta  != INVALID_HANDLE) IndicatorRelease(handleEMA_lenta);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Procesar solo en apertura de nueva vela H4 (no en cada tick)
   datetime tiempoVelaActual = iTime(_Symbol, PERIOD_H4, 0);
   if(tiempoVelaActual == ultimaVela) return;
   ultimaVela = tiempoVelaActual;

   // Verificar filtros básicos antes de cualquier lógica
   if(!FiltrosBasicosOK()) return;

   // Leer valores de indicadores
   double emaRapida[], emaLenta[];
   ArraySetAsSeries(emaRapida, true);
   ArraySetAsSeries(emaLenta, true);

   if(CopyBuffer(handleEMA_rapida, 0, 0, 3, emaRapida) < 3) return;
   if(CopyBuffer(handleEMA_lenta,  0, 0, 3, emaLenta)  < 3) return;

   // Verificar si hay posición abierta del EA en este símbolo
   bool hayPosicion = HayPosicionAbierta();

   // --- LÓGICA DE ENTRADA ---
   if(!hayPosicion)
     {
      // Señal de compra: EMA rápida cruza EMA lenta hacia arriba
      bool senalCompra  = emaRapida[1] > emaLenta[1] && emaRapida[2] <= emaLenta[2];
      // Señal de venta: EMA rápida cruza EMA lenta hacia abajo
      bool senalVenta   = emaRapida[1] < emaLenta[1] && emaRapida[2] >= emaLenta[2];

      if(senalCompra)  AbrirCompra();
      if(senalVenta)   AbrirVenta();
     }
  }

//+------------------------------------------------------------------+
//| Verificar filtros básicos                                         |
//+------------------------------------------------------------------+
bool FiltrosBasicosOK()
  {
   // Filtro de spread
   long spreadActual = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadActual > SpreadMaximo)
     {
      Print("Spread demasiado alto: ", spreadActual, " > ", SpreadMaximo);
      return false;
     }

   // Filtro de días (solo Lunes a Jueves)
   if(SoloLunesJueves)
     {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      // dt.day_of_week: 0=Dom, 1=Lun, 2=Mar, 3=Mié, 4=Jue, 5=Vie, 6=Sáb
      if(dt.day_of_week == 0 || dt.day_of_week == 5 || dt.day_of_week == 6)
         return false;
     }

   return true;
  }

//+------------------------------------------------------------------+
//| Verificar si hay posición abierta del EA en este símbolo          |
//+------------------------------------------------------------------+
bool HayPosicionAbierta()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(posInfo.SelectByIndex(i))
        {
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
            return true;
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Calcular tamaño de lote basado en % de riesgo                    |
//+------------------------------------------------------------------+
double CalcularLote(double slPips)
  {
   double balance     = AccountInfoDouble(ACCOUNT_BALANCE);
   double riesgoUSD   = balance * RiesgoPorc / 100.0;
   double valorPip    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double punto       = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(slPips <= 0 || valorPip <= 0) return LoteMinimo;

   // Convertir pips a puntos (para pares de 5 dígitos, 1 pip = 10 puntos)
   double slPuntos = slPips * 10 * punto;
   double lote     = riesgoUSD / (slPuntos / tickSize * valorPip);

   // Normalizar al step de lotes permitido
   double lotStep  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lote = MathFloor(lote / lotStep) * lotStep;
   lote = MathMax(lote, lotMin);
   lote = MathMin(lote, lotMax);
   lote = MathMax(lote, LoteMinimo);

   return NormalizeDouble(lote, 2);
  }

//+------------------------------------------------------------------+
//| Abrir operación de compra                                         |
//+------------------------------------------------------------------+
void AbrirCompra()
  {
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl     = ask - 500 * _Point; // ejemplo: 50 pips de SL
   double tp     = ask + 1500 * _Point; // ejemplo: 150 pips de TP

   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lote = CalcularLote(50); // 50 pips de SL

   if(trade.Buy(lote, _Symbol, ask, sl, tp, "EA_Compra"))
      Print("Compra abierta: lote=", lote, " sl=", sl, " tp=", tp);
   else
      Print("Error al abrir compra: ", trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Abrir operación de venta                                          |
//+------------------------------------------------------------------+
void AbrirVenta()
  {
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl     = bid + 500 * _Point; // ejemplo: 50 pips de SL
   double tp     = bid - 1500 * _Point; // ejemplo: 150 pips de TP

   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lote = CalcularLote(50);

   if(trade.Sell(lote, _Symbol, bid, sl, tp, "EA_Venta"))
      Print("Venta abierta: lote=", lote, " sl=", sl, " tp=", tp);
   else
      Print("Error al abrir venta: ", trade.ResultRetcodeDescription());
  }
//+------------------------------------------------------------------+
```

---

## BLOQUE 3 — 30 Patrones de Código MQL5 para Swing Trading H4/D1

Cada patrón es un fragmento listo para ensamblar dentro de la plantilla base.

---

### Patrón 01 — Detectar nueva vela en cualquier timeframe

```cpp
// Variables globales necesarias:
datetime ultimaVela_H4 = 0;
datetime ultimaVela_D1 = 0;

// En OnTick():
datetime tiempoH4 = iTime(_Symbol, PERIOD_H4, 0);
if(tiempoH4 == ultimaVela_H4) return; // No es vela nueva, salir
ultimaVela_H4 = tiempoH4;
// A partir de aquí se ejecuta solo una vez por vela H4
```

---

### Patrón 02 — Crear handle de EMA y leer su valor

```cpp
// En variables globales:
int handleEMA = INVALID_HANDLE;

// En OnInit():
handleEMA = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);
if(handleEMA == INVALID_HANDLE)
  {
   Print("Error creando EMA handle: ", GetLastError());
   return(INIT_FAILED);
  }

// En OnTick() (después de confirmar nueva vela):
double ema[];
ArraySetAsSeries(ema, true); // índice 0 = vela más reciente
if(CopyBuffer(handleEMA, 0, 0, 3, ema) < 3)
  {
   Print("Error copiando buffer EMA");
   return;
  }
// ema[0] = vela actual (puede estar incompleta)
// ema[1] = vela cerrada anterior  ← usar esta para señales
// ema[2] = dos velas atrás
```

---

### Patrón 03 — Crear handle de RSI y leer su valor

```cpp
// En variables globales:
int handleRSI = INVALID_HANDLE;

// En OnInit():
handleRSI = iRSI(_Symbol, PERIOD_H4, 14, PRICE_CLOSE);
if(handleRSI == INVALID_HANDLE) return(INIT_FAILED);

// En OnTick():
double rsi[];
ArraySetAsSeries(rsi, true);
if(CopyBuffer(handleRSI, 0, 0, 3, rsi) < 3) return;
double rsiValor = rsi[1]; // valor de la última vela cerrada
```

---

### Patrón 04 — Crear handle de MACD y leer líneas

```cpp
// En variables globales:
int handleMACD = INVALID_HANDLE;

// En OnInit():
// iMACD parámetros: símbolo, timeframe, fast, slow, signal, applied_price
handleMACD = iMACD(_Symbol, PERIOD_H4, 12, 26, 9, PRICE_CLOSE);
if(handleMACD == INVALID_HANDLE) return(INIT_FAILED);

// En OnTick():
double macdMain[], macdSignal[];
ArraySetAsSeries(macdMain, true);
ArraySetAsSeries(macdSignal, true);
// Buffer 0 = línea MACD (main), Buffer 1 = línea Signal
if(CopyBuffer(handleMACD, 0, 0, 3, macdMain)   < 3) return;
if(CopyBuffer(handleMACD, 1, 0, 3, macdSignal) < 3) return;

double macdValor   = macdMain[1];
double signalValor = macdSignal[1];
bool   cruce_alcista = macdMain[1] > macdSignal[1] && macdMain[2] <= macdSignal[2];
bool   cruce_bajista = macdMain[1] < macdSignal[1] && macdMain[2] >= macdSignal[2];
```

---

### Patrón 05 — Crear handle de Bollinger Bands y leer bandas

```cpp
// En variables globales:
int handleBB = INVALID_HANDLE;

// En OnInit():
// iBands parámetros: símbolo, tf, período, desviación, shift, applied_price
handleBB = iBands(_Symbol, PERIOD_H4, 20, 0, 2.0, PRICE_CLOSE);
if(handleBB == INVALID_HANDLE) return(INIT_FAILED);

// En OnTick():
double bbUpper[], bbMiddle[], bbLower[];
ArraySetAsSeries(bbUpper,  true);
ArraySetAsSeries(bbMiddle, true);
ArraySetAsSeries(bbLower,  true);
// Buffer 0 = banda media, 1 = banda superior, 2 = banda inferior
if(CopyBuffer(handleBB, 0, 0, 3, bbMiddle) < 3) return;
if(CopyBuffer(handleBB, 1, 0, 3, bbUpper)  < 3) return;
if(CopyBuffer(handleBB, 2, 0, 3, bbLower)  < 3) return;
```

---

### Patrón 06 — Crear handle de ATR y leer su valor

```cpp
// En variables globales:
int handleATR = INVALID_HANDLE;

// En OnInit():
handleATR = iATR(_Symbol, PERIOD_H4, 14);
if(handleATR == INVALID_HANDLE) return(INIT_FAILED);

// En OnTick():
double atr[];
ArraySetAsSeries(atr, true);
if(CopyBuffer(handleATR, 0, 0, 3, atr) < 3) return;
double atrValor = atr[1]; // ATR de la última vela cerrada
// Uso típico: SL = precio ± (atrValor * multiplicador)
```

---

### Patrón 07 — Detectar cruce de dos EMAs (Golden/Death Cross)

```cpp
// Requiere: Patrón 02 aplicado dos veces (EMA rápida y EMA lenta)
// ema_r[] = EMA rápida,  ema_l[] = EMA lenta

// Cruce alcista (golden cross): rápida cruza lenta hacia arriba
bool crucAlcista = ema_r[1] > ema_l[1] && ema_r[2] <= ema_l[2];

// Cruce bajista (death cross): rápida cruza lenta hacia abajo
bool crucBajista = ema_r[1] < ema_l[1] && ema_r[2] >= ema_l[2];

// Tendencia alcista activa (sin cruce, solo dirección)
bool tendAlcista = ema_r[1] > ema_l[1];
bool tendBajista = ema_r[1] < ema_l[1];
```

---

### Patrón 08 — Detectar cruce del precio sobre una EMA

```cpp
// Requiere: handle de EMA creado (Patrón 02)
// close[] = precios de cierre de velas anteriores

double close[];
ArraySetAsSeries(close, true);
if(CopyClose(_Symbol, PERIOD_H4, 0, 3, close) < 3) return;

// Precio cruza EMA hacia arriba
bool precioCruzaArribaEMA = close[1] > ema[1] && close[2] <= ema[2];

// Precio cruza EMA hacia abajo
bool precioCruzaAbajoEMA  = close[1] < ema[1] && close[2] >= ema[2];
```

---

### Patrón 09 — Abrir orden BUY con SL y TP en pips

```cpp
// Requiere: objeto CTrade configurado con MagicNumber
// slPips y tpPips son los pips de stop loss y take profit

void AbrirBuy(double slPips, double tpPips, double lote)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // Para pares de 5 dígitos: 1 pip = 10 * _Point
   double sl  = NormalizeDouble(ask - slPips * 10 * _Point, _Digits);
   double tp  = NormalizeDouble(ask + tpPips * 10 * _Point, _Digits);

   if(!trade.Buy(lote, _Symbol, ask, sl, tp, "EA_Buy"))
      Print("Error Buy: ", trade.ResultRetcodeDescription());
  }
```

---

### Patrón 10 — Abrir orden SELL con SL y TP en pips

```cpp
void AbrirSell(double slPips, double tpPips, double lote)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl  = NormalizeDouble(bid + slPips * 10 * _Point, _Digits);
   double tp  = NormalizeDouble(bid - tpPips * 10 * _Point, _Digits);

   if(!trade.Sell(lote, _Symbol, bid, sl, tp, "EA_Sell"))
      Print("Error Sell: ", trade.ResultRetcodeDescription());
  }
```

---

### Patrón 11 — Verificar que no hay posición abierta del EA

```cpp
// Requiere: CPositionInfo posInfo, input int MagicNumber
bool HayPosicionAbierta()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
            return true;
     }
   return false;
  }
```

---

### Patrón 12 — Cerrar posición abierta del EA por símbolo

```cpp
void CerrarPosicion()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(posInfo.SelectByIndex(i))
        {
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
           {
            if(!trade.PositionClose(posInfo.Ticket()))
               Print("Error cerrando posición: ", trade.ResultRetcodeDescription());
           }
        }
     }
  }
```

---

### Patrón 13 — Trailing Stop

```cpp
// Mueve el SL a medida que el precio avanza a favor
// trailPips: distancia del trailing stop en pips
void AplicarTrailingStop(double trailPips)
  {
   double trail = trailPips * 10 * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol() != _Symbol || posInfo.Magic() != MagicNumber) continue;

      double slActual   = posInfo.StopLoss();
      double precioOpen = posInfo.PriceOpen();

      if(posInfo.PositionType() == POSITION_TYPE_BUY)
        {
         double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double nuevoSL = NormalizeDouble(bid - trail, _Digits);
         if(nuevoSL > slActual + _Point) // Solo mover SL hacia arriba
            trade.PositionModify(posInfo.Ticket(), nuevoSL, posInfo.TakeProfit());
        }
      else if(posInfo.PositionType() == POSITION_TYPE_SELL)
        {
         double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double nuevoSL = NormalizeDouble(ask + trail, _Digits);
         if(nuevoSL < slActual - _Point || slActual == 0) // Solo mover SL hacia abajo
            trade.PositionModify(posInfo.Ticket(), nuevoSL, posInfo.TakeProfit());
        }
     }
  }
```

---

### Patrón 14 — Breakeven automático

```cpp
// Mueve el SL al precio de entrada cuando el precio avanza X pips
// activacionPips: pips de beneficio para activar breakeven
void AplicarBreakeven(double activacionPips)
  {
   double activacion = activacionPips * 10 * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Symbol() != _Symbol || posInfo.Magic() != MagicNumber) continue;

      double precioOpen = posInfo.PriceOpen();
      double slActual   = posInfo.StopLoss();

      if(posInfo.PositionType() == POSITION_TYPE_BUY)
        {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(bid >= precioOpen + activacion && slActual < precioOpen)
            trade.PositionModify(posInfo.Ticket(),
                                 NormalizeDouble(precioOpen + _Point, _Digits),
                                 posInfo.TakeProfit());
        }
      else if(posInfo.PositionType() == POSITION_TYPE_SELL)
        {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(ask <= precioOpen - activacion && (slActual > precioOpen || slActual == 0))
            trade.PositionModify(posInfo.Ticket(),
                                 NormalizeDouble(precioOpen - _Point, _Digits),
                                 posInfo.TakeProfit());
        }
     }
  }
```

---

### Patrón 15 — Calcular lote por porcentaje de riesgo

```cpp
// balance * riesgoPorc% = riesgo en USD
// slPips: stop loss en pips
double CalcularLotePorRiesgo(double slPips, double riesgoPorc)
  {
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riesgoUSD = balance * riesgoPorc / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double punto     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(slPips <= 0 || tickValue <= 0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

   double slPuntos = slPips * 10 * punto;
   double lote     = riesgoUSD / (slPuntos / tickSize * tickValue);

   double step  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lote = MathFloor(lote / step) * step;
   lote = MathMax(minL, MathMin(maxL, lote));

   return NormalizeDouble(lote, 2);
  }
```

---

### Patrón 16 — Filtro de spread máximo

```cpp
// Retorna false si el spread es mayor al máximo permitido
bool SpreadPermitido(int spreadMaxPips)
  {
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   // spread viene en puntos (para EURUSD 5 dígitos, 10 puntos = 1 pip)
   return (spread <= spreadMaxPips * 10);
  }
```

---

### Patrón 17 — Filtro de sesión por horario (Hora del servidor)

```cpp
// Operar solo dentro de una ventana horaria
// horaInicio y horaFin en hora del servidor MT5
bool DentroDeHorario(int horaInicio, int horaFin)
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hora = dt.hour;
   if(horaInicio < horaFin)
      return (hora >= horaInicio && hora < horaFin);
   else // cruza medianoche
      return (hora >= horaInicio || hora < horaFin);
  }

// Ejemplo de uso (sesión Londres + NY: 8:00 a 17:00):
// if(!DentroDeHorario(8, 17)) return;
```

---

### Patrón 18 — Filtro de día de la semana

```cpp
// Retorna true si hoy es un día permitido para operar
bool DiaPermitido()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   // day_of_week: 0=Dom, 1=Lun, 2=Mar, 3=Mié, 4=Jue, 5=Vie, 6=Sáb
   // Evitar Viernes tarde y fin de semana
   if(dt.day_of_week == 0 || dt.day_of_week == 6) return false;
   if(dt.day_of_week == 5 && dt.hour >= 18) return false;
   return true;
  }
```

---

### Patrón 19 — Leer precio OHLC de velas anteriores

```cpp
// Leer los últimos N precios de cierre
double close[];
ArraySetAsSeries(close, true);
CopyClose(_Symbol, PERIOD_H4, 0, 10, close);
// close[0] = vela actual (incompleta)
// close[1] = última vela cerrada ← usar para señales
// close[9] = 9 velas atrás

// Leer máximos y mínimos
double high[], low[];
ArraySetAsSeries(high, true);
ArraySetAsSeries(low, true);
CopyHigh(_Symbol, PERIOD_H4, 0, 10, high);
CopyLow(_Symbol,  PERIOD_H4, 0, 10, low);

// Leer precios de apertura
double open[];
ArraySetAsSeries(open, true);
CopyOpen(_Symbol, PERIOD_H4, 0, 10, open);
```

---

### Patrón 20 — Encontrar máximo y mínimo de N velas anteriores

```cpp
// Máximo de las últimas N velas (excluyendo la vela actual)
double MaximoN(int n)
  {
   double high[];
   ArraySetAsSeries(high, true);
   if(CopyHigh(_Symbol, PERIOD_H4, 1, n, high) < n) return 0;
   return high[ArrayMaximum(high, 0, n)];
  }

// Mínimo de las últimas N velas
double MinimoN(int n)
  {
   double low[];
   ArraySetAsSeries(low, true);
   if(CopyLow(_Symbol, PERIOD_H4, 1, n, low) < n) return 0;
   return low[ArrayMinimum(low, 0, n)];
  }
```

---

### Patrón 21 — SL dinámico basado en ATR

```cpp
// Requiere: handle de ATR y valor atrValor calculado (Patrón 06)
// multiplicador: ej. 1.5, 2.0, 2.5

double SlDinamicoBuy(double atrValor, double multiplicador)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   return NormalizeDouble(ask - atrValor * multiplicador, _Digits);
  }

double TpDinamicoRRBuy(double slPrecio, double ratioRR)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double riesgo = ask - slPrecio;
   return NormalizeDouble(ask + riesgo * ratioRR, _Digits);
  }
```

---

### Patrón 22 — Filtro de tendencia con EMA larga en D1

```cpp
// Confirmar que la operación va a favor de la tendencia diaria
// Requiere: handle de EMA en D1

int handleEMA_D1 = INVALID_HANDLE;

// En OnInit():
handleEMA_D1 = iMA(_Symbol, PERIOD_D1, 200, 0, MODE_EMA, PRICE_CLOSE);
if(handleEMA_D1 == INVALID_HANDLE) return(INIT_FAILED);

// En OnTick():
double emaD1[];
ArraySetAsSeries(emaD1, true);
if(CopyBuffer(handleEMA_D1, 0, 0, 2, emaD1) < 2) return;

double closeActual = iClose(_Symbol, PERIOD_D1, 1);
bool tendAlcistaD1 = closeActual > emaD1[1]; // precio sobre EMA200 diaria
bool tendBajistaD1 = closeActual < emaD1[1];

// Usar como filtro: solo comprar si tendAlcistaD1, solo vender si tendBajistaD1
```

---

### Patrón 23 — Detectar Higher High y Lower Low (estructura de mercado)

```cpp
// Higher High: el máximo actual es mayor al máximo N velas atrás
// Lower Low:   el mínimo actual es menor al mínimo N velas atrás
bool EsHigherHigh(int nVelas)
  {
   double high[];
   ArraySetAsSeries(high, true);
   if(CopyHigh(_Symbol, PERIOD_H4, 1, nVelas + 1, high) < nVelas + 1) return false;
   // high[0] = última vela cerrada, high[1..n] = anteriores
   double maxAnterior = high[ArrayMaximum(high, 1, nVelas)];
   return high[0] > maxAnterior;
  }

bool EsLowerLow(int nVelas)
  {
   double low[];
   ArraySetAsSeries(low, true);
   if(CopyLow(_Symbol, PERIOD_H4, 1, nVelas + 1, low) < nVelas + 1) return false;
   double minAnterior = low[ArrayMinimum(low, 1, nVelas)];
   return low[0] < minAnterior;
  }
```

---

### Patrón 24 — Niveles de soporte y resistencia por swing points

```cpp
// Detectar swing high (máximo local): vela i tiene el high mayor a sus vecinas
bool EsSwingHigh(int i, int rango)
  {
   double high[];
   ArraySetAsSeries(high, true);
   if(CopyHigh(_Symbol, PERIOD_H4, 0, i + rango + 1, high) < i + rango + 1) return false;
   for(int j = 1; j <= rango; j++)
      if(high[i] <= high[i - j] || high[i] <= high[i + j]) return false;
   return true;
  }

bool EsSwingLow(int i, int rango)
  {
   double low[];
   ArraySetAsSeries(low, true);
   if(CopyLow(_Symbol, PERIOD_H4, 0, i + rango + 1, low) < i + rango + 1) return false;
   for(int j = 1; j <= rango; j++)
      if(low[i] >= low[i - j] || low[i] >= low[i + j]) return false;
   return true;
  }
```

---

### Patrón 25 — Gestión de múltiples posiciones del mismo EA

```cpp
// Contar cuántas posiciones tiene abierto el EA
int ContarPosiciones()
  {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(posInfo.SelectByIndex(i))
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
            count++;
   return count;
  }

// Cerrar todas las posiciones del EA
void CerrarTodasLasPosiciones()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
            trade.PositionClose(posInfo.Ticket());
     }
  }
```

---

### Patrón 26 — Profit/Loss flotante de posiciones abiertas

```cpp
// Obtener el profit flotante total del EA
double ObtenerProfitFlotante()
  {
   double totalProfit = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Symbol() == _Symbol && posInfo.Magic() == MagicNumber)
            totalProfit += posInfo.Profit() + posInfo.Swap();
     }
   return totalProfit;
  }
```

---

### Patrón 27 — Divergencia RSI básica

```cpp
// Divergencia alcista: precio hace Lower Low, RSI hace Higher Low
bool DivergenciaAlcista(double rsi[], double low[])
  {
   // Comparar las dos últimas velas cerradas (índice 1 y 2)
   bool precioLowerLow = low[1] < low[2];  // precio bajó
   bool rsiHigherLow   = rsi[1] > rsi[2];  // RSI subió
   return precioLowerLow && rsiHigherLow;
  }

// Divergencia bajista: precio hace Higher High, RSI hace Lower High
bool DivergenciaBajista(double rsi[], double high[])
  {
   bool precioHigherHigh = high[1] > high[2]; // precio subió
   bool rsiLowerHigh     = rsi[1] < rsi[2];   // RSI bajó
   return precioHigherHigh && rsiLowerHigh;
  }
```

---

### Patrón 28 — Manejo de errores con GetLastError()

```cpp
// Siempre verificar errores después de operaciones críticas
void VerificarError(string operacion)
  {
   int error = GetLastError();
   if(error != 0)
     {
      Print("ERROR en ", operacion, ": código ", error,
            " - ", trade.ResultRetcodeDescription());
      ResetLastError();
     }
  }

// Uso:
// trade.Buy(...);
// VerificarError("Buy EURUSD");
```

---

### Patrón 29 — Normalización correcta de precios y lotes

```cpp
// SIEMPRE normalizar antes de enviar órdenes
double NormalizarPrecio(double precio)
  {
   return NormalizeDouble(precio, _Digits);
  }

double NormalizarLote(double lote)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lote = MathFloor(lote / step) * step;
   return NormalizeDouble(MathMax(minL, MathMin(maxL, lote)), 2);
  }
```

---

### Patrón 30 — Validación completa en OnInit()

```cpp
// Checklist de validaciones que todo EA debe hacer al iniciarse
int OnInit()
  {
   // 1. Verificar que es el símbolo correcto (opcional)
   // if(_Symbol != "EURUSD") { Print("EA solo para EURUSD"); return(INIT_FAILED); }

   // 2. Configurar CTrade
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   trade.LogLevel(LOG_LEVEL_ERRORS); // Solo loguear errores

   // 3. Crear y validar todos los handles
   handleEMA_rapida = iMA(_Symbol, PERIOD_H4, 50,  0, MODE_EMA, PRICE_CLOSE);
   handleEMA_lenta  = iMA(_Symbol, PERIOD_H4, 200, 0, MODE_EMA, PRICE_CLOSE);
   handleRSI        = iRSI(_Symbol, PERIOD_H4, 14, PRICE_CLOSE);
   handleATR        = iATR(_Symbol, PERIOD_H4, 14);

   if(handleEMA_rapida == INVALID_HANDLE ||
      handleEMA_lenta  == INVALID_HANDLE ||
      handleRSI        == INVALID_HANDLE ||
      handleATR        == INVALID_HANDLE)
     {
      Print("ERROR CRÍTICO: Fallo al crear handles de indicadores. Error: ", GetLastError());
      return(INIT_FAILED);
     }

   // 4. Verificar que el símbolo tiene datos
   if(Bars(_Symbol, PERIOD_H4) < 300)
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " H4");
      return(INIT_PARAMETERS_INCORRECT);
     }

   Print("EA inicializado correctamente. Magic: ", MagicNumber,
         " | Símbolo: ", _Symbol, " | Build: ", TerminalInfoInteger(TERMINAL_BUILD));
   return(INIT_SUCCEEDED);
  }
```

---

## BLOQUE 4 — Errores de Compilación Más Comunes

### Error 031 — Variable no definida

```
Mensaje:  'Ask' - undeclared identifier
Causa:    Ask/Bid son variables globales en MQL4, no existen en MQL5
Fix:      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
          double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
```

### Error 029 — Parámetros incorrectos en función

```
Mensaje:  'OrderSend' - wrong parameters count
Causa:    OrderSend de MQL4 tiene firma diferente a MQL5
Fix:      Usar CTrade::Buy() o CTrade::Sell() en su lugar
```

### Error 263 — Función obsoleta

```
Mensaje:  'RefreshRates' - deprecated function
Causa:    RefreshRates() no existe en MQL5
Fix:      Eliminar la llamada. En MQL5 los datos se actualizan automáticamente
```

### Error 130 — Stops inválidos

```
Mensaje:  Trade error 130: Invalid stops
Causa:    SL o TP demasiado cercanos al precio actual (menor al stop level)
Fix:      Verificar mínimo: SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)
          Agregar ese mínimo al cálculo de SL/TP
```

### Error de compilación — Conversión de tipos

```
Mensaje:  implicit conversion from 'number' to 'string'
Causa:    Mezclar tipos en Print() o concatenación
Fix:      Usar (string) para castear: Print("Valor: " + (string)miDouble);
          O usar coma en lugar de +: Print("Valor: ", miDouble);
```

### Error 4756 — Handle inválido

```
Mensaje:  en runtime: invalid handle (CopyBuffer devuelve -1)
Causa:    El handle del indicador es INVALID_HANDLE
Fix:      Siempre validar handle != INVALID_HANDLE en OnInit()
          Verificar que los parámetros del indicador son válidos
```

### Error — ArraySetAsSeries no aplicado

```
Síntoma:  Los valores del buffer están al revés (índice 0 es el más antiguo)
Causa:    Falta ArraySetAsSeries(buffer, true) antes de CopyBuffer
Fix:      Siempre llamar ArraySetAsSeries(miArray, true) antes de CopyBuffer
          Esto hace que índice 0 = vela más reciente (comportamiento esperado)
```

### Error 4109 — Trading no permitido

```
Mensaje:  en runtime: trade not allowed
Causa:    El EA no tiene permiso para operar (AutoTrading desactivado)
Fix:      Verificar que el botón de AutoTrading está activo en MT5
          O verificar: AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)
```

### Error — ORDER_FILLING_FOK rechazado

```
Mensaje:  error 10030: unsupported filling mode
Causa:    El broker no soporta ORDER_FILLING_FOK
Fix:      Cambiar a ORDER_FILLING_IOC o ORDER_FILLING_RETURN
          trade.SetTypeFilling(ORDER_FILLING_IOC);
```

### Error — Normalización de precio incorrecta

```
Síntoma:  Las órdenes se rechazan con error de precio inválido
Causa:    El precio enviado tiene más decimales de los permitidos
Fix:      Siempre usar NormalizeDouble(precio, _Digits) antes de enviar
```

---

## BLOQUE 5 — Reglas Absolutas para el Coder Agent

Estas reglas no tienen excepciones. Violar cualquiera produce código que no funciona.

1. **NUNCA** usar `Bid`, `Ask`, `Point`, `Digits`, `Bars` como variables directas
2. **NUNCA** usar `OrderSend()` con la firma de 10 parámetros de MQL4
3. **NUNCA** usar funciones de indicadores sin handle (`iMA(NULL, 0, ...)`)
4. **SIEMPRE** crear handles en `OnInit()` y liberar en `OnDeinit()`
5. **SIEMPRE** usar `ArraySetAsSeries(array, true)` antes de `CopyBuffer()`
6. **SIEMPRE** validar que `CopyBuffer()` devuelve el número esperado de elementos
7. **SIEMPRE** usar `NormalizeDouble(precio, _Digits)` antes de enviar órdenes
8. **SIEMPRE** incluir `#include <Trade\Trade.mqh>` para usar `CTrade`
9. **SIEMPRE** configurar `trade.SetExpertMagicNumber()` en `OnInit()`
10. **NUNCA** procesar lógica en cada tick — usar el patrón de detección de nueva vela
11. **SIEMPRE** liberar handles con `IndicatorRelease()` en `OnDeinit()`
12. **NUNCA** usar `Sleep()` dentro de `OnTick()` — congela el terminal
13. **SIEMPRE** verificar que el handle != `INVALID_HANDLE` antes de usar `CopyBuffer()`
14. **NUNCA** acceder a `close[0]` para señales — usar `close[1]` (vela cerrada)
15. **SIEMPRE** usar `_Symbol` y `_Period` o valores explícitos, nunca `NULL` o `0`
