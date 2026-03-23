//+------------------------------------------------------------------+
//|                                        RSI_Divergence_MultiTF.mq5 |
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
input double RiesgoPorc            = 1.0;    // Riesgo por operación (% del balance)
input double LoteMinimo            = 0.01;   // Lote mínimo si el cálculo es menor

input group "=== Parámetros RSI ==="
input int    RSI_Periodo_H4        = 14;     // Periodo del RSI para el timeframe H4.
input int    RSI_Periodo_D1        = 14;     // Periodo del RSI para el timeframe D1.
input int    RSI_Nivel_Sobrevendido = 30;    // Nivel de sobreventa del RSI para confirmación D1.
input int    RSI_Nivel_Sobrecomprado = 70;   // Nivel de sobrecompra del RSI para confirmación D1.

input group "=== Parámetros ATR ==="
input int    ATR_Periodo_H4        = 14;     // Periodo del ATR para el timeframe H4.
input double ATR_Multiplicador_SL  = 1.5;    // Multiplicador del ATR para calcular el Stop Loss.
input double ATR_Multiplicador_TP  = 3.0;    // Multiplicador del ATR para calcular el Take Profit (2x SL).

input group "=== Filtros ==="
input double MaxSpreadPips         = 2.0;    // Spread máximo permitido en pips para abrir una operación.
input double MinATR_H4_Pips        = 10.0;   // Valor mínimo de ATR en pips para permitir una operación.

input group "=== Identificación ==="
input int    MagicNumber           = 100001; // Número mágico único del EA

//--- Objetos globales
CTrade         trade;          // Objeto para ejecutar operaciones
CPositionInfo  posInfo;        // Objeto para leer posiciones
CAccountInfo   accountInfo;    // Objeto para leer cuenta

//--- Handles de indicadores (se crean en OnInit, se usan en OnTick)
int handleRSI_H4 = INVALID_HANDLE;
int handleRSI_D1 = INVALID_HANDLE;
int handleATR_H4 = INVALID_HANDLE;

//--- Variables de control
datetime ultimaVelaH4 = 0; // Timestamp de la última vela H4 procesada

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   // Configurar el objeto de trading
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   trade.LogLevel(LOG_LEVEL_ERRORS); // Solo loguear errores

   // Crear handles de indicadores
   handleRSI_H4 = iRSI(_Symbol, PERIOD_H4, RSI_Periodo_H4, PRICE_CLOSE);
   handleRSI_D1 = iRSI(_Symbol, PERIOD_D1, RSI_Periodo_D1, PRICE_CLOSE);
   handleATR_H4 = iATR(_Symbol, PERIOD_H4, ATR_Periodo_H4);

   // Validar que los handles se crearon correctamente
   if(handleRSI_H4 == INVALID_HANDLE || handleRSI_D1 == INVALID_HANDLE || handleATR_H4 == INVALID_HANDLE)
     {
      Print("ERROR CRÍTICO: Fallo al crear handles de indicadores. Error: ", GetLastError());
      return(INIT_FAILED);
     }

   // Verificar que el símbolo tiene datos suficientes
   if(Bars(_Symbol, PERIOD_H4) < 300)
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " H4");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(Bars(_Symbol, PERIOD_D1) < 300)
     {
      Print("ERROR: Datos históricos insuficientes para ", _Symbol, " D1");
      return(INIT_PARAMETERS_INCORRECT);
     }

   Print("EA inicializado correctamente. Magic: ", MagicNumber,
         " | Símbolo: ", _Symbol, " | Build: ", TerminalInfoInteger(TERMINAL_BUILD));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   // OBLIGATORIO: liberar todos los handles al cerrar el EA
   if(handleRSI_H4 != INVALID_HANDLE) IndicatorRelease(handleRSI_H4);
   if(handleRSI_D1 != INVALID_HANDLE) IndicatorRelease(handleRSI_D1);
   if(handleATR_H4 != INVALID_HANDLE) IndicatorRelease(handleATR_H4);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Procesar solo en apertura de nueva vela H4 (no en cada tick)
   datetime tiempoVelaActualH4 = iTime(_Symbol, PERIOD_H4, 0);
   if(tiempoVelaActualH4 == ultimaVelaH4) return;
   ultimaVelaH4 = tiempoVelaActualH4;

   // Verificar filtros básicos antes de cualquier lógica
   if(!FiltrosBasicosOK()) return;

   // Leer valores de indicadores H4
   double rsiH4_buffer[], atrH4_buffer[];
   ArraySetAsSeries(rsiH4_buffer, true);
   ArraySetAsSeries(atrH4_buffer, true);

   // Necesitamos 4 velas para detectar divergencias en las últimas 3 velas cerradas (índices 1, 2, 3)
   if(CopyBuffer(handleRSI_H4, 0, 0, 4, rsiH4_buffer) < 4) { Print("Error copiando RSI H4 buffer"); return; }
   if(CopyBuffer(handleATR_H4, 0, 0, 2, atrH4_buffer) < 2) { Print("Error copiando ATR H4 buffer"); return; }

   double atrH4_valor    = atrH4_buffer[1]; // ATR de la última vela cerrada

   // Leer valores de indicadores D1
   double rsiD1_buffer[];
   ArraySetAsSeries(rsiD1_buffer, true);
   // Necesitamos 2 velas para detectar cruce en D1 (actual y anterior)
   if(CopyBuffer(handleRSI_D1, 0, 0, 2, rsiD1_buffer) < 2) { Print("Error copiando RSI D1 buffer"); return; }
   double rsiD1_actual   = rsiD1_buffer[0]; // Vela actual D1 (puede estar incompleta, pero es la más reciente)
   double rsiD1_anterior = rsiD1_buffer[1]; // Última vela cerrada D1

   // Leer precios OHLC H4 para divergencias
   double highH4[], lowH4[];
   ArraySetAsSeries(highH4, true);
   ArraySetAsSeries(lowH4, true);
   // Necesitamos 4 velas para detectar divergencias en las últimas 3 velas cerradas (índices 1, 2, 3)
   if(CopyHigh(_Symbol, PERIOD_H4, 0, 4, highH4) < 4) { Print("Error copiando High H4 buffer"); return; }
   if(CopyLow(_Symbol,  PERIOD_H4, 0, 4, low