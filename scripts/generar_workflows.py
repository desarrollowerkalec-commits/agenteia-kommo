#!/usr/bin/env python3
"""
Genera los workflows de n8n del agente ITVM en workflows/*.json.

El prompt del agente vive en prompts/agente-itvm.md (fuente unica). Despues de editarlo,
volve a correr este script y reimporta "ITVM - Chat Kommo" en n8n.

Uso:
  python3 scripts/generar_workflows.py \
      --nombre-agente "Sofía" \
      --id-oferta  <ID workflow "ITVM - Consultar oferta academica"> \
      --id-info    <ID workflow "ITVM - Consultar info adicional"> \
      --id-derivar <ID workflow "ITVM - Derivar a asesor">

Los IDs de subworkflows son opcionales: si no se pasan, despues de importar hay que
elegir el subworkflow a mano en cada nodo tool del agente.
"""
import argparse
import json
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "workflows"
MODELO = "gpt-5.4-mini"
TAG = [{"name": "cliente:itvm"}]
CHAT_HISTORY_TABLE = "itvm_chat_histories"


_CONTADOR = [0]


def nid():
    """UUID determinista (mismo orden de generacion => mismos IDs), para diffs limpios en git."""
    _CONTADOR[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "itvm-agente/%d" % _CONTADOR[0]))


def nodo(nombre, tipo, version, pos, params, **extra):
    n = {
        "parameters": params,
        "id": nid(),
        "name": nombre,
        "type": tipo,
        "typeVersion": version,
        "position": list(pos),
    }
    n.update(extra)
    return n


def conectar(conns, origen, destino, salida=0, tipo="main"):
    """Conecta origen -> destino. salida = indice de output del nodo origen."""
    por_tipo = conns.setdefault(origen, {}).setdefault(tipo, [])
    while len(por_tipo) <= salida:
        por_tipo.append([])
    por_tipo[salida].append({"node": destino, "type": tipo, "index": 0})


def workflow(nombre, nodos, conns):
    return {
        "name": nombre,
        "nodes": nodos,
        "connections": conns,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "tags": TAG,
    }


def ref_workflow(wf_id, nombre):
    if wf_id:
        return {"__rl": True, "value": wf_id, "mode": "id", "cachedResultName": nombre}
    return {"__rl": True, "value": "", "mode": "list", "cachedResultName": nombre}


def cond_bool(cid, expr):
    return {
        "id": cid,
        "leftValue": expr,
        "rightValue": True,
        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
    }


def filtro(conds, loose=True):
    return {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "loose" if loose else "strict",
                "version": 2,
            },
            "conditions": conds,
            "combinator": "and",
        },
        "options": {},
    }


def asignaciones(campos):
    """campos: lista de (nombre, valor, tipo)."""
    return {
        "assignments": {
            "assignments": [
                {"id": nid(), "name": n, "value": v, "type": t} for n, v, t in campos
            ]
        },
        "options": {},
    }


def http_kommo(metodo, url, body_expr=None, query=None):
    p = {
        "method": metodo,
        "url": url,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpBearerAuth",
        "options": {"response": {"response": {"responseFormat": "json"}}},
    }
    if query:
        p["sendQuery"] = True
        p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query]}
    if body_expr:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_expr
    if metodo == "GET":
        p.pop("method")
    return p


def pg(query, params_expr=None, **extra):
    p = {"operation": "executeQuery", "query": query, "options": {}}
    if params_expr:
        p["options"]["queryReplacement"] = params_expr
    return nodo(extra.pop("nombre"), "n8n-nodes-base.postgres", 2.6, extra.pop("pos"), p, **extra)


def espera(nombre, pos, segundos):
    return nodo(nombre, "n8n-nodes-base.wait", 1.1, pos, {"amount": segundos, "unit": "seconds"},
                webhookId=nid())


def trigger_subworkflow(pos, entradas):
    return nodo(
        "When Executed by Another Workflow",
        "n8n-nodes-base.executeWorkflowTrigger",
        1.1,
        pos,
        {"workflowInputs": {"values": [{"name": e} for e in entradas]}},
    )


def tool_workflow(nombre, pos, descripcion, wf_ref, entradas):
    """entradas: dict nombre -> expresion n8n."""
    return nodo(
        nombre,
        "@n8n/n8n-nodes-langchain.toolWorkflow",
        2.2,
        pos,
        {
            "description": descripcion,
            "workflowId": wf_ref,
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": entradas,
                "matchingColumns": [],
                "schema": [
                    {
                        "id": k,
                        "displayName": k,
                        "required": False,
                        "defaultMatch": False,
                        "display": True,
                        "canBeUsedToMatch": True,
                        "type": "string",
                    }
                    for k in entradas
                ],
                "attemptToConvertTypes": False,
                "convertFieldsToString": False,
            },
        },
    )


def from_ai(nombre, descripcion):
    descripcion = descripcion.replace("`", "'")
    return "={{ $fromAI('%s', `%s`, 'string') }}" % (nombre, descripcion)


# ---------------------------------------------------------------------------
# Expresiones reutilizadas
# ---------------------------------------------------------------------------
CFG = "$('Config ITVM').first().json"
MSG = "$('Set Campos Mensaje').first().json"
BASE = "{{ " + CFG + ".kommo_base_url }}"


