# Agente IA de ITVM para Kommo (n8n)

Asesora virtual de admisiones para **ITVM, Instituto Técnico VM** ([itvm.cr](https://itvm.cr), La Uruca, San José, Costa Rica). Atiende por WhatsApp a través de Kommo y hace cuatro cosas:
- orienta sobre las carreras técnicas y los cursos libres;
- revisa si la persona cumple los requisitos;
- responde sobre precios, horarios y financiamiento.

Lo que sabe y cómo se comporta lo mantienen los vendedores de ITVM en **dos archivos de Google Drive**, sin tocar n8n:
- **Planilla** (Google Sheets): programas, precios, horarios, promociones, preguntas frecuentes y datos de contacto.
- **Documento** (Google Docs): nombre del asistente, cómo se presenta, tono, qué tiene que hacer, cuándo derivar e información extra (proceso de matrícula, políticas, becas).

Además:
- **deriva a un asesor humano** cuando la persona quiere matricularse.

La estructura sale del agente "Andrea" (Tienda de Sillas), con varias correcciones (ver [Diferencias con Andrea](#diferencias-con-andrea)).

## Estructura

```
prompts/agente-itvm.md          Prompt del agente (fuente única: se edita acá)
scripts/generar_workflows.py    Genera los JSON de n8n a partir del prompt
scripts/generar_planilla.py     Genera la planilla precargada para ITVM
scripts/generar_documento.js    Genera el Word de instrucciones para ITVM
workflows/                      Workflows listos para importar en n8n
  ITVM - Chat Kommo.json                  Principal: webhook → agente → respuesta
  ITVM - Consultar oferta academica.json  Tool: datos de carreras y cursos
  ITVM - Consultar info adicional.json    Tool: precios, horarios, promos y preguntas frecuentes
  ITVM - Derivar a asesor.json            Tool: mueve el lead a la etapa de derivación, etiqueta, resumen y nota
  ITVM - Sync Planilla.json               Cron: Google Sheet → base de datos, y limpieza
  ITVM - Setup DB.json                    Manual: crea las tablas y carga los programas (una sola vez)
sql/001_esquema.sql             Tablas (prefijo crm.itvm_*)
sql/002_programas_seed.sql      Oferta académica relevada de itvm.cr (contenido de cada programa)
docs/ITVM - Planilla asistente virtual.xlsx   Planilla original que se le pasó a ITVM
docs/ITVM - Instrucciones del asistente.docx  Documento de instrucciones (plantilla)
```

## Flujo

```
Kommo (mensaje entrante) ──► Webhook /itvm-kommo
  ► Config ITVM (todos los IDs en un solo lugar)
  ► Idempotencia (crm.itvm_processed_messages)
  ► Filtros: autor no es bot/usuario · hay texto/audio/archivo · no es mensaje de sistema
  ► Get Lead ► si tiene la etiqueta "ITVM-derivado" → el bot no responde
  ► "/reset" → borra memoria
  ► Audio → transcripción · Texto/archivo → contenido
  ► Buffer en Postgres + espera de 8 s → solo el ÚLTIMO mensaje reclama el lote
  ► Leer Instrucciones (texto del Google Doc, guardado por el sync)
  ► Agente ITVM (gpt-5.4-mini, memoria Postgres de 20 mensajes)
       reglas fijas (prompts/agente-itvm.md) + instrucciones del negocio (Doc)
       ├─ Consultar oferta academica
       ├─ Consultar informacion adicional
       └─ Derivar a asesor
  ► Respuesta → campo "Responde IA" del LEAD ► Salesbot que envía ese campo
```

## Configuración de Kommo (ya hecha)

Cuenta: `https://dwcorporativoitvm.kommo.com`

| Qué | Valor |
|---|---|
| Campo del lead para la respuesta | **Responde IA**, ID `3929118` (área de texto) |
| Campo del lead para el resumen | **Resumen IA**, ID `3929120` (área de texto) |
| Salesbot que envía la respuesta | ID `212896`. Su paso "Enviar mensaje" tiene que tener el texto `{{lead.cf.3929118}}` |
| Etapa de derivación | **LISTO PARA ASESOR (IA)**, creada en los 4 embudos de ventas (ver abajo) |
| Etiqueta de derivado | `ITVM-derivado` (Kommo la crea sola la primera vez) |

Etapa "LISTO PARA ASESOR (IA)" (va después de "Contacto inicial"):

| Embudo | pipeline_id | status_id |
|---|---|---|
| PRINCIPAL ADMINISTRACION | 12492823 | 113965535 |
| ASESOR MAURICIO | 12492855 | 113965539 |
| ASESOR IVAN | 12492867 | 113965543 |
| ASESORA GABRIELA | 14192647 | 113965547 |

El workflow busca la etapa **por nombre** dentro del embudo en el que esté el lead, así que no hace falta cargar estos IDs. Si se agrega un embudo de asesor nuevo, basta con crearle una etapa con ese mismo nombre. Si un embudo no tiene la etapa, la derivación igual pone la etiqueta, el resumen y la nota, pero no mueve el lead.

Falta configurar el **webhook**: Ajustes → Integraciones → Webhooks → evento **"Mensaje entrante"** → URL `https://TU-N8N/webhook/itvm-kommo`.

## Planilla (información que mantiene ITVM)

Google Sheet: `https://docs.google.com/spreadsheets/d/1YZqpfdGdRLp2OH683OvN3NZUjd0D_N27` (compartida como "cualquier persona con el enlace puede ver").

El workflow **"ITVM - Sync Planilla"** la lee cada 2 horas, de 6 a 22 h (hora de Costa Rica):

| Pestaña | Va a | Qué ignora |
|---|---|---|
| Datos generales, Precios, Horarios e inicios, Promociones, Preguntas frecuentes | Texto de `crm.itvm_bot_config` → tool "Consultar informacion adicional" | Filas marcadas EJEMPLO, precios VENCIDOS, promos VENCIDAS, preguntas sin respuesta, notas internas |
| Programas | `crm.itvm_programas` → tool "Consultar oferta academica" | Marcas "(VERIFICAR…)" y "FALTA…". Un programa que se borra de la planilla o tiene Activo = "No" deja de ofrecerse |

**Protecciones:** si alguna pestaña no se puede leer, o alguien le cambia el nombre (Google devolvería otra pestaña sin avisar), el sync **no pisa** la información anterior. Los programas se emparejan **por nombre exacto**: el contenido detallado (temario, palabras clave) viene del seed y se conserva.

> **No renombrar las pestañas ni los encabezados** (fila 4). Si se cambia el nombre de un programa, se crea como programa nuevo, sin temario, y el viejo se desactiva.

## Documento de instrucciones (Google Docs)

1. Subí `docs/ITVM - Instrucciones del asistente.docx` a Google Drive.
2. Abrilo con Google Docs → **Archivo → Guardar como Documentos de Google**. Tiene que ser un Documento de Google, no un .docx.
3. Compartir → **cualquier persona con el enlace puede ver**.
4. Copiá el ID de la URL (`docs.google.com/document/d/ESTE_ID/edit`) y pegalo en el nodo **Config Sync** del workflow "ITVM - Sync Planilla" (campo `doc_id`).

El sync lo lee cada 2 horas y lo guarda en `crm.itvm_bot_config.instrucciones`. El agente lo recibe en cada mensaje como "INSTRUCCIONES DEL NEGOCIO".
- Los ejemplos entre paréntesis que no se completaron, como "(Completar)" o "(Ejemplo: …)", se descartan solos.
- Si el documento no se puede leer, se mantiene la última versión buena.
- Las **reglas fijas** de `prompts/agente-itvm.md` siempre mandan sobre el documento: no inventar precios, usar las herramientas, no armar links, no pedir datos sensibles.

## Instalación

### 1. Base de datos

La forma más simple: importá **"ITVM - Setup DB"**, elegí la credencial de Postgres y ejecutalo una vez. El nodo "Verificar" tiene que mostrar `programas = 12`. Se puede volver a ejecutar sin problema.

O, si tenés acceso directo a la base:

```bash
psql "$DATABASE_URL" -f sql/001_esquema.sql
```

```bash
psql "$DATABASE_URL" -f sql/002_programas_seed.sql
```

Los dos scripts se pueden volver a correr sin problema.

### 2. n8n

1. **Credenciales:**
   - *Bearer Auth* con el token de Kommo (integración privada "Asistente IA ITVM (n8n)").
   - *OpenAI*.
   - *Postgres*.
2. **Importar los workflows en este orden:** primero los 3 subworkflows ("Consultar oferta academica", "Consultar info adicional", "Derivar a asesor"), después "Sync Planilla" y por último "Chat Kommo".
3. En cada nodo HTTP de Kommo, Postgres y OpenAI, elegí la credencial que corresponde. Los nodos de Google Sheets no llevan credencial.
4. En **"Chat Kommo"**, en los 3 nodos tool del agente, elegí el subworkflow correspondiente. Otra opción: regenerá los JSON con los IDs (ver abajo).
5. Ejecutá "Sync Planilla" una vez a mano y fijate que "Guardar Info" y "Guardar Programas" corran sin error.
6. Activá "Sync Planilla" y "Chat Kommo".

El nodo **Config ITVM** ya viene con los valores de la cuenta:

| Campo | Valor |
|---|---|
| `kommo_base_url` | `https://dwcorporativoitvm.kommo.com` |
| `tag_derivado` | `ITVM-derivado` |
| `nombre_etapa_derivado` | `LISTO PARA ASESOR (IA)` |
| `campo_respuesta_lead_id` | `3929118` |
| `campo_resumen_lead_id` | `3929120` |
| `salesbot_id` | `212896` |
| `segundos_debounce` | `8` |

### 3. Prueba

Desde un WhatsApp de prueba:
- **Saludo:** "hola" → se presenta y pregunta qué quiere estudiar.
- **Programa:** "quiero estudiar mecánica de motos" → describe el programa con el folleto.
- **Precio:** "¿cuánto cuesta?" → precio de la planilla, o "se lo confirma un asesor" si no hay.
- **Derivación:** "quiero matricularme" → pide el nombre si falta y deriva. El lead pasa a "LISTO PARA ASESOR (IA)" con la etiqueta, el campo Resumen IA y una nota, y el bot deja de responder.
- **Reset:** "/reset" → reinicia la memoria. Para volver a probar un lead derivado, quitale la etiqueta `ITVM-derivado`.

## Editar las reglas fijas del agente

El nombre, el tono y el comportamiento los cambia ITVM en el documento. Las **reglas fijas** (herramientas, no inventar, derivación) están en `prompts/agente-itvm.md`:

1. Editá `prompts/agente-itvm.md`. No uses `{{ }}`: n8n lo interpretaría como una expresión.
2. Regenerá los workflows:

   ```bash
   python3 scripts/generar_workflows.py --id-oferta ID1 --id-info ID2 --id-derivar ID3
   ```

3. Reimportá **"ITVM - Chat Kommo"**.

Para cambios chicos también podés editar el *System Message* directamente en n8n, pero después hay que pasarlos a este archivo para no perderlos.

## Diferencias con Andrea

| Problema en Andrea | Solución en ITVM |
|---|---|
| La respuesta se escribe en 5 **plantillas compartidas** (hash del `chat_id % 5`). Dos chats que responden a la vez pueden mandarse el mensaje del otro. | La respuesta se guarda en un **campo del lead**, propio de cada conversación, y el Salesbot envía ese campo. |
| El buffer de Redis hace Get y después Delete: se pierde lo que llega en el medio. | Buffer en Postgres con una sola sentencia atómica `UPDATE … RETURNING`; solo el último mensaje reclama el lote. Además saca Redis de la arquitectura. |
| El LLM escribe SQL que se ejecuta tal cual. | La consulta es fija y la búsqueda se hace en código, con sinónimos (`palabras_clave`). |
| La derivación depende de que el texto contenga "te contacta en breve", y hace una llamada extra a OpenAI para el resumen. | Tool explícita **"Derivar a asesor"**: el agente completa nombre, programa, horario, financiamiento y resumen. Usa `tags_to_add`, así que no pisa las etiquetas existentes, y busca la etapa en el embudo del asesor. |
| IDs y subdominio repetidos en muchos nodos. | Un solo nodo **Config ITVM**. |
| Los syncs vaciaban la tabla antes de insertar (TRUNCATE): si fallaba, el bot quedaba sin datos. | Upsert, y **no pisa** nada si alguna pestaña falla. |
| Info del negocio en un Google Doc con texto libre, interpretado con expresiones regulares frágiles. | Planilla con listas desplegables, vencimientos automáticos y filas de ejemplo que se ignoran. |
| Párrafos duplicados en el prompt. | Prompt nuevo en un archivo versionado, sin duplicados. |
| Imágenes sin texto: el bot no respondía. | Le llega "[El cliente envió un archivo…]" y responde igual. |
| Memoria en la tabla compartida `n8n_chat_histories`. | Tabla propia `itvm_chat_histories`. |

## Pendientes / a confirmar con ITVM

- **Precios, horarios y fechas de inicio:** la planilla todavía no tiene precios ni horarios reales; solo las filas de EJEMPLO, que el sync ignora. Hasta que los carguen, el agente dice que lo confirma un asesor.
- **Requisito de Vehículos Livianos:** el folleto de 2026 pide *sexto grado*; la web dice *noveno año*. En la planilla está marcado "VERIFICAR".
- **Semiconductores:** faltan requisitos. **Common Rail:** falta modalidad.
- **Promoción de ejemplo** ("Matrícula gratis enero"): el sync la ignora, pero conviene borrarla de la planilla.
- **Documento de instrucciones:** subirlo a Drive como Documento de Google y pegar su ID en `doc_id` (nodo Config Sync). Mientras no esté, el agente se presenta como "asistente virtual de admisiones de ITVM".
- **Salesbot sobre el lead:** el envío corre el Salesbot 212896 sobre el **lead** (`entity_type: 2`). Antes de activar, conviene probarlo con un lead de prueba.
