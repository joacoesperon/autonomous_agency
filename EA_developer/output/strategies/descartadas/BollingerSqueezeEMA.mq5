//+------------------------------------------------------------------+
//|                                              BollingerSqueezeEMA.mq5 |
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

input group "=== Filtros Generales ==="
input int    MaxSpreadPips    = 20;     // Spread máximo permitido en pips para abrir una operación.
input bool   SoloLunesJueves  = true;   // Operar solo Lun-Jue

input group "=== Parámetros de Indicadores ==="
input int    BB_Periodo       = 20;     // Período de las Bandas de Bollinger.
input double BB_Desviacion    = 2.0;    // Desviación estándar de las Bandas de Bollinger.
input int    EMA_Periodo      = 100;    // Período de la EMA para el filtro de tendencia.

input group "=== Parámetros de Trading ==="
input int    SL_Pips          = 50;     // Valor del Stop Loss en pips.
input int    TP_Pips          = 100;    // Valor del Take Profit en pips.
input int    MagicNumber      = 100001; // Número mágico único del EA

//--- Objetos globales
CTrade         trade;          // Objeto para ejecutar operaciones
CPositionInfo  posInfo;        // Objeto para leer posiciones
CAccountInfo   accountInfo;    // Objeto para leer cuenta

//--- Handles de indicadores (se crean en OnInit, se usan en OnTick)
int handleBB         = INVALID_HANDLE;
int handleEMATendencia = INVALID_HANDLE;

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
   trade.SetTypeFilling(ORDER_FILLING_FOK); // Fill or Kill
   trade.LogLevel(LOG_LEVEL_ERRORS); // Solo loguear errores

   // Crear handles de indicadores
   // Bandas de Bollinger
   handleBB = iBands(_Symbol, PERIOD_H1, BB_Periodo, 0, BB_Desviacion, PRICE_CLOSE);
   // EMA de tendencia
   handleEMATendencia = iMA(_Symbol, PERIOD_H1, EMA_Periodo, 0, MODE_EMA, PRICE_CLOSE);

   // Validar que los handles se crearon correctamente
   if(handleBB == INVALID_HANDLE || handleEMATendencia == INVALID_HANDLE)
     {
      Print("ERROR CRÍTICO: Fallo al crear handles de indicadores. Error: ", GetLastError());
      return(INIT_FAILED);
     }

   // Verificar que el símbolo tiene datos suficientes
   if(Bars(_Symbol, PERIOD_H1) < MathMax(BB_Periodo, EMA_Periodo) + 5) // +5 por seguridad
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " H1");
      return(INIT_PARAMETERS_INCORRECT);
     }

   Print("EA BollingerSqueezeEMA iniciado correctamente. Magic: ", MagicNumber,
         " | Símbolo: ", _Symbol, " | Timeframe: H1 | Build: ", TerminalInfoInteger(TERMINAL_BUILD));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // OBLIGATORIO: liberar todos los handles al cerrar el EA
   if(handleBB         != INVALID_HANDLE) IndicatorRelease(handleBB);
   if(handleEMATendencia != INVALID_HANDLE) IndicatorRelease(handleEMATendencia);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Procesar solo en apertura de nueva vela H1 (no en cada tick)
   datetime tiempoVelaActual = iTime(_Symbol, PERIOD_H1, 0);
   if(tiempoVelaActual == ultimaVela) return;
   ultimaVela = tiempoVelaActual;

   // Verificar filtros básicos antes de cualquier lógica
   if(!FiltrosBasicosOK()) return;

   // Leer valores de indicadores
   double bbUpper[], bbMiddle[], bbLower[];
   double emaTendencia[];
   double open[], high[], low[], close[];

   ArraySetAsSeries(bbUpper,  true);
   ArraySetAsSeries(bbMiddle, true);
   ArraySetAsSeries(bbLower,  true);
   ArraySetAsSeries(emaTendencia, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);

   // Copiar buffers de indicadores y precios (necesitamos al menos 2 velas: 0 y 1)
   if(CopyBuffer(handleBB, 0, 0, 2, bbMiddle) < 2) { Print("Error copiando BB Middle"); return; }
   if(CopyBuffer(handleBB, 1, 0, 2, bbUpper)  < 2) { Print("Error copiando BB Upper"); return; }
   if(CopyBuffer(handleBB, 2, 0, 2, bbLower)  < 2) { Print("Error copiando BB Lower"); return; }
   if(CopyBuffer(handleEMATendencia, 0, 0, 2, emaTendencia) < 2) { Print("Error copiando EMA Tendencia"); return; }

   if(CopyOpen(_Symbol, PERIOD_H1, 0, 2, open) < 2) { Print("Error copiando Open"); return; }
   if(CopyHigh(_Symbol, PERIOD_H1, 0, 2, high) < 2) { Print("Error copiando High"); return; }
   if(CopyLow(_Symbol, PERIOD_H1, 0, 2, low) < 2) { Print("Error copiando Low"); return; }
   if(CopyClose(_Symbol, PERIOD_H1, 0, 2, close) < 2) { Print("Error copiando Close"); return; }

   // Verificar si hay posición abierta del EA en este símbolo
   bool hayPosicion = HayPosicionAbierta();

   // --- LÓGICA DE ENTRADA ---
   if(!hayPosicion)
     {
      // Condición de squeeze: la vela anterior estaba contenida dentro de las Bandas de Bollinger
      bool squeezeAnterior = (low[1] > bbLower[1] && high[1] < bbUpper[1]);

      // Señal de compra:
      // Cierre actual > Banda Superior Y squeeze anterior Y Cierre actual > EMA de tendencia
      bool senalCompra = (close[0] > bbUpper[0]) &&
                         squeezeAnterior &&
                         (close[0] > emaTendencia[0]);

      // Señal de venta:
      // Cierre actual < Banda Inferior Y squeeze anterior Y Cierre actual < EMA de tendencia
      bool senalVenta = (close[0] < bbLower[0]) &&
                        squeezeAnterior &&
                        (close[0] < emaTendencia[0]);

      if(senalCompra)
        {
         double lote = CalcularLote(SL_Pips);
         if(lote > 0) AbrirCompra(SL_Pips, TP_Pips, lote);
        }
      else if(senalVenta)
        {
         double lote = CalcularLote(SL_Pips);
         if(lote > 0) AbrirVenta(SL_Pips, TP_Pips, lote);
        }
     }
  }

