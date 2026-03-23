//+------------------------------------------------------------------+
//|                                              IchimokuRSIBreakout.mq5 |
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

input group "=== Parámetros Ichimoku ==="
input int    Tenkan_Period      = 9;      // Período para la línea Tenkan-Sen de Ichimoku.
input int    Kijun_Period       = 26;     // Período para la línea Kijun-Sen de Ichimoku.
input int    Senkou_Span_B_Period = 52;   // Período para la línea Senkou Span B de Ichimoku.

input group "=== Parámetros RSI ==="
input int    RSI_Period         = 14;     // Período para el indicador RSI.

input group "=== Parámetros ATR ==="
input int    ATR_Period         = 14;     // Período para el indicador ATR usado en el cálculo de SL/TP.
input double ATR_Multiplier_SL  = 1.5;    // Multiplicador del ATR para calcular el Stop Loss.

input group "=== Filtros ==="
input int    MaxSpreadPips      = 20;     // Máximo spread permitido en pips para abrir una operación.

input group "=== Identificación ==="
input int    MagicNumber        = 100001; // Número mágico para identificar las operaciones del EA.

//--- Objetos globales
CTrade         trade;          // Objeto para ejecutar operaciones
CPositionInfo  posInfo;        // Objeto para leer posiciones
CAccountInfo   accountInfo;    // Objeto para leer cuenta