# ---------------------------------------------------------------------------
# 1) Workflow principal: ITVM - Chat Kommo
# ---------------------------------------------------------------------------
def wf_chat(prompt, ids):
    N, C = [], {}
    add = N.append

    add(nodo("Webhook Kommo", "n8n-nodes-base.webhook", 2, (0, 300),
             {"httpMethod": "POST", "path": "itvm-kommo", "options": {}}, webhookId=nid()))

    add(nodo("Config ITVM", "n8n-nodes-base.set", 3.4, (220, 300), asignaciones([
        ("kommo_base_url", "https://dwcorporativoitvm.kommo.com", "string"),
        ("tag_derivado", "ITVM-derivado", "string"),
        ("nombre_etapa_derivado", "LISTO PARA ASESOR (IA)", "string"),
        ("campo_respuesta_lead_id", 3929118, "number"),
        ("campo_resumen_lead_id", 3929120, "number"),
        ("salesbot_id", 212896, "number"),
        ("segundos_debounce", 8, "number"),
    ]) | {"includeOtherFields": True}))

    add(nodo("Set Campos Mensaje", "n8n-nodes-base.set", 3.4, (440, 300), asignaciones([
        ("message_id", "={{ $json.body['message[add][0][id]'] }}", "string"),
        ("chat_id", "={{ $json.body['message[add][0][chat_id]'] }}", "string"),
        ("element_id", "={{ $json.body['message[add][0][element_id]'] }}", "string"),
        ("element_type", "={{ $json.body['message[add][0][element_type]'] || '' }}", "string"),
        ("contact_id", "={{ $json.body['message[add][0][contact_id]'] || '' }}", "string"),
        ("text", "={{ $json.body['message[add][0][text]'] || '' }}", "string"),
        ("attachment_type", "={{ $json.body['message[add][0][attachment][type]'] || 'text' }}", "string"),
        ("attachment_link", "={{ $json.body['message[add][0][attachment][link]'] || '' }}", "string"),
        ("author_name", "={{ $json.body['message[add][0][author][name]'] || '' }}", "string"),
        ("author_type", "={{ $json.body['message[add][0][author][type]'] || 'customer' }}", "string"),
    ])))

    add(pg(
        "INSERT INTO crm.itvm_processed_messages (message_id, chat_id)\n"
        "VALUES ($1, $2)\nON CONFLICT (message_id) DO NOTHING\nRETURNING message_id;",
        "={{ [" + MSG + ".message_id, " + MSG + ".chat_id] }}",
        nombre="Idempotencia", pos=(660, 300)))

    add(nodo("Filter Mensaje Nuevo", "n8n-nodes-base.filter", 2.2, (880, 300), filtro([
        cond_bool("n1", "={{ String($json.message_id || '').length > 0 }}"),
    ])))

    add(nodo("Filter Mensaje Valido", "n8n-nodes-base.filter", 2.2, (1100, 300), filtro([
        cond_bool("v1", "={{ !['bot','system','user'].includes(" + MSG + ".author_type) }}"),
        cond_bool("v2", "={{ (" + MSG + ".text || '').trim().length > 0 || "
                        "['voice','audio','picture','image','video','file','document'].includes(" + MSG + ".attachment_type) }}"),
        cond_bool("v3", "={{ (() => { const n = (" + MSG + ".author_name || '').toLowerCase().trim(); "
                        "const bloqueados = ['itvm','itvm bot','asistente itvm','ai chat','aichat','salesbot','chatbot','bot','sistema','system','.','@']; "
                        "return n.length > 0 && !bloqueados.includes(n); })() }}"),
        cond_bool("v4", "={{ (() => { const t = String(" + MSG + ".text || '').trim(); "
                        "return !(/^unable to open this message/i.test(t) || /support\\.kommo\\.com/i.test(t)); })() }}"),
    ])))

    add(espera("Wait Inicial 2s", (1320, 300), 2))

    add(nodo("Get Lead", "n8n-nodes-base.httpRequest", 4.2, (1540, 300),
             http_kommo("GET", "=" + BASE + "/api/v4/leads/{{ " + MSG + ".element_id }}",
                        query=[("with", "contacts")])))

    add(nodo("Filter Bot Activo", "n8n-nodes-base.filter", 2.2, (1760, 300), filtro([
        cond_bool("t1", "={{ !((($json._embedded && $json._embedded.tags) || []).some(t => "
                        "String(t.name || '').toLowerCase() === String(" + CFG + ".tag_derivado).toLowerCase())) }}"),
    ], loose=False)))

    add(nodo("Switch /reset", "n8n-nodes-base.switch", 3.2, (1980, 300), {
        "rules": {"values": [{
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "r1",
                    "leftValue": "={{ (" + MSG + ".text || '').trim().toLowerCase() }}",
                    "rightValue": "^/?(reset|resetear|reiniciar)( todo)?$",
                    "operator": {"type": "string", "operation": "regex"},
                }],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": "reset",
        }]},
        "options": {"fallbackOutput": "extra", "renameFallbackOutput": "normal"},
    }))

    # --- rama reset
    add(pg(
        "WITH borrado AS (\n  DELETE FROM " + CHAT_HISTORY_TABLE + " WHERE session_id = $1\n)\n"
        "UPDATE crm.itvm_buffer SET procesado = true WHERE chat_id = $1 AND NOT procesado;",
        "={{ [" + MSG + ".chat_id] }}",
        nombre="Reset Memoria", pos=(2200, 100)))
    add(nodo("Set Output Reset", "n8n-nodes-base.set", 3.4, (2420, 100), asignaciones([
        ("output", "Listo, reinicié la conversación. ¿En qué le puedo ayudar?", "string"),
    ])))

    # --- rama normal: tipo de mensaje
    add(nodo("Switch Tipo", "n8n-nodes-base.switch", 3.2, (2200, 400), {
        "rules": {"values": [{
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "a1",
                    "leftValue": "={{ ['voice','audio'].includes(" + MSG + ".attachment_type) }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": "audio",
        }]},
        "options": {"fallbackOutput": "extra", "renameFallbackOutput": "texto"},
    }))

    add(nodo("Download Audio", "n8n-nodes-base.httpRequest", 4.2, (2420, 300), {
        "url": "={{ " + MSG + ".attachment_link }}",
        "options": {"response": {"response": {"responseFormat": "file"}}},
    }))
    add(nodo("Transcribir Audio", "@n8n/n8n-nodes-langchain.openAi", 1.8, (2640, 300),
             {"resource": "audio", "operation": "transcribe", "options": {"language": "es"}},
             onError="continueRegularOutput"))
    add(nodo("Set Audio Text", "n8n-nodes-base.set", 3.4, (2860, 300), asignaciones([
        ("content", "={{ ($json.text || '').trim() || '[El cliente envió un audio que no se pudo transcribir]' }}", "string"),
    ])))
    add(nodo("Set Text Content", "n8n-nodes-base.set", 3.4, (2640, 500), asignaciones([
        ("content", "={{ (" + MSG + ".text || '').trim() || ('[El cliente envió un archivo de tipo ' + "
                    + MSG + ".attachment_type + ' sin texto]') }}", "string"),
    ])))

    add(pg(
        "INSERT INTO crm.itvm_buffer (message_id, chat_id, content)\n"
        "VALUES ($1, $2, $3)\nON CONFLICT (message_id) DO NOTHING;",
        "={{ [" + MSG + ".message_id, " + MSG + ".chat_id, $json.content] }}",
        nombre="Guardar en Buffer", pos=(3080, 400)))

    add(nodo("Wait Debounce", "n8n-nodes-base.wait", 1.1, (3300, 400),
             {"amount": "={{ " + CFG + ".segundos_debounce }}", "unit": "seconds"}, webhookId=nid()))

    add(pg(
        "-- Solo la ejecucion del ULTIMO mensaje pendiente del chat reclama el lote.\n"
        "WITH yo AS (\n"
        "  SELECT id FROM crm.itvm_buffer WHERE message_id = $1\n"
        "), ultimo AS (\n"
        "  SELECT max(id) AS id FROM crm.itvm_buffer WHERE chat_id = $2 AND NOT procesado\n"
        ")\n"
        "UPDATE crm.itvm_buffer b\n"
        "SET procesado = true\n"
        "FROM yo, ultimo\n"
        "WHERE b.chat_id = $2 AND NOT b.procesado AND yo.id = ultimo.id\n"
        "RETURNING b.id, b.content;",
        "={{ [" + MSG + ".message_id, " + MSG + ".chat_id] }}",
        nombre="Reclamar Buffer", pos=(3520, 400)))

    add(nodo("Unir Mensajes", "n8n-nodes-base.code", 2, (3740, 400), {
        "jsCode": (
            "// Si esta ejecucion no era la del ultimo mensaje, no llegan filas y se corta.\n"
            "const filas = $input.all().map(i => i.json).filter(j => j && j.id && j.content);\n"
            "if (filas.length === 0) return [];\n"
            "filas.sort((a, b) => Number(a.id) - Number(b.id));\n"
            "const chat_input = filas.map(f => String(f.content).trim()).filter(Boolean).join('\\n');\n"
            "return [{ json: { chat_input } }];"
        )
    }))

    system_message = (
        "=" + prompt
        + "\n\n---\n\n# CONTEXTO DE ESTE MENSAJE\n"
        + "- Fecha y hora actual en Costa Rica: {{ $now.setZone('America/Costa_Rica').setLocale('es').toFormat('cccc d \\'de\\' LLLL \\'de\\' yyyy, HH:mm') }}\n"
        + "- Nombre que figura en el chat: {{ " + MSG + ".author_name || 'desconocido' }}\n"
    )
    add(nodo("Agente ITVM", "@n8n/n8n-nodes-langchain.agent", 1.9, (3960, 400), {
        "promptType": "define",
        "text": "={{ $json.chat_input }}",
        "options": {"systemMessage": system_message, "maxIterations": 8},
    }))
    add(nodo("OpenAI Chat Model", "@n8n/n8n-nodes-langchain.lmChatOpenAi", 1.2, (3820, 640), {
        "model": {"__rl": True, "value": MODELO, "mode": "list", "cachedResultName": MODELO},
        "options": {"temperature": 0.4},
    }, retryOnFail=True, maxTries=3, waitBetweenTries=3000))
    add(nodo("Postgres Chat Memory", "@n8n/n8n-nodes-langchain.memoryPostgresChat", 1.3, (3960, 640), {
        "sessionIdType": "customKey",
        "sessionKey": "={{ " + MSG + ".chat_id }}",
        "tableName": CHAT_HISTORY_TABLE,
        "contextWindowLength": 20,
    }))

    add(tool_workflow(
        "Consultar oferta academica", (4100, 640),
        "Devuelve la informacion oficial de las carreras tecnicas y cursos libres de ITVM: modalidad, "
        "duracion, horario, requisitos, contenido y links (pagina y folleto PDF). Usala SIEMPRE antes de "
        "dar esos datos. Input 'consulta': nombre del programa o tema en pocas palabras (ej 'motos', "
        "'peritaje', 'electricidad residencial', 'diesel'), o 'todos', 'carreras' o 'cursos' para listar.",
        ref_workflow(ids.get("oferta"), "ITVM - Consultar oferta academica"),
        {"consulta": from_ai("consulta", "Programa o tema a consultar, o 'todos' / 'carreras' / 'cursos'")},
    ))
    add(tool_workflow(
        "Consultar informacion adicional", (4240, 640),
        "Devuelve la informacion que el equipo de ITVM actualiza seguido: precios, fechas de inicio, "
        "horarios especificos, promociones, becas, cupos y avisos. Usala SIEMPRE antes de hablar de "
        "precios, costos, matricula, fechas de inicio o promociones, y cuando te pregunten algo que no "
        "este en tus instrucciones.",
        ref_workflow(ids.get("info"), "ITVM - Consultar info adicional"),
        {"tema": from_ai("tema", "Tema que se quiere consultar, en pocas palabras")},
    ))
    add(tool_workflow(
        "Derivar a asesor", (4380, 640),
        "Pasa la conversacion a un asesor humano de admisiones: mueve el lead a la etapa de derivacion, le agrega la "
        "etiqueta de derivado y deja una nota con el resumen. Despues de esto el bot deja de responder "
        "en este chat. Usala cuando la persona quiere matricularse, pide hablar con una persona o visitar "
        "el instituto, es una empresa, o necesita algo que solo resuelve un humano.",
        ref_workflow(ids.get("derivar"), "ITVM - Derivar a asesor"),
        {
            "nombre": from_ai("nombre", "Nombre de la persona, si lo dio. Vacio si no"),
            "programa": from_ai("programa", "Programa de interes, ej 'Tecnico en Peritaje Automotriz'"),
            "horario_preferido": from_ai("horario_preferido", "Horario que prefiere (diurno, nocturno, sabados), si lo dijo"),
            "financiamiento": from_ai("financiamiento", "Si pregunto por financiamiento (CONAPE o propio) y que dijo. Vacio si no"),
            "resumen": from_ai("resumen", "Resumen de 3 a 6 lineas para el asesor: que quiere, si cumple requisitos, dudas pendientes y datos de contacto que dio"),
            "lead_id": "={{ " + MSG + ".element_id }}",
            "kommo_base_url": "={{ " + CFG + ".kommo_base_url }}",
            "pipeline_id": "={{ $('Get Lead').first().json.pipeline_id }}",
            "nombre_etapa_derivado": "={{ " + CFG + ".nombre_etapa_derivado }}",
            "tag_derivado": "={{ " + CFG + ".tag_derivado }}",
            "campo_resumen_lead_id": "={{ " + CFG + ".campo_resumen_lead_id }}",
        },
    ))

    add(nodo("Preparar Respuesta", "n8n-nodes-base.code", 2, (4320, 300), {
        "jsCode": (
            "const lead_id = Number($('Set Campos Mensaje').first().json.element_id) || null;\n"
            "let output = String($json.output || '').trim();\n"
            "if (!output) return [];\n"
            "// Kommo/WhatsApp no renderizan markdown de titulos ni negritas dobles.\n"
            "output = output.replace(/\\*\\*(.+?)\\*\\*/g, '*$1*').replace(/^#+\\s*/gm, '');\n"
            "return [{ json: { output, lead_id } }];"
        )
    }))
    add(nodo("Filter Tiene Lead", "n8n-nodes-base.filter", 2.2, (4540, 300), filtro([
        cond_bool("c1", "={{ !!$json.lead_id }}"),
    ])))
    # La respuesta se guarda en un campo del LEAD (cada lead tiene el suyo: no hay cruces entre chats)
    # y el Salesbot envia ese campo por el chat del lead.
    add(nodo("Guardar Respuesta en Lead", "n8n-nodes-base.httpRequest", 4.2, (4760, 300), http_kommo(
        "PATCH", "=" + BASE + "/api/v4/leads/{{ $json.lead_id }}",
        "={{ JSON.stringify({ custom_fields_values: [{ field_id: Number(" + CFG
        + ".campo_respuesta_lead_id), values: [{ value: $json.output }] }] }) }}")))
    add(espera("Wait Propagacion", (4980, 300), 2))
    add(nodo("Run Salesbot", "n8n-nodes-base.httpRequest", 4.2, (5200, 300), http_kommo(
        "POST", "=" + BASE + "/api/v2/salesbot/run",
        "={{ JSON.stringify([{ bot_id: Number(" + CFG + ".salesbot_id), entity_id: Number($('Preparar Respuesta').first().json.lead_id), entity_type: 2 }]) }}")))

    # conexiones
    for a, b in [
        ("Webhook Kommo", "Config ITVM"), ("Config ITVM", "Set Campos Mensaje"),
        ("Set Campos Mensaje", "Idempotencia"), ("Idempotencia", "Filter Mensaje Nuevo"),
        ("Filter Mensaje Nuevo", "Filter Mensaje Valido"), ("Filter Mensaje Valido", "Wait Inicial 2s"),
        ("Wait Inicial 2s", "Get Lead"), ("Get Lead", "Filter Bot Activo"),
        ("Filter Bot Activo", "Switch /reset"),
        ("Reset Memoria", "Set Output Reset"), ("Set Output Reset", "Preparar Respuesta"),
        ("Download Audio", "Transcribir Audio"), ("Transcribir Audio", "Set Audio Text"),
        ("Set Audio Text", "Guardar en Buffer"), ("Set Text Content", "Guardar en Buffer"),
        ("Guardar en Buffer", "Wait Debounce"), ("Wait Debounce", "Reclamar Buffer"),
        ("Reclamar Buffer", "Unir Mensajes"), ("Unir Mensajes", "Agente ITVM"),
        ("Agente ITVM", "Preparar Respuesta"), ("Preparar Respuesta", "Filter Tiene Lead"),
        ("Filter Tiene Lead", "Guardar Respuesta en Lead"),
        ("Guardar Respuesta en Lead", "Wait Propagacion"), ("Wait Propagacion", "Run Salesbot"),
    ]:
        conectar(C, a, b)
    conectar(C, "Switch /reset", "Reset Memoria", 0)
    conectar(C, "Switch /reset", "Switch Tipo", 1)
    conectar(C, "Switch Tipo", "Download Audio", 0)
    conectar(C, "Switch Tipo", "Set Text Content", 1)
    conectar(C, "OpenAI Chat Model", "Agente ITVM", tipo="ai_languageModel")
    conectar(C, "Postgres Chat Memory", "Agente ITVM", tipo="ai_memory")
    for t in ["Consultar oferta academica", "Consultar informacion adicional", "Derivar a asesor"]:
        conectar(C, t, "Agente ITVM", tipo="ai_tool")

    return workflow("ITVM - Chat Kommo", N, C)