//+------------------------------------------------------------------+
//| Verificar filtros básicos                                         |
//+------------------------------------------------------------------+
bool FiltrosBasicosOK()
  {
   // Filtro de spread
   long spreadActual = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   // Convertir MaxSpreadPips a puntos para comparar con SYMBOL_SPREAD
   if(spreadActual > MaxSpreadPips * 10)
     {
      Print("Spread demasiado alto: ", spreadActual, " puntos > ", MaxSpreadPips, " pips");
      return false;
     }

   // Filtro de días (solo Lunes a Jueves si SoloLunesJueves es true)
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
   double tickValue   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double punto       = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(slPips <= 0 || tickValue <= 0) return LoteMinimo;

   // Convertir pips a puntos (para pares de 5 dígitos, 1 pip = 10 puntos)
   // Para XAUUSD, _Point es 0.01, 1 pip = 0.1. Entonces slPips * 10 * _Point es correcto.
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

   return NormalizeDouble(lote, 2); // Normalizar a 2 decimales para lotes
  }

//+------------------------------------------------------------------+
//| Abrir operación de compra                                         |
//+------------------------------------------------------------------+
void AbrirCompra(double slPips, double tpPips, double lote)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // Para pares de 5 dígitos: 1 pip = 10 * _Point
   // Para XAUUSD, _Point es 0.01, 1 pip = 0.1. Entonces slPips * 10 * _Point es correcto.
   double sl  = NormalizeDouble(ask - slPips * 10 * _Point, _Digits);
   double tp  = NormalizeDouble(ask + tpPips * 10 * _Point, _Digits);

   if(!trade.Buy(lote, _Symbol, ask, sl, tp, "BS_Buy"))
      Print("Error Buy: ", trade.ResultRetcodeDescription());
   else
      Print("Compra abierta: lote=", lote, " sl=", sl, " tp=", tp);
  }

//+------------------------------------------------------------------+
//| Abrir operación de venta                                          |
//+------------------------------------------------------------------+
void AbrirVenta(double slPips, double tpPips, double lote)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl  = NormalizeDouble(bid + slPips * 10 * _Point, _Digits);
   double tp  = NormalizeDouble(bid - tpPips * 10 * _Point, _Digits);

   if(!trade.Sell(lote, _Symbol, bid, sl, tp, "BS_Sell"))
      Print("Error Sell: ", trade.ResultRetcodeDescription());
   else
      Print("Venta abierta: lote=", lote, " sl=", sl, " tp=", tp);
  }
//+------------------------------------------------------------------+