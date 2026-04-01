# OpenClaw Test Prompts (Shees + Marketer)

## 1) Shees -> Delegacion completa al Marketer

```text
Shees, quiero una prueba operativa completa.

Objetivo:
- Delega al Marketer la creacion de 1 bloque de contenido completo sobre:
  "Por que el trading algoritmico reduce errores emocionales en mercados volatiles"

Entregables del bloque:
- guion de video (30-45s)
- 6 ideas de carrusel
- caption de Instagram con 4-6 hashtags
- hilo de 5 tweets

Reglas obligatorias:
1) No cambies configuracion global por defecto.
2) Esta es una corrida puntual con overrides.
3) El Marketer debe enviar la aprobacion final por Telegram HITL directamente al owner.
4) Si video esta deshabilitado por defecto, forzar provider de video solo para esta corrida.
5) Tu NO actues de intermediario de aprobacion.

Responde SOLO con:
- delegado: si/no
- agente_objetivo: marketer
- override_llm_script: (provider/model)
- override_image: (provider/model)
- override_video: (provider)
- estado: en_progreso / enviado_a_aprobacion
```

## 2) Marketer -> Corrida completa con overrides puntuales

```text
Ejecuta una corrida puntual completa con overrides, sin tocar defaults globales.

Tema:
"Por que el trading algoritmico reduce errores emocionales en mercados volatiles"

Stack puntual para ESTA corrida:
- Script/copy LLM: provider=openai, model=llama3.3:latest
- Prompt visual LLM: provider=openai, model=llama3.3:latest
- Imagen: provider=flux, model=black-forest-labs/flux-schnell
- Video: provider=d-id

Entregables obligatorios:
1) Video script 30-45s
2) 6 puntos de carrusel
3) Caption Instagram con 4-6 hashtags
4) 5 tweets (thread)
5) Enviar a Telegram HITL con opciones Approve / Deny / Request Changes

Reglas:
- No hype, no promesas, no "guaranteed".
- Mantener tono fintech profesional.
- Si falta API de video, no te quedes bloqueado: genera todo lo demas y reporta exactamente que variable falto.

Salida final (breve):
- success: true/false
- generado: [script, carousel, caption, tweets, video]
- enviado_a_telegram: true/false
- bloqueos: ninguno / lista
```

## 3) Prueba low-cost (sin video)

```text
Quiero prueba low-cost/local.

Genera 1 bloque sin video:
- guion corto (solo texto)
- 6 puntos de carrusel
- caption Instagram con 4-6 hashtags
- 5 tweets

Overrides puntuales:
- llm script: provider=openai, model=llama3.3:latest
- llm prompts: provider=openai, model=llama3.3:latest
- imagenes: provider=flux, model=black-forest-labs/flux-schnell

No cambies defaults globales.
Envialo a Telegram HITL igual (sin video).

Salida:
- success
- assets_generados
- enviado_a_telegram
- errores
```

## 4) Prompt de refinamiento (iterar hasta aprobar)

```text
No apruebo todavia. Quiero ajustes concretos:

1) Hook mas agresivo en los primeros 3 segundos.
2) Caption mas corto (max 180 caracteres antes de hashtags).
3) Hashtags mas nicho forex/algo (sin genericos).
4) Carrusel con lenguaje mas simple, menos tecnico.
5) CTA final mas claro a "link en bio".

Aplica cambios y vuelve a enviar a Telegram HITL para aprobacion.
No cambies configuracion global.
```

## 5) Prompt de diagnostico (cuando "no hace nada")

```text
No ejecutaste el flujo. Haz diagnostico operativo real ahora.

Quiero que valides y reportes:
1) Herramientas que intentaste ejecutar.
2) Si hubo fallo de tool-calling.
3) Variables/env faltantes exactas.
4) Que paso se corto (script, image, video, telegram).
5) Reintento automatico con fallback razonable.

Luego ejecuta una nueva corrida minima (script + 1 imagen + caption + 1 tweet) y reporta resultado.
```

## 6) Cambio permanente de defaults (solo cuando se decide)

```text
Ahora si quiero cambio permanente de defaults del Marketer.

Actualiza configuracion por defecto a:
- provider_selections.llm = google_gemini_2_5_flash_copy
- provider_selections.image = flux_schnell_free
- provider_selections.video = d_id_baseline_avatar

Confirma exactamente que claves cambiaste y no toques otras secciones.
```