# ---------------------------------------------------------------------------
# 2) Subworkflow: Consultar oferta academica
# ---------------------------------------------------------------------------
JS_OFERTA = r"""
const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
const consulta = norm($('When Executed by Another Workflow').first().json.consulta);
const programas = $input.all().map(i => i.json).filter(p => p && p.slug);

const resumen = p => ({ nombre: p.nombre, tipo: p.tipo, modalidad: p.modalidad, duracion: p.duracion, url_info: p.url_info });
const detalle = p => ({
  nombre: p.nombre, tipo: p.tipo, acreditacion: p.acreditacion, modalidad: p.modalidad,
  duracion: p.duracion, horario: p.horario || 'Consultar con asesor', requisitos: p.requisitos || 'Consultar con asesor',
  dirigido_a: p.dirigido_a, contenido: p.contenido, inversion: p.inversion || 'Ver informacion adicional o consultar con asesor',
  notas: p.notas, url_info: p.url_info, url_folleto: p.url_folleto,
});

if (programas.length === 0) {
  return [{ json: { ok: false, nota: 'No se pudo leer la oferta academica. No inventes datos: ofrece que un asesor le confirme.' } }];
}

const listar = /^(todos?|todas?|lista|listado|oferta|que tienen|que ofrecen|opciones|)$/.test(consulta);
const soloCarreras = /^(carreras?|tecnicos?|carreras tecnicas)$/.test(consulta);
const soloCursos = /^(cursos?|cursos libres?|capacitacion(es)?)$/.test(consulta);
if (listar || soloCarreras || soloCursos) {
  let lista = programas;
  if (soloCarreras) lista = programas.filter(p => p.tipo === 'tecnico');
  if (soloCursos) lista = programas.filter(p => p.tipo !== 'tecnico');
  return [{ json: { ok: true, total: lista.length, programas: lista.map(resumen) } }];
}

const vacias = new Set(['de','del','la','el','los','las','en','y','o','para','un','una','curso','cursos','carrera','carreras','tecnico','tecnica','info','informacion','precio','requisitos','horario','horarios']);
const palabras = consulta.split(/[^a-z0-9]+/).filter(w => w.length > 1 && !vacias.has(w));

const puntuados = programas.map(p => {
  const texto = norm([p.nombre, p.slug.replace(/-/g, ' '), p.palabras_clave].join(' '));
  let score = 0;
  if (texto.includes(consulta)) score += 10;
  for (const w of palabras) if (texto.includes(w)) score += (w.length > 3 ? 2 : 1);
  return { p, score };
}).filter(x => x.score > 0).sort((a, b) => b.score - a.score || (a.p.orden - b.p.orden));

if (puntuados.length === 0) {
  return [{ json: { ok: true, total: 0, nota: 'No hay un programa que coincida con esa busqueda. Estos son los programas disponibles; no ofrezcas otros.', programas: programas.map(resumen) } }];
}
const top = puntuados[0].score;
const elegidos = puntuados.filter(x => x.score >= top / 2).slice(0, 3).map(x => detalle(x.p));
return [{ json: { ok: true, total: elegidos.length, programas: elegidos } }];
""".strip()


