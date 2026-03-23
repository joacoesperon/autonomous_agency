//+------------------------------------------------------------------+
//|                                                EMA50_200_RSI_Test.mq5 |
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
input group "=== Configuración de Indicadores ==="
input int    EMA_Rapida       = 50;     // Período de la EMA rápida
input int    EMA_Lenta        = 200;    // Período de la EMA lenta
input int    RSI_Periodo      = 14;     // Período del RSI
input double RSI_Nivel        = 50.0;   // Nivel del RSI para la señal

input group "=== Gestión de Riesgo ==="
input double Riesgo_Porc      = 1.0;    // Riesgo por operación (% del balance)
input double SL_Pips          = 50.0;   // Stop Loss en pips
input double TP_Pips          = 150.0;  // Take Profit en pips
input double LoteMinimo       = 0.01;   // Lote mínimo si el cálculo es menor

input group "=== Filtros ==="
input int    SpreadMaximoPips = 20;     // Spread máximo permitido (en pips)
input bool   SoloLunesJueves  = true;   // Operar solo Lunes a Jueves

input group "=== Identificación ==="
input int    MagicNumber      = 100001; // Número mágico único del EA

//--- Objetos globales
CTrade         trade;          // Objeto para ejecutar operaciones
CPositionInfo  posInfo;        // Objeto para leer posiciones
CAccountInfo   accountInfo;    // Objeto para leer cuenta

//--- Handles de indicadores (se crean en OnInit, se usan en OnTick)
int handleEMA_rapida = INVALID_HANDLE;
int handleEMA_lenta  = INVALID_HANDLE;
int handleRSI        = INVALID_HANDLE; // Handle para el RSI

//--- Variables de control
datetime ultimaVela = 0; // Timestamp de la última vela procesada

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Configurar el objeto de trading
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10); // Desviación de 10 puntos (1 pip para 5 dígitos)
   trade.SetTypeFilling(ORDER_FILLING_FOK); // Fill or Kill

   // Crear handles de indicadores
   // EMA Rápida
   handleEMA_rapida = iMA(_Symbol, PERIOD_H4, EMA_Rapida, 0, MODE_EMA, PRICE_CLOSE);
   // EMA Lenta
   handleEMA_lenta  = iMA(_Symbol, PERIOD_H4, EMA_Lenta, 0, MODE_EMA, PRICE_CLOSE);
   // RSI
   handleRSI        = iRSI(_Symbol, PERIOD_H4, RSI_Periodo, PRICE_CLOSE);

   // Validar que todos los handles se crearon correctamente
   if(handleEMA_rapida == INVALID_HANDLE ||
      handleEMA_lenta  == INVALID_HANDLE ||
      handleRSI        == INVALID_HANDLE)
     {
      Print("ERROR: No se pudieron crear los handles de indicadores. Error: ", GetLastError());
      return(INIT_FAILED);
     }

   // Verificar que el símbolo tiene suficientes datos históricos
   if(Bars(_Symbol, PERIOD_H4) < MathMax(EMA_Lenta, RSI_Periodo) + 5) // +5 para asegurar datos
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " H4");
      return(INIT_PARAMETERS_INCORRECT);
     }

   Print("EA 'EMA50_200_RSI_Test' iniciado correctamente en ", _Symbol, " H4. Magic: ", MagicNumber);
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
   if(handleRSI        != INVALID_HANDLE) IndicatorRelease(handleRSI);
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

   // Verificar filtros básicos antes de cualquier lógica de trading
   if(!FiltrosBasicosOK()) return;

   // Leer valores de indicadores
   double emaRapida[], emaLenta[], rsi[];
   
   // Configurar arrays como series de tiempo (índice 0 = vela actual)
   ArraySetAsSeries(emaRapida, true);
   ArraySetAsSeries(emaLenta, true);
   ArraySetAsSeries(rsi, true);

   // Copiar datos de los buffers de indicadores
   // Se necesitan al menos 3 valores para detectar cruces y valores anteriores de EMA
   if(CopyBuffer(handleEMA_rapida, 0, 0, 3, emaRapida) < 3)
     { Print("Error copiando buffer EMA rápida."); return; }
   if(CopyBuffer(handleEMA_lenta,  0, 0, 3, emaLenta)  < 3)
     { Print("Error copiando buffer EMA lenta."); return; }
   // Para RSI, solo necesitamos el valor de la vela anterior (índice 1)
   if(CopyBuffer(handleRSI,        0, 0, 2, rsi)       < 2)
     { Print("Error copiando buffer RSI."); return; }

   // Obtener valores de la última vela cerrada (índice 1) y la anterior (índice 2)
   double emaRapida_1 = emaRapida[1];
   double emaLenta_1  = emaLenta[1];
   double emaRapida_2 = emaRapida[2];
   double emaLenta_2  = emaLenta[2];
   double rsiValor_1  = rsi[1];

   // Verificar si hay posición abierta del EA en este símbolo
   bool hayPosicion = HayPosicionAbierta();

   // --- LÓGICA DE ENTRADA ---
   if(!hayPosicion)
     {
      // Señal de compra: EMA rápida cruza EMA lenta hacia arriba Y RSI > Nivel
      bool senalCompra = (emaRapida_1 > emaLenta_1 && emaRapida_2 <= emaLenta_2) && (rsiValor_1 > RSI_Nivel);
      // Señal de venta: EMA rápida cruza EMA lenta hacia abajo Y RSI < Nivel
      bool senalVenta  = (emaRapida_1 < emaLenta_1 && emaRapida_2 >= emaLenta_2) && (rsiValor_1 < RSI_Nivel);

      if(senalCompra)
        {
         Print("Señal de COMPRA detectada: EMA rápida cruza EMA lenta hacia arriba y RSI (", rsiValor_1, ") > ", RSI_Nivel);
         AbrirCompra();
        }
      else if(senalVenta)
        {
         Print("Señal de VENTA detectada: EMA rápida cruza EMA lenta hacia abajo y RSI (", rsiValor_1, ") < ", RSI_Nivel);
         AbrirVenta();
        }
     }
  }

