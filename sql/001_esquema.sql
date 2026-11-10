-- ITVM - Agente IA Kommo
-- Esquema de base de datos (PostgreSQL). Idempotente: se puede correr varias veces.
-- Las tablas llevan prefijo itvm_ para poder convivir con otros bots en la misma base.

CREATE SCHEMA IF NOT EXISTS crm;

-- 1) Idempotencia: Kommo puede reenviar el mismo webhook. Cada message_id se procesa una sola vez.
CREATE TABLE IF NOT EXISTS crm.itvm_processed_messages (
  message_id  text PRIMARY KEY,
  chat_id     text,
  creado_en   timestamptz NOT NULL DEFAULT now()
);

-- 2) Buffer de mensajes (debounce). Reemplaza a Redis.
--    Cada mensaje entrante se inserta aca; despues de la espera, SOLO la ejecucion
--    del ultimo mensaje del chat "reclama" (UPDATE ... RETURNING) todos los pendientes
--    en una sola sentencia atomica. Asi no se pierden mensajes que llegan en el medio.
CREATE TABLE IF NOT EXISTS crm.itvm_buffer (
  id          bigserial PRIMARY KEY,
  message_id  text NOT NULL UNIQUE,
  chat_id     text NOT NULL,
  content     text NOT NULL,
  procesado   boolean NOT NULL DEFAULT false,
  creado_en   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS itvm_buffer_pendientes_idx
  ON crm.itvm_buffer (chat_id, id) WHERE NOT procesado;

-- 3) Informacion editable por el equipo de ITVM.
--    notas_adicionales: planilla (precios, horarios, promos, FAQ). instrucciones: Google Doc.
--    Las llena el workflow "ITVM - Sync Planilla".
CREATE TABLE IF NOT EXISTS crm.itvm_bot_config (
  id                 int PRIMARY KEY,
  notas_adicionales  text,
  actualizado_en     timestamptz
);
-- Instrucciones del negocio (nombre, tono, que hacer, info extra): vienen del Google Doc de ITVM.
ALTER TABLE crm.itvm_bot_config ADD COLUMN IF NOT EXISTS instrucciones text;
ALTER TABLE crm.itvm_bot_config ADD COLUMN IF NOT EXISTS instrucciones_actualizado_en timestamptz;
INSERT INTO crm.itvm_bot_config (id, notas_adicionales, actualizado_en)
VALUES (1, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- 4) Oferta academica (carreras tecnicas y cursos libres).
CREATE TABLE IF NOT EXISTS crm.itvm_programas (
  id                serial PRIMARY KEY,
  slug              text NOT NULL UNIQUE,
  nombre            text NOT NULL,
  tipo              text NOT NULL CHECK (tipo IN ('tecnico', 'curso_libre', 'capacitacion')),
  acreditacion      text,           -- ej: 'Acreditada por el INA (resolucion 2026-02)'
  modalidad         text,
  duracion          text,
  horario           text,           -- NULL = consultar con asesor
  requisitos        text,
  dirigido_a        text,
  contenido         text,
  inversion         text,           -- NULL = el precio lo confirma el asesor / Google Doc
  notas             text,           -- detalles extra que el agente puede usar
  url_info          text,
  url_folleto       text,
  palabras_clave    text,           -- sinonimos para la busqueda (sin tildes, minusculas)
  orden             int NOT NULL DEFAULT 100,
  activo            boolean NOT NULL DEFAULT true,
  actualizado_en    timestamptz NOT NULL DEFAULT now()
);

-- La memoria del agente (tabla public.itvm_chat_histories) la crea n8n automaticamente
-- la primera vez que corre el nodo "Postgres Chat Memory".