def wf_oferta():
    N, C = [], {}
    N.append(trigger_subworkflow((0, 300), ["consulta"]))
    N.append(pg(
        "SELECT slug, nombre, tipo, acreditacion, modalidad, duracion, horario, requisitos, dirigido_a,\n"
        "       contenido, inversion, notas, url_info, url_folleto, palabras_clave, orden\n"
        "FROM crm.itvm_programas\nWHERE activo\nORDER BY orden;",
        nombre="Leer Programas", pos=(220, 300), alwaysOutputData=True, onError="continueRegularOutput"))
    N.append(nodo("Buscar Programa", "n8n-nodes-base.code", 2, (440, 300), {"jsCode": JS_OFERTA}))
    conectar(C, "When Executed by Another Workflow", "Leer Programas")
    conectar(C, "Leer Programas", "Buscar Programa")
    return workflow("ITVM - Consultar oferta academica", N, C)


# ---------------------------------------------------------------------------
# 3) Subworkflow: Consultar info adicional
# ---------------------------------------------------------------------------
def wf_info():
    N, C = [], {}
    N.append(trigger_subworkflow((0, 300), ["tema"]))
    N.append(pg(
        "SELECT notas_adicionales, actualizado_en FROM crm.itvm_bot_config WHERE id = 1;",
        nombre="Leer Info Adicional", pos=(220, 300), alwaysOutputData=True, onError="continueRegularOutput"))
    N.append(nodo("Formatear Info", "n8n-nodes-base.code", 2, (440, 300), {"jsCode": (
        "const j = $input.first().json || {};\n"
        "const texto = String(j.notas_adicionales || '').trim();\n"
        "if (!texto) {\n"
        "  return [{ json: { ok: false, nota: 'No hay informacion adicional cargada. No inventes precios ni fechas: ofrece que un asesor lo confirme.' } }];\n"
        "}\n"
        "return [{ json: { ok: true, actualizado_en: j.actualizado_en, informacion: texto.slice(0, 15000) } }];"
    )}))
    conectar(C, "When Executed by Another Workflow", "Leer Info Adicional")
    conectar(C, "Leer Info Adicional", "Formatear Info")
    return workflow("ITVM - Consultar info adicional", N, C)


