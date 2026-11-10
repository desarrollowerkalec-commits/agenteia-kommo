# Agente IA de ITVM para Kommo (n8n)

Asesora virtual de admisiones para **ITVM, Instituto Técnico VM** ([itvm.cr](https://itvm.cr), La Uruca, San José, Costa Rica). Atiende por WhatsApp a través de Kommo y hace cuatro cosas:
- orienta sobre las 6 carreras técnicas y los 6 cursos libres;
- revisa si la persona cumple los requisitos;
- responde sobre financiamiento (CONAPE y letras de cambio);
- **deriva a un asesor humano** cuando la persona quiere matricularse.

La estructura sale del agente "Andrea" (Tienda de Sillas), con varias correcciones (ver [Diferencias con Andrea](#diferencias-con-andrea)).

## Estructura

```
prompts/agente-itvm.md          Prompt del agente (fuente única: se edita acá)
scripts/generar_workflows.py    Genera los JSON de n8n a partir del prompt
workflows/                      Workflows listos para importar en n8n
  ITVM - Chat Kommo.json                  Principal: webhook → agente → respuesta
  ITVM - Consultar oferta academica.json  Tool: datos de carreras y cursos
  ITVM - Consultar info adicional.json    Tool: precios, fechas y promos (Google Doc)
  ITVM - Derivar a asesor.json            Tool: mueve el lead, agrega etiqueta y nota
  ITVM - Sync Documento.json              Cron: Google Doc → base de datos, y limpieza
sql/001_esquema.sql             Tablas (prefijo crm.itvm_*)
sql/002_programas_seed.sql      Oferta académica relevada de itvm.cr y sus folletos
docs/plantilla-google-doc.md    Plantilla del Doc que mantiene el equipo de ITVM
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
  ► Agente ITVM (gpt-5.4-mini, memoria Postgres de 20 mensajes)
       ├─ Consultar oferta academica
       ├─ Consultar informacion adicional
       └─ Derivar a asesor  (cambia etapa + etiqueta + nota en el lead)
  ► Respuesta → campo del CONTACTO ► Salesbot que envía ese campo
```

## Instalación

### 1. Base de datos

En el Postgres que usa n8n (o en otro):

```bash
psql "$DATABASE_URL" -f sql/001_esquema.sql
```

```bash
psql "$DATABASE_URL" -f sql/002_programas_seed.sql
```

Los dos scripts se pueden volver a correr sin problema. Para cambiar un programa, editá `002_programas_seed.sql` y corrélo otra vez. Para ocultar uno: `UPDATE crm.itvm_programas SET activo = false WHERE slug = '...'`.

### 2. Kommo

1. **Token de larga duración:** Ajustes → Integraciones → crear integración privada → copiar el token.
2. **Campo del contacto para la respuesta:** Ajustes → Contactos → agregar un campo de tipo **área de texto** (por ejemplo "Respuesta bot"). Anotá su ID.
3. **Salesbot:** creá uno con un solo paso, "Enviar mensaje", con el texto `{{contact.cf.ID_DEL_CAMPO}}`. Anotá el ID del bot.
4. **Etapa de derivación:** la etapa del embudo a la que pasa el lead cuando el bot deriva (por ejemplo "Asesor – matrícula"). Anotá `status_id` y `pipeline_id`.
5. **Webhook:** Ajustes → Integraciones → Webhooks → evento **"Mensaje entrante"** → URL `https://TU-N8N/webhook/itvm-kommo`.

### 3. n8n

1. **Credenciales:**
   - *Bearer Auth* con el token de Kommo.
   - *OpenAI*.
   - *Postgres*. Para el subworkflow de oferta alcanza con un usuario de solo lectura.
2. **Importar los workflows en este orden:** primero los 3 subworkflows ("Consultar oferta academica", "Consultar info adicional", "Derivar a asesor"), después "Sync Documento" y por último "Chat Kommo".
3. En cada nodo HTTP / Postgres / OpenAI, elegí la credencial que corresponde.
4. En **"Chat Kommo"**:
   - En el nodo **Config ITVM**, completá:

     | Campo | Valor |
     |---|---|
     | `kommo_base_url` | `https://dwcorporativoitvm.kommo.com` (ya cargado) |
     | `tag_derivado` | nombre de la etiqueta de derivado (por defecto `ITVM-derivado`) |
     | `status_derivado_id`, `pipeline_id` | IDs del paso 2.4 (0 = no mover de etapa) |
     | `campo_respuesta_contacto_id` | ID del campo del paso 2.2 |
     | `campo_resumen_lead_id` | campo del lead donde se guarda el resumen al derivar (0 = solo nota) |
     | `salesbot_id` | ID del paso 2.3 |
     | `segundos_debounce` | espera para juntar mensajes seguidos (8 s) |

   - En los 3 nodos tool del agente, elegí el subworkflow correspondiente. Otra opción: regenerá los JSON con los IDs (ver abajo).
5. En **"Sync Documento"**, reemplazá `ID_DEL_DOCUMENTO` por el ID del Google Doc (ver `docs/plantilla-google-doc.md`).
6. Activá "Sync Documento" y "Chat Kommo".

### 4. Prueba

Desde un WhatsApp de prueba:
- **Saludo:** "hola" → se presenta y pregunta qué quiere estudiar.
- **Programa:** "quiero estudiar mecánica de motos" → describe el programa con el folleto.
- **Precio:** "¿cuánto cuesta?" → precio del Doc, o "se lo confirma un asesor".
- **Derivación:** "quiero matricularme" → pide el nombre si falta y deriva. El lead se mueve de etapa, queda con la etiqueta y una nota, y el bot deja de responder.
- **Reset:** "/reset" → reinicia la memoria. Para volver a probar un lead derivado, quitale la etiqueta.

## Editar el prompt

1. Editá `prompts/agente-itvm.md`. No uses `{{ }}`: n8n lo interpretaría como una expresión.
2. Regenerá los workflows:

   ```bash
   python3 scripts/generar_workflows.py --nombre-agente "Sofía" --id-oferta ID1 --id-info ID2 --id-derivar ID3
   ```

3. Reimportá **"ITVM - Chat Kommo"**. Si los IDs de los subworkflows ya están cargados en el JSON, no hay que volver a elegirlos a mano.

Para cambios chicos también podés editar el *System Message* directamente en n8n, pero después hay que pasarlos a este archivo para no perderlos.

## Diferencias con Andrea

| Problema en Andrea | Solución en ITVM |
|---|---|
| La respuesta se escribe en 5 **plantillas compartidas** (hash del `chat_id % 5`). Dos chats que responden a la vez pueden mandarse el mensaje del otro. | La respuesta se guarda en un **campo del contacto**, propio de cada persona, y el Salesbot envía ese campo. |
| El buffer de Redis hace Get y después Delete: se pierde lo que llega en el medio. | Buffer en Postgres con una sola sentencia atómica `UPDATE … RETURNING`; solo el último mensaje reclama el lote. Además saca Redis de la arquitectura. |
| El LLM escribe SQL que se ejecuta tal cual. | La consulta es fija y la búsqueda se hace en código, con sinónimos (`palabras_clave`). |
| La derivación depende de que el texto contenga "te contacta en breve", y hace una llamada extra a OpenAI para el resumen. | Tool explícita **"Derivar a asesor"**: el agente completa nombre, programa, horario, financiamiento y resumen, y queda una nota en el lead. Usa `tags_to_add`, así que no pisa las etiquetas que ya existen. |
| IDs y subdominio repetidos en muchos nodos. | Un solo nodo **Config ITVM**. |
| El sync vaciaba la tabla antes de insertar (TRUNCATE): si fallaba, el bot quedaba sin datos. | El sync del Doc hace upsert y **no pisa** la info si el Doc vino vacío o como página de login. |
| Párrafos duplicados en el prompt. | Prompt nuevo en un archivo versionado, sin duplicados. |
| Imágenes sin texto: el bot no respondía. | Le llega "[El cliente envió un archivo…]" y responde igual. |
| Memoria en la tabla compartida `n8n_chat_histories`. | Tabla propia `itvm_chat_histories`. |

## Pendientes / a confirmar con ITVM

- **Requisito de Vehículos Livianos:** el folleto de 2026 pide *sexto grado*; la página web dice *noveno año*. El seed usa el folleto. Confirmar.
- **Resolución INA:** la página "Carreras" dice 2026-01 y el folleto de Vehículos Livianos dice 2026-02. El seed usa 2026-02.
- **Precios y fechas de inicio:** no están publicados (salvo folletos viejos). Cargarlos en el Google Doc; la plantilla trae los montos viejos marcados para confirmar.
- **Semiconductores:** el sitio no publica requisitos.
- **Montacargas:** la última edición publicada fue del 19 al 21 de octubre de 2026; las próximas fechas van en el Doc.
- **Nombre del agente:** por defecto "Sofía" (`--nombre-agente`).
- **API de Kommo:** si la cuenta no acepta `tags_to_add` en `PATCH /api/v4/leads`, hay que cambiar el nodo "Armar Cambios" del subworkflow "Derivar a asesor" para que mande `_embedded.tags` con las etiquetas existentes más la nueva (como hacía Andrea).