//+------------------------------------------------------------------+
//| Verificar filtros básicos                                         |
//+------------------------------------------------------------------+
bool FiltrosBasicosOK()
  {
   // Filtro de spread: SpreadMaximoPips se convierte a puntos
   long spreadActual = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD); // Spread en puntos
   if(spreadActual > SpreadMaximoPips * 10) // Convertir pips a puntos para la comparación
     {
      Print("Filtro de Spread: Spread actual (", spreadActual, " puntos) es mayor que el máximo permitido (", SpreadMaximoPips, " pips).");
      return false;
     }

   // Filtro de días (solo Lunes a Jueves)
   if(SoloLunesJueves)
     {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      // dt.day_of_week: 0=Dom, 1=Lun, 2=Mar, 3=Mié, 4=Jue, 5=Vie, 6=Sáb
      if(dt.day_of_week == 0 || dt.day_of_week == 5 || dt.day_of_week == 6)
        {
         Print("Filtro de Día: Hoy es ", EnumToString((ENUM_DAY_OF_WEEK)dt.day_of_week), ". Operación no permitida.");
         return false;
        }
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
   double riesgoUSD   = balance * Riesgo_Porc / 100.0; // Usar Riesgo_Porc del input
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
   lote = MathMax(lote, LoteMinimo); // Asegurar que no sea menor que el lote mínimo configurado

   return NormalizeDouble(lote, 2); // Normalizar a 2 decimales para lotes
  }

//+------------------------------------------------------------------+
//| Abrir operación de compra                                         |
//+------------------------------------------------------------------+
void AbrirCompra()
  {
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl     = ask - SL_Pips * 10 * _Point; // SL_Pips del input
   double tp     = ask + TP_Pips * 10 * _Point; // TP_Pips del input

   // Asegurar que SL y TP estén normalizados al número de dígitos del símbolo
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   // Calcular lote basado en el SL configurado
   double lote = CalcularLote(SL_Pips);

   // Verificar si el lote es válido
   if(lote <= 0)
     {
      Print("Error: Lote calculado es inválido (", lote, "). No se puede abrir compra.");
      return;
     }

   // Enviar orden de compra
   if(trade.Buy(lote, _Symbol, ask, sl, tp, "EA_Compra"))
      Print("Compra abierta: Lote=", lote, ", SL=", sl, ", TP=", tp);
   else
      Print("Error al abrir compra: ", trade.ResultRetcodeDescription(), " (", GetLastError(), ")");
  }

//+------------------------------------------------------------------+
//| Abrir operación de venta                                          |
//+------------------------------------------------------------------+
void AbrirVenta()
  {
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl     = bid + SL_Pips * 10 * _Point; // SL_Pips del input
   double tp     = bid - TP_Pips * 10 * _Point; // TP_Pips del input

   // Asegurar que SL y TP estén normalizados al número de dígitos del símbolo
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   // Calcular lote basado en el SL configurado
   double lote = CalcularLote(