# ---------------------------------------------------------------------------
# 4) Subworkflow: Derivar a asesor
# ---------------------------------------------------------------------------
def wf_derivar():
    N, C = [], {}
    entradas = ["nombre", "programa", "horario_preferido", "financiamiento", "resumen",
                "lead_id", "kommo_base_url", "pipeline_id", "nombre_etapa_derivado", "tag_derivado",
                "campo_resumen_lead_id"]
    N.append(trigger_subworkflow((0, 300), entradas))
    # Cada asesor tiene su embudo: se busca la etapa de derivacion POR NOMBRE dentro del embudo del lead.
    N.append(nodo("Get Etapas", "n8n-nodes-base.httpRequest", 4.2, (220, 300), http_kommo(
        "GET", "={{ String($json.kommo_base_url).replace(/\\/$/, '') }}/api/v4/leads/pipelines/{{ $json.pipeline_id }}/statuses"),
        onError="continueRegularOutput", alwaysOutputData=True))
    N.append(nodo("Armar Cambios", "n8n-nodes-base.code", 2, (440, 300), {"jsCode": (
        "const i = $('When Executed by Another Workflow').first().json;\n"
        "const limpio = v => String(v || '').trim();\n"
        "const norm = v => limpio(v).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');\n"
        "const body = { tags_to_add: [{ name: limpio(i.tag_derivado) || 'ITVM-derivado' }] };\n"
        "const etapas = (($input.first().json || {})._embedded || {}).statuses || [];\n"
        "const etapa = etapas.find(e => norm(e.name) === norm(i.nombre_etapa_derivado));\n"
        "if (etapa) body.status_id = etapa.id;\n"
        "const campoResumen = Number(i.campo_resumen_lead_id) || 0;\n"
        "const textoResumen = [limpio(i.programa) && ('Programa: ' + limpio(i.programa)), limpio(i.horario_preferido) && ('Horario: ' + limpio(i.horario_preferido)), limpio(i.financiamiento) && ('Financiamiento: ' + limpio(i.financiamiento)), limpio(i.resumen)].filter(Boolean).join('\\n');\n"
        "if (campoResumen > 0 && textoResumen) body.custom_fields_values = [{ field_id: campoResumen, values: [{ value: textoResumen }] }];\n"
        "const lineas = [\n"
        "  'Derivado por el asistente IA de ITVM',\n"
        "  limpio(i.nombre) && ('Nombre: ' + limpio(i.nombre)),\n"
        "  limpio(i.programa) && ('Programa: ' + limpio(i.programa)),\n"
        "  limpio(i.horario_preferido) && ('Horario preferido: ' + limpio(i.horario_preferido)),\n"
        "  limpio(i.financiamiento) && ('Financiamiento: ' + limpio(i.financiamiento)),\n"
        "  limpio(i.resumen) && ('Resumen:\\n' + limpio(i.resumen)),\n"
        "].filter(Boolean);\n"
        "const base = limpio(i.kommo_base_url).replace(/\\/$/, '');\n"
        "return [{ json: { base, lead_id: limpio(i.lead_id), body, nota: lineas.join('\\n') } }];"
    )}))
    N.append(nodo("Actualizar Lead", "n8n-nodes-base.httpRequest", 4.2, (660, 300), http_kommo(
        "PATCH", "={{ $json.base }}/api/v4/leads/{{ $json.lead_id }}",
        "={{ JSON.stringify($json.body) }}"), onError="continueErrorOutput"))
    N.append(nodo("Agregar Nota", "n8n-nodes-base.httpRequest", 4.2, (880, 200), http_kommo(
        "POST", "={{ $('Armar Cambios').first().json.base }}/api/v4/leads/{{ $('Armar Cambios').first().json.lead_id }}/notes",
        "={{ JSON.stringify([{ note_type: 'common', params: { text: $('Armar Cambios').first().json.nota } }]) }}"),
        onError="continueRegularOutput"))
    N.append(nodo("Resultado OK", "n8n-nodes-base.set", 3.4, (1100, 200), asignaciones([
        ("ok", "true", "boolean"),
        ("mensaje", "Listo: el lead quedo derivado a un asesor. Despedite confirmando que un asesor le contacta y el horario de atencion.", "string"),
    ])))
    N.append(nodo("Resultado Error", "n8n-nodes-base.set", 3.4, (880, 420), asignaciones([
        ("ok", "false", "boolean"),
        ("mensaje", "No se pudo registrar la derivacion en el CRM. Igual decile a la persona que un asesor le contacta, sin mencionar el error.", "string"),
    ])))
    conectar(C, "When Executed by Another Workflow", "Get Etapas")
    conectar(C, "Get Etapas", "Armar Cambios")
    conectar(C, "Armar Cambios", "Actualizar Lead")
    conectar(C, "Actualizar Lead", "Agregar Nota", 0)
    conectar(C, "Actualizar Lead", "Resultado Error", 1)
    conectar(C, "Agregar Nota", "Resultado OK")
    return workflow("ITVM - Derivar a asesor", N, C)