//--- Handles de indicadores (se crean en OnInit, se usan en OnTick)
int handleIchimoku = INVALID_HANDLE;
int handleRSI      = INVALID_HANDLE;
int handleATR      = INVALID_HANDLE;

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
   trade.SetTypeFilling(ORDER_FILLING_FOK); // Puede ser ORDER_FILLING_IOC si FOK no es soportado
   trade.LogLevel(LOG_LEVEL_ERRORS); // Solo loguear errores

   // Crear handles de indicadores
   // Ichimoku: símbolo, timeframe, Tenkan, Kijun, Senkou B
   handleIchimoku = iIchimoku(_Symbol, PERIOD_H4, Tenkan_Period, Kijun_Period, Senkou_Span_B_Period);
   handleRSI      = iRSI(_Symbol, PERIOD_H4, RSI_Period, PRICE_CLOSE);
   handleATR      = iATR(_Symbol, PERIOD_H4, ATR_Period);

   // Validar que los handles se crearon correctamente
   if(handleIchimoku == INVALID_HANDLE || handleRSI == INVALID_HANDLE || handleATR == INVALID_HANDLE)
     {
      Print("ERROR CRÍTICO: No se pudieron crear los handles de indicadores. Error: ", GetLastError());
      return(INIT_FAILED);
     }

   // Verificar que el símbolo tiene datos suficientes para Ichimoku (al menos Senkou_Span_B_Period + 26 velas para Chikou Span)
   if(Bars(_Symbol, PERIOD_H4) < Senkou_Span_B_Period + 26 + 1) // +1 para la vela actual
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " H4. Se requieren al menos ", Senkou_Span_B_Period + 26 + 1, " velas.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   Print("EA IchimokuRSIBreakout iniciado correctamente en ", _Symbol, " H4. Magic: ", MagicNumber);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // OBLIGATORIO: liberar todos los handles al cerrar el EA
   if(handleIchimoku != INVALID_HANDLE) IndicatorRelease(handleIchimoku);
   if(handleRSI      != INVALID_HANDLE) IndicatorRelease(handleRSI);
   if(handleATR      != INVALID_HANDLE) IndicatorRelease(handleATR);
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

   // --- Leer valores de indicadores y precios ---
   double tenkan[], kijun[], senkouA[], senkouB[], chikou[];
   double rsiBuffer[];
   double atrBuffer[];
   double closePrices[];

   // Configurar arrays para que el índice 0 sea la vela más reciente
   ArraySetAsSeries(tenkan, true);
   ArraySetAsSeries(kijun, true);
   ArraySetAsSeries(senkouA, true);
   ArraySetAsSeries(senkouB, true);
   ArraySetAsSeries(chikou, true);
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(atrBuffer, true);
   ArraySetAsSeries(closePrices, true);

   // Copiar datos de los indicadores y precios
   // Se necesitan al menos 27 velas para Ichimoku Chikou Span (Close[26])
   if(CopyBuffer(handleIchimoku, 0, 0, 27, tenkan)  < 27 || // Tenkan-Sen
      CopyBuffer(handleIchimoku, 1, 0, 27, kijun)   < 27 || // Kijun-Sen
      CopyBuffer(handleIchimoku, 2, 0, 27, senkouA) < 27 || // Senkou Span A
      CopyBuffer(handleIchimoku, 3, 0, 27, senkouB) < 27 || // Senkou Span B
      CopyBuffer(handleIchimoku, 4, 0, 27, chikou)  < 27 || // Chikou Span
      CopyBuffer(handleRSI, 0, 0, 1, rsiBuffer)     < 1  || // RSI actual
      CopyBuffer(handleATR, 0, 0, 2, atrBuffer)     < 2  || // ATR de la vela anterior
      CopyClose(_Symbol, PERIOD_H4, 0, 27, closePrices) < 27) // Precios de cierre
     {
      Print("Error copiando buffers de indicadores o precios. Asegúrese de tener suficientes datos históricos.");
      return;
     }

   // Valores de la vela actual (índice 0) y vela anterior (índice 1)
   double currentClose = closePrices[0];
   double currentRSI   = rsiBuffer[0];
   double prevATR      = atrBuffer[1]; // ATR de la última vela cerrada

   // Verificar si hay posición abierta del EA en este símbolo
   bool hayPosicion = HayPosicionAbierta();

   // --- LÓGICA DE ENTRADA ---
   if(!hayPosicion)
     {
      // Señal de compra:
      // 1. Precio de cierre actual > Senkou Span A y Senkou Span B (ruptura de la nube alcista)
      // 2. Tenkan-Sen > Kijun-Sen (alineación alcista)
      // 3. Chikou Span actual > Precio de cierre de hace 26 velas (confirmación de momentum alcista)
      // 4. RSI no sobrecomprado (< 70)
      bool senalCompra = currentClose > senkouA[0] &&
                         currentClose > senkouB[0] &&
                         tenkan[0] > kijun[0] &&
                         chikou[0] > closePrices[26] &&
                         currentRSI < 70;

      // Señal de venta:
      // 1. Precio de cierre actual < Senkou Span A y Senkou Span B (ruptura de la nube bajista)
      // 2. Tenkan-Sen < Kijun-Sen (alineación bajista)
      // 3. Chikou Span actual < Precio de cierre de hace 26 velas (confirmación de momentum bajista)
      // 4. RSI no sobrevendido (> 30)
      bool senalVenta = currentClose < senkouA[0] &&
                        currentClose < senkouB[0] &&
                        tenkan[0] < kijun[0] &&
                        chikou[0] < closePrices[26] &&
                        currentRSI > 30;

      if(senalCompra)  AbrirCompra(prevATR);
      if(senalVenta)   AbrirVenta(prevATR);
     }
  }

