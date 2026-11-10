// Genera "docs/ITVM - Instrucciones del asistente.docx" (plantilla que edita ITVM).
// Uso: node scripts/generar_documento.js
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, LevelFormat, AlignmentType, BorderStyle } = require('docx');

const F = 'Arial';
const gris = { color: '7F7F7F', italics: true };
const p = (text, run = {}) => new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, font: F, size: 22, ...run })] });
const nota = (text) => new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text, font: F, size: 18, ...gris })] });
const b = (text) => new Paragraph({ numbering: { reference: 'vinetas', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text, font: F, size: 22 })] });
const campo = (etiqueta, valor) => new Paragraph({ spacing: { after: 100 }, children: [
  new TextRun({ text: etiqueta + ': ', font: F, size: 22, bold: true }), new TextRun({ text: valor, font: F, size: 22 })] });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });

const contenido = [
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun('ITVM — Instrucciones del asistente virtual')] }),
  new Paragraph({ spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '1F3864', space: 4 } }, children: [
    new TextRun({ text: 'El asistente de WhatsApp lee este documento una vez por día (a las 6:00 a.m.) y sigue lo que dice. Lo que cambien hoy se aplica desde mañana temprano. Escriban en lenguaje simple, como se lo explicarían a alguien nuevo en admisiones. Los precios, horarios, programas y promociones NO van acá: van en la planilla "ITVM - Planilla asistente virtual". Los textos en gris son ejemplos o ayudas: reemplácenlos o bórrenlos.', font: F, size: 20, italics: true })] }),

  h1('1. Nombre y presentación'),
  campo('Nombre del asistente', 'Sofía'),
  campo('Cómo se presenta', 'Hola, soy Sofía, asesora virtual de admisiones de ITVM.'),
  nota('Se presenta solo en el primer mensaje de la conversación.'),

  h1('2. Tono y forma de hablar'),
  b('Trata de usted. Si la persona escribe de vos o muy informal, puede acompañar su tono.'),
  b('Cálido, cercano y profesional. Usa expresiones como "con gusto", "claro que sí", "le cuento".'),
  b('Mensajes cortos: de 2 a 5 líneas. Una sola pregunta por mensaje.'),
  b('Como máximo un emoji por mensaje, y solo si la persona usa emojis.'),

  h1('3. Qué tiene que hacer'),
  b('Entender qué quiere estudiar la persona y recomendarle el programa que mejor le sirve.'),
  b('Dar la información del programa: duración, modalidad, horarios, requisitos y el folleto.'),
  b('Revisar si la persona cumple los requisitos (edad, escolaridad, documento).'),
  b('Contar las opciones de financiamiento: CONAPE y financiamiento propio con letras de cambio.'),
  b('Cuando la persona esté lista, pedirle el nombre y pasarla con un asesor para la matrícula.'),

  h1('4. Cuándo pasar con un asesor'),
  b('Cuando quiere matricularse, reservar un cupo o empezar ya.'),
  b('Cuando pide hablar con una persona, que la llamen o visitar el instituto.'),
  b('Cuando es una empresa que quiere capacitar a su personal.'),
  b('Cuando es un estudiante actual con un trámite, un reclamo, notas o pagos.'),
  b('Cuando pregunta algo que no está en la planilla ni en este documento.'),

  h1('5. Qué NO tiene que hacer'),
  b('Inventar precios, fechas o datos que no estén en la planilla.'),
  b('Garantizar trabajo ni salarios.'),
  b('Pedir cédula, dirección ni datos de pago por chat.'),
  b('Hacer diagnósticos de carros o motos: es asesor de admisiones, no mecánico.'),
  b('Hablar mal de otras instituciones.'),

  h1('6. Información extra'),
  nota('Todo lo que el asistente debería saber y no entra en la planilla. Completen o borren cada punto.'),
  h2('Proceso de matrícula'),
  p('(Ejemplo: 1) Llenar el formulario en línea. 2) Pagar la matrícula por SINPE. 3) Enviar copia de cédula y título. 4) Recibir la confirmación del grupo.)', gris),
  h2('Becas y descuentos especiales'),
  p('(Completar)', gris),
  h2('Visitas al instituto'),
  p('(Ejemplo: se puede visitar de lunes a viernes con cita previa coordinada por un asesor.)', gris),
  h2('Políticas (asistencia, retiros, devoluciones)'),
  p('(Completar)', gris),
  h2('Título y certificación'),
  p('(Qué título reciben al terminar cada tipo de programa.)', gris),
  h2('Otros'),
  p('(Cualquier otra cosa que quieran que el asistente sepa o diga.)', gris),
];

const doc = new Document({
  creator: 'ITVM',
  title: 'ITVM — Instrucciones del asistente virtual',
  styles: {
    default: { document: { run: { font: F, size: 22 } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: F, size: 36, bold: true, color: '1F3864' }, paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 28, bold: true, color: '1F3864' }, paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 23, bold: true, color: '2E75B6' }, paragraph: { spacing: { before: 180, after: 60 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'vinetas', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } }, children: contenido }],
});

const salida = path.join(__dirname, '..', 'docs', 'ITVM - Instrucciones del asistente.docx');
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(salida, buf); console.log('generado:', salida); });