# ---------------------------------------------------------------------------
# 5) Sync Planilla (Google Sheets -> itvm_bot_config + itvm_programas) + limpieza
# ---------------------------------------------------------------------------
SHEET_ID = "1YZqpfdGdRLp2OH683OvN3NZUjd0D_N27"

# hoja, rango (desde la fila de encabezados), primer encabezado esperado (valida que la hoja exista:
# si el nombre no existe, Google devuelve la PRIMERA hoja sin avisar).
HOJAS = [
    ("Datos generales", "A4:C60", "Dato"),
    ("Programas", "A4:I80", "Nombre del programa"),
    ("Precios", "A4:G200", "Programa"),
    ("Horarios e inicios", "A4:H200", "Programa"),
    ("Promociones", "A4:G80", "Promoción"),
    ("Preguntas frecuentes", "A4:B120", "Pregunta"),
]

JS_PROCESAR_PLANILLA = r"""
// Convierte las pestañas de la planilla en:
//  - notas: texto que lee la tool "Consultar informacion adicional"
//  - programas: filas para actualizar crm.itvm_programas
const HOJAS = $('Hojas').all().map(i => i.json);
const respuestas = $input.all().map(i => i.json);

function parseCSV(texto) {
  const filas = []; let fila = []; let campo = ''; let comillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (comillas) {
      if (c === '"') { if (texto[i + 1] === '"') { campo += '"'; i++; } else comillas = false; }
      else campo += c;
    } else if (c === '"') comillas = true;
    else if (c === ',') { fila.push(campo); campo = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && texto[i + 1] === '\n') i++;
      fila.push(campo); filas.push(fila); fila = []; campo = '';
    } else campo += c;
  }
  if (campo !== '' || fila.length) { fila.push(campo); filas.push(fila); }
  return filas;
}
const limpio = v => String(v == null ? '' : v).replace(/\s+/g, ' ').trim();
const esEjemplo = fila => fila.some(v => /^EJEMPLO\b/i.test(limpio(v)));
// Filas de ejemplo que vinieron precargadas en la plantilla y no tienen la marca EJEMPLO.
const EJEMPLOS_PLANTILLA = new Set(['matrícula gratis enero']);

const tablas = {}; const errores = [];
HOJAS.forEach((h, idx) => {
  const r = respuestas[idx] || {};
  const data = typeof r.data === 'string' ? r.data : '';
  const filas = parseCSV(data);
  if (!filas.length || limpio(filas[0][0]) !== h.encabezado) { errores.push(h.hoja); return; }
  const enc = filas[0].map(limpio);
  tablas[h.hoja] = filas.slice(1)
    .filter(f => f.some(v => limpio(v) !== ''))
    .map(f => Object.fromEntries(enc.map((k, i) => [k, limpio(f[i])])));
});
if (errores.length) {
  return [{ json: { ok: false, errores, hojas_ok: HOJAS.length - errores.length } }];
}

const out = [];
// --- Datos generales
const dg = tablas['Datos generales'].filter(r => r['Dato'] && r['Valor']);
if (dg.length) {
  out.push('# DATOS GENERALES DE ITVM');
  for (const r of dg) out.push(`- ${r['Dato']}: ${r['Valor']}`);
}

// --- Precios
const precios = tablas['Precios'].filter(r => r['Programa'] && r['Monto (₡)'] && !esEjemplo(Object.values(r)) && !/vencid/i.test(r['Estado']));
out.push('', '# PRECIOS VIGENTES (en colones)');
if (!precios.length) out.push('No hay precios cargados: el precio lo confirma un asesor.');
const porPrograma = {};
for (const r of precios) (porPrograma[r['Programa']] = porPrograma[r['Programa']] || []).push(r);
for (const [prog, filas] of Object.entries(porPrograma)) {
  out.push(`## ${prog}`);
  for (const r of filas) {
    let monto = r['Monto (₡)']; if (!/₡/.test(monto)) monto = '₡' + monto;
    out.push(`- ${r['Concepto'] || 'Precio'}: ${monto}` + (r['Detalle'] ? ` (${r['Detalle']})` : '') + (r['Vigente hasta'] ? ` — vigente hasta ${r['Vigente hasta']}` : ''));
  }
}

// --- Horarios e inicios
const horarios = tablas['Horarios e inicios'].filter(r => r['Programa'] && !esEjemplo(Object.values(r)));
out.push('', '# HORARIOS Y PRÓXIMOS INICIOS');
if (!horarios.length) out.push('No hay grupos cargados: horarios y fechas de inicio los confirma un asesor.');
for (const r of horarios) {
  const partes = [r['Jornada'], r['Días'], (r['Hora inicio'] && r['Hora fin']) ? `${r['Hora inicio']} a ${r['Hora fin']}` : (r['Hora inicio'] || '')].filter(Boolean).join(', ');
  out.push(`- ${r['Programa']}: ${partes || 'horario a confirmar'}`
    + (r['Fecha de inicio'] ? `. Inicio: ${r['Fecha de inicio']}` : '. Fecha de inicio: a confirmar con asesor')
    + (r['Cupos'] ? `. Cupos: ${r['Cupos']}` : '')
    + (r['Notas'] ? `. ${r['Notas']}` : ''));
}

// --- Promociones
const promos = tablas['Promociones'].filter(r => r['Promoción'] && !esEjemplo(Object.values(r))
  && !EJEMPLOS_PLANTILLA.has(r['Promoción'].toLowerCase()) && !/vencid/i.test(r['Estado']));
out.push('', '# PROMOCIONES Y BECAS');
if (!promos.length) out.push('No hay promociones vigentes. No ofrezcas descuentos.');
for (const r of promos) {
  const proxima = /pr[oó]xima/i.test(r['Estado']);
  out.push(`- ${r['Promoción']}${proxima ? ' (todavía no empezó)' : ''}: ${r['Qué incluye']}`
    + (r['Aplica a'] ? `. Aplica a: ${r['Aplica a']}` : '')
    + (r['Desde'] ? `. Desde: ${r['Desde']}` : '') + (r['Hasta'] ? `. Hasta: ${r['Hasta']}` : '')
    + (r['Condiciones'] ? `. Condiciones: ${r['Condiciones']}` : ''));
}

// --- Preguntas frecuentes
const faq = tablas['Preguntas frecuentes'].filter(r => r['Pregunta'] && r['Respuesta'] && !esEjemplo(Object.values(r)));
if (faq.length) {
  out.push('', '# PREGUNTAS FRECUENTES (responder con este contenido)');
  for (const r of faq) out.push(`- P: ${r['Pregunta']}\n  R: ${r['Respuesta']}`);
}

// --- Programas
const TIPOS = { 'carrera tecnica': 'tecnico', 'curso libre': 'curso_libre', 'capacitacion': 'capacitacion' };
const norm = v => limpio(v).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const sinMarcas = v => limpio(String(v || '').replace(/\s*\(\s*VERIFICAR\b[^)]*\)/gi, '').replace(/^FALTA[^.]*\.?/i, ''));
const programas = tablas['Programas'].filter(r => r['Nombre del programa']).map((r, i) => {
  const acred = limpio(r['Acreditado INA']);
  return {
    nombre: r['Nombre del programa'],
    slug: norm(r['Nombre del programa']).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    tipo: TIPOS[norm(r['Tipo'])] || 'curso_libre',
    activo: norm(r['Activo']) !== 'no',
    acreditacion: (!acred || norm(acred) === 'no') ? null : (/^s[ií](\s|$)/i.test(acred) ? ('Acreditada por el INA ' + acred.replace(/^s[ií]\s*/i, '')).trim() : acred),
    modalidad: sinMarcas(r['Modalidad']) || null,
    duracion: sinMarcas(r['Duración']) || null,
    requisitos: sinMarcas(r['Requisitos de ingreso']) || null,
    notas: sinMarcas(r['Notas para el asistente']) || null,
    url_folleto: /^https?:\/\//.test(r['Link del folleto']) ? r['Link del folleto'] : null,
    orden: (i + 1) * 10,
  };
});

const notas = out.join('\n').trim();
return [{ json: { ok: true, hojas_ok: HOJAS.length, notas, largo: notas.length, programas, n_programas: programas.length } }];
""".strip()