//+------------------------------------------------------------------+
//| Verificar filtros básicos                                         |
//+------------------------------------------------------------------+
bool FiltrosBasicosOK()
  {
   // Filtro de spread
   long spreadActual = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadActual > MaxSpreadPips * 10) // MaxSpreadPips está en pips, spreadActual en puntos
     {
      Print("Spread demasiado alto: ", spreadActual, " puntos > ", MaxSpreadPips, " pips.");
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
double CalcularLotePorRiesgo(double slPips, double riesgoPorc)
  {
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riesgoUSD = balance * riesgoPorc / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double punto     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(slPips <= 0 || tickValue <= 0) return LoteMinimo;

   // Convertir pips a puntos (para pares de 5 dígitos, 1 pip = 10 puntos)
   double slPuntos = slPips * 10 * punto;
   double lote     = riesgoUSD / (slPuntos / tickSize * tickValue);

   // Normalizar al step de lotes permitido
   double lotStep  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lote = MathFloor(lote / lotStep) * lotStep;
   lote = MathMax(lote, lotMin);
   lote = MathMin(lote, lotMax);
   lote = MathMax(lote, LoteMinimo); // Asegurar que no sea menor al lote mínimo global

   return NormalizeDouble(lote, 2);
  }

//+------------------------------------------------------------------+
//| Abrir operación de compra                                         |
//+------------------------------------------------------------------+
void AbrirCompra(double atrValor)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Calcular SL en pips basado en ATR
   double slPips = atrValor / _Point * ATR_Multiplier_SL;
   // Calcular TP en pips (2 veces el SL)
   double tpPips = slPips * 2.0;

   // Calcular los precios de SL y TP
   double sl = NormalizeDouble(ask - slPips * 10 * _Point, _Digits);
   double tp = NormalizeDouble(ask + tpPips * 10 * _Point, _Digits);

   // Asegurar que SL y TP estén por encima del StopLevel mínimo del broker
   int stopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(MathAbs(ask - sl) < stopLevel * _Point) sl = ask - (stopLevel + 10) * _Point; // Ajustar si es muy cercano
   if(MathAbs(tp - ask) < stopLevel * _Point) tp = ask + (stopLevel + 10) * _Point;

   // Calcular el lote
   double lote = CalcularLotePorRiesgo(slPips, RiesgoPorc);

   if(lote < LoteMinimo)
     {
      Print("Lote calculado (", lote, ") es menor que LoteMinimo (", LoteMinimo, "). No se abre la operación.");
      return;
     }

   if(trade.Buy(lote, _Symbol, ask, sl, tp, "IchimokuRSI_Buy"))
      Print("Compra abierta: lote=", lote, " sl=", sl, " tp=", tp, " (SL Pips: ", slPips, ", TP Pips: ", tpPips, ")");
   else
      Print("Error al abrir compra: ", trade.ResultRetcodeDescription(), " (Error code: ", GetLastError(), ")");
  }

//+------------------------------------------------------------------+
//| Abrir operación de venta                                          |
//+------------------------------------------------------------------+
void AbrirVenta(double atrValor)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Calcular SL en pips basado en ATR
   double slPips = atrValor / _Point * ATR_Multiplier_SL;
   // Calcular TP en pips (2 veces el SL)
   double tpPips = slPips * 2.0;

   // Calcular los precios de SL y TP
   double sl = NormalizeDouble(bid + slPips * 10 * _Point, _Digits);
   double tp = NormalizeDouble(bid - tpPips * 10 * _Point, _Digits);

   // Asegurar que SL y TP estén por encima del StopLevel mínimo del broker
   int stopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(MathAbs(sl - bid) < stopLevel * _Point) sl = bid + (stopLevel + 10) * _Point; // Ajustar si es muy cercano
   if(MathAbs(bid - tp) < stopLevel * _Point) tp = bid - (stopLevel + 10) * _Point;

   // Calcular el lote
   double lote = CalcularLotePorRiesgo(slPips, RiesgoPorc);

   if(lote < LoteMinimo)
     {
      Print("Lote calculado (", lote, ") es menor que LoteMinimo (", LoteMinimo, "). No se abre la operación.");
      return;
     }

   if(trade.Sell(lote, _Symbol, bid, sl, tp, "IchimokuRSI_Sell"))
      Print("Venta abierta: lote=", lote, " sl=", sl, " tp=", tp, " (SL Pips: ", slPips, ", TP Pips: ", tpPips, ")");
   else
      Print("Error al abrir venta: ", trade.ResultRetcodeDescription(), " (Error code: ", GetLastError(), ")");
  }
//+------------------------------------------------------------------+