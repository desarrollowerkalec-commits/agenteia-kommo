# Agente IA de ITVM para Kommo (n8n)

Asesora virtual de admisiones de **ITVM** ([itvm.cr](https://itvm.cr)) que atiende por WhatsApp a través de Kommo: orienta sobre carreras y cursos, revisa requisitos, responde precios y horarios, y **pasa con un asesor** cuando la persona quiere matricularse.

Lo que sabe y cómo se comporta lo mantienen los vendedores de ITVM en Google Drive, sin tocar n8n:
- **Planilla** ([Google Sheets](https://docs.google.com/spreadsheets/d/1YZqpfdGdRLp2OH683OvN3NZUjd0D_N27)): programas, precios, horarios, promociones, preguntas frecuentes y datos de contacto.
- **Documento** ([Google Docs](https://docs.google.com/document/d/190WtOTVfCgF01xcNyE2UA4DO6CYypPOWMYd1aY2Ucpk)): nombre del asistente, tono, qué hacer, cuándo derivar e información extra.

Se leen **una vez por día a las 6:00 a.m.** (Costa Rica). Lo que se cambie hoy se aplica desde mañana; para aplicarlo en el momento, se ejecuta "ITVM - Actualizar" a mano.

## Los 3 workflows

| Workflow | Qué hace |
|---|---|
| **ITVM - Chat** | Recibe el mensaje de Kommo, junta los mensajes seguidos, transcribe audios, responde con el agente y, si corresponde, deriva al asesor. |
| **ITVM - Busqueda** | Herramienta del agente: busca carreras y cursos. |
| **ITVM - Actualizar** | Todos los días a las 6 a.m. (o a mano): crea las tablas si no existen, lee la planilla y el documento, y limpia datos viejos. |

```
Kommo ──► ITVM - Chat
            Filtros · idempotencia · solo leads con "CONTESTA IA" (sin "NO IA" ni "ITVM-derivado") · /reset
            Audio → texto · espera de 8 s para juntar mensajes
            Agente (gpt-5.4-mini + memoria)
              ├─ reglas fijas            prompts/agente-itvm.md
              ├─ instrucciones           Google Doc   ┐ los guarda
              ├─ información actualizada planilla     ┘ ITVM - Actualizar
              └─ tool "Buscar programas" ──► ITVM - Busqueda
            Respuesta → campo "Responde IA" del lead → Salesbot la envía
            Si el agente marcó [DERIVAR] → resumen IA → etapa "LISTO PARA ASESOR (IA)"
                                          + etiqueta + campo "Resumen IA" + nota
```

## Cargar en n8n

**1. Credenciales** (Credentials → Add credential):
- **Postgres** "Postgres ITVM": datos del Postgres de Railway (servicio Postgres → Variables). Si n8n está en otro proyecto, usá `DATABASE_PUBLIC_URL`, con SSL en "Allow".
- **OpenAI** "OpenAI ITVM".
- **Bearer Auth** "Kommo ITVM": token de la integración privada de Kommo.

**2. Importar** (Create workflow → ⋯ → Import from File):
1. **ITVM - Actualizar**
   - Credencial Postgres en los nodos Postgres.
   - **Execute workflow** una vez: crea las tablas y carga la planilla y el documento.
   - Save y activar.
2. **ITVM - Busqueda**
   - Credencial Postgres.
   - Save. No hace falta activarlo.
3. **ITVM - Chat**
   - Credenciales:
     - Postgres en todos los nodos Postgres y en la memoria.
     - OpenAI en "OpenAI Chat Model", "Transcribir Audio" y "Resumen IA".
     - Kommo en los nodos HTTP de Kommo.
   - En el nodo **Buscar programas**, elegí "ITVM - Busqueda".
   - Save y activar.

**3. Kommo:** Ajustes → Integraciones → Webhooks → pegar la **Production URL** del nodo "Webhook Kommo" (`…/webhook/itvm-kommo`) con el evento **"Mensaje entrante"**.

## Configuración de Kommo (ya hecha)

Cuenta `dwcorporativoitvm.kommo.com`. Estos valores están en el nodo **Config ITVM** del Chat:

| Qué | Valor |
|---|---|
| Campo del lead para la respuesta | Responde IA, `3929118` |
| Campo del lead para el resumen | Resumen IA, `3929120` |
| Salesbot | `212896`. Su "Enviar mensaje" debe tener `{{lead.cf.3929118}}` |
| Etapa de derivación | "LISTO PARA ASESOR (IA)", creada en los embudos PRINCIPAL, MAURICIO, IVAN y GABRIELA. Se busca por nombre en el embudo del lead. |
| **Cuándo contesta el bot** | Solo si el lead tiene la etiqueta **`CONTESTA IA`** y **no** tiene **`NO IA`** ni `ITVM-derivado`. Sin `CONTESTA IA` el bot no responde nada. |
| Apagar el bot en un lead | Ponerle la etiqueta `NO IA`. |
| Etiqueta de derivado | `ITVM-derivado` (la pone el bot al pasar con un asesor). Para que vuelva a atender, se le quita. |

## Reglas de la planilla y el documento

- **No renombrar** pestañas ni títulos de columnas (fila 4). Si se cambia el nombre de un programa, el asistente lo toma como programa nuevo.
- Se ignoran:
  - las filas marcadas EJEMPLO;
  - los precios y promos VENCIDOS;
  - las preguntas sin respuesta;
  - las notas internas;
  - los textos "(Completar)" y "(Ejemplo: …)" del documento.
- Si la planilla o el documento no se pueden leer (o el documento está vacío), **se mantiene la última versión buena**.
- El documento tiene que ser un **Documento de Google** (no un .docx subido) compartido como "cualquier persona con el enlace puede ver".

## Repositorio

```
prompts/agente-itvm.md            Reglas fijas del agente (herramienta, no inventar, derivación)
scripts/generar_workflows.py      Genera los 3 JSON de workflows/
scripts/generar_planilla.py       Genera la planilla inicial
scripts/generar_documento.js      Genera el Word de instrucciones inicial
sql/001_esquema.sql               Tablas (las crea "ITVM - Actualizar")
sql/002_programas_seed.sql        Temario y palabras clave iniciales de cada programa
workflows/                        ITVM - Chat / Busqueda / Actualizar
docs/                             Planilla y Word originales que se le pasaron a ITVM
```

Para cambiar las reglas fijas: editar `prompts/agente-itvm.md` (sin `{{ }}`), correr `python3 scripts/generar_workflows.py` y reimportar "ITVM - Chat".