SQL_PROGRAMAS = """
WITH datos AS (
  SELECT * FROM jsonb_to_recordset($1::jsonb) AS d(
    nombre text, slug text, tipo text, activo boolean, acreditacion text, modalidad text,
    duracion text, requisitos text, notas text, url_folleto text, orden int)
), actualizados AS (
  UPDATE crm.itvm_programas p SET
    tipo = d.tipo,
    activo = d.activo,
    acreditacion = d.acreditacion,
    modalidad = COALESCE(d.modalidad, p.modalidad),
    duracion = COALESCE(d.duracion, p.duracion),
    requisitos = COALESCE(d.requisitos, p.requisitos),
    notas = COALESCE(d.notas, p.notas),
    url_folleto = COALESCE(d.url_folleto, p.url_folleto),
    orden = d.orden,
    actualizado_en = now()
  FROM datos d
  WHERE lower(p.nombre) = lower(d.nombre)
  RETURNING p.id
), nuevos AS (
  INSERT INTO crm.itvm_programas
    (slug, nombre, tipo, activo, acreditacion, modalidad, duracion, requisitos, notas, url_folleto, palabras_clave, orden)
  SELECT d.slug, d.nombre, d.tipo, d.activo, d.acreditacion, d.modalidad, d.duracion, d.requisitos,
         d.notas, d.url_folleto, replace(d.slug, '-', ' '), d.orden
  FROM datos d
  WHERE NOT EXISTS (SELECT 1 FROM crm.itvm_programas p WHERE lower(p.nombre) = lower(d.nombre))
  ON CONFLICT (slug) DO NOTHING
  RETURNING id
), desactivados AS (
  -- Programas que ya no estan en la planilla: se dejan de ofrecer.
  UPDATE crm.itvm_programas p SET activo = false, actualizado_en = now()
  WHERE p.activo AND lower(p.nombre) NOT IN (SELECT lower(nombre) FROM datos)
  RETURNING p.id
)
SELECT (SELECT count(*) FROM actualizados) AS actualizados,
       (SELECT count(*) FROM nuevos) AS nuevos,
       (SELECT count(*) FROM desactivados) AS desactivados;
""".strip()


def wf_sync_planilla():
    N, C = [], {}
    N.append(nodo("Cada 2 horas", "n8n-nodes-base.scheduleTrigger", 1.2, (0, 300),
                  {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6-22/2 * * *"}]}}))
    N.append(nodo("Hojas", "n8n-nodes-base.code", 2, (220, 300), {"jsCode": (
        "// ID de la planilla de Google Sheets (debe estar compartida: 'cualquier persona con el enlace').\n"
        "const sheet_id = '" + SHEET_ID + "';\n"
        "return " + json.dumps([{"hoja": h, "rango": r, "encabezado": e} for h, r, e in HOJAS], ensure_ascii=False)
        + ".map(h => ({ json: { ...h, sheet_id } }));"
    )}))
    N.append(nodo("Leer Hoja", "n8n-nodes-base.httpRequest", 4.2, (440, 300), {
        "url": "=https://docs.google.com/spreadsheets/d/{{ $json.sheet_id }}/gviz/tq",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "tqx", "value": "out:csv"},
            {"name": "sheet", "value": "={{ $json.hoja }}"},
            {"name": "range", "value": "={{ $json.rango }}"},
            {"name": "headers", "value": "1"},
        ]},
        "options": {"response": {"response": {"responseFormat": "text"}}},
    }, retryOnFail=True, maxTries=3, waitBetweenTries=5000, onError="continueRegularOutput"))
    N.append(nodo("Procesar Planilla", "n8n-nodes-base.code", 2, (660, 300), {"jsCode": JS_PROCESAR_PLANILLA}))
    N.append(nodo("Filter Planilla OK", "n8n-nodes-base.filter", 2.2, (880, 300), filtro([
        # Si alguna hoja fallo, no se pisa la informacion buena que ya esta en la base.
        cond_bool("p1", "={{ $json.ok === true && $json.largo >= 100 }}"),
    ])))
    N.append(pg(
        "INSERT INTO crm.itvm_bot_config (id, notas_adicionales, actualizado_en)\n"
        "VALUES (1, $1, now())\n"
        "ON CONFLICT (id) DO UPDATE SET notas_adicionales = EXCLUDED.notas_adicionales, actualizado_en = now();",
        "={{ [$json.notas] }}",
        nombre="Guardar Info", pos=(1100, 300)))
    N.append(nodo("Filter Hay Programas", "n8n-nodes-base.filter", 2.2, (1320, 300), filtro([
        cond_bool("p2", "={{ $('Procesar Planilla').first().json.n_programas > 0 }}"),
    ])))
    N.append(pg(SQL_PROGRAMAS, "={{ [JSON.stringify($('Procesar Planilla').first().json.programas)] }}",
                nombre="Guardar Programas", pos=(1540, 300)))
    N.append(pg(
        "DELETE FROM crm.itvm_buffer WHERE creado_en < now() - interval '7 days';\n"
        "DELETE FROM crm.itvm_processed_messages WHERE creado_en < now() - interval '30 days';",
        nombre="Limpiar Tablas", pos=(220, 520)))
    conectar(C, "Cada 2 horas", "Hojas")
    conectar(C, "Cada 2 horas", "Limpiar Tablas")
    conectar(C, "Hojas", "Leer Hoja")
    conectar(C, "Leer Hoja", "Procesar Planilla")
    conectar(C, "Procesar Planilla", "Filter Planilla OK")
    conectar(C, "Filter Planilla OK", "Guardar Info")
    conectar(C, "Guardar Info", "Filter Hay Programas")
    conectar(C, "Filter Hay Programas", "Guardar Programas")
    w = workflow("ITVM - Sync Planilla", N, C)
    w["settings"]["timezone"] = "America/Costa_Rica"
    return w


# ---------------------------------------------------------------------------
# 6) Setup DB: crea las tablas y carga los programas (se ejecuta una vez a mano)
# ---------------------------------------------------------------------------
def wf_setup_db():
    sql = "\n\n".join((RAIZ / "sql" / f).read_text(encoding="utf-8")
                       for f in ["001_esquema.sql", "002_programas_seed.sql"])
    N, C = [], {}
    N.append(nodo("Ejecutar una vez", "n8n-nodes-base.manualTrigger", 1, (0, 300), {}))
    N.append(pg(sql, nombre="Crear Tablas y Programas", pos=(220, 300)))
    N.append(pg(
        "SELECT (SELECT count(*) FROM crm.itvm_programas) AS programas,\n"
        "       (SELECT count(*) FROM crm.itvm_bot_config) AS config,\n"
        "       to_regclass('crm.itvm_buffer') IS NOT NULL AS buffer_ok,\n"
        "       to_regclass('crm.itvm_processed_messages') IS NOT NULL AS idempotencia_ok;",
        nombre="Verificar", pos=(440, 300)))
    conectar(C, "Ejecutar una vez", "Crear Tablas y Programas")
    conectar(C, "Crear Tablas y Programas", "Verificar")
    return workflow("ITVM - Setup DB", N, C)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nombre-agente", default="Sofía")
    ap.add_argument("--id-oferta", default="")
    ap.add_argument("--id-info", default="")
    ap.add_argument("--id-derivar", default="")
    a = ap.parse_args()

    prompt = (RAIZ / "prompts" / "agente-itvm.md").read_text(encoding="utf-8").strip()
    if "{{" in prompt or "}}" in prompt:
        raise SystemExit("El prompt no puede contener '{{' ni '}}' (n8n lo interpretaria como expresion).")
    prompt = prompt.replace("__NOMBRE_AGENTE__", a.nombre_agente)

    ids = {"oferta": a.id_oferta, "info": a.id_info, "derivar": a.id_derivar}
    SALIDA.mkdir(exist_ok=True)
    for wf in [wf_chat(prompt, ids), wf_oferta(), wf_info(), wf_derivar(), wf_sync_planilla(), wf_setup_db()]:
        destino = SALIDA / (wf["name"] + ".json")
        destino.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("generado:", destino.relative_to(RAIZ))


if __name__ == "__main__":
    main()
