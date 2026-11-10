#!/usr/bin/env python3
"""Genera la planilla que completa ITVM. Uso: python3 scripts/generar_planilla.py "docs/ITVM - Planilla asistente virtual.xlsx" """
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment

OUT = sys.argv[1]
F = 'Arial'
AZUL = '1F3864'
AMARILLO = PatternFill('solid', fgColor='FFF2CC')
GRIS = PatternFill('solid', fgColor='EDEDED')
VERDE = PatternFill('solid', fgColor='E2EFDA')
HEAD = PatternFill('solid', fgColor=AZUL)
borde = Border(*(Side(style='thin', color='BFBFBF'),)*4)
wrap = Alignment(wrap_text=True, vertical='top')

wb = Workbook()

def titulo(ws, texto, sub, ncols):
    ws['A1'] = texto; ws['A1'].font = Font(name=F, size=14, bold=True, color=AZUL)
    ws['A2'] = sub; ws['A2'].font = Font(name=F, size=10, italic=True, color='595959')
    ws['A2'].alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    ws.row_dimensions[2].height = 42

def tabla(ws, headers, anchos, filas, fila_ini=4, n_vacias=15, ejemplo_filas=()):
    for c, (h, w) in enumerate(zip(headers, anchos), 1):
        cell = ws.cell(fila_ini, c, h)
        cell.font = Font(name=F, bold=True, color='FFFFFF'); cell.fill = HEAD
        cell.alignment = Alignment(wrap_text=True, vertical='center'); cell.border = borde
        ws.column_dimensions[cell.column_letter].width = w
    ws.row_dimensions[fila_ini].height = 30
    total = len(filas) + n_vacias
    for i in range(total):
        r = fila_ini + 1 + i
        datos = filas[i] if i < len(filas) else [None]*len(headers)
        es_ej = i in ejemplo_filas
        for c in range(1, len(headers)+1):
            v = datos[c-1] if c-1 < len(datos) else None
            cell = ws.cell(r, c, v)
            cell.font = Font(name=F, size=10, italic=es_ej, color='7F7F7F' if es_ej else '000000')
            cell.fill = GRIS if es_ej else AMARILLO
            cell.alignment = wrap; cell.border = borde
    ws.freeze_panes = ws.cell(fila_ini+1, 2)
    return fila_ini+1, fila_ini+total

# ---------------- Listas (oculta) ----------------
L = wb.active; L.title = 'Listas'
listas = {
 'A': ('Tipo', ['Carrera técnica', 'Curso libre', 'Capacitación']),
 'B': ('SiNo', ['Sí', 'No']),
 'C': ('Concepto', ['Matrícula', 'Gabacha, camisa y póliza INS', 'Mensualidad', 'Costo por cuatrimestre', 'Costo total del curso', 'Derecho de diploma', 'Prima financiamiento', 'Otro']),
 'D': ('Jornada', ['Diurno', 'Nocturno', 'Sábados', 'Virtual', 'Mixto']),
 'E': ('Cupos', ['Hay cupos', 'Quedan pocos', 'Lleno', 'Sin confirmar']),
}
for col, (n, vals) in listas.items():
    L[f'{col}1'] = n
    for i, v in enumerate(vals, 2): L[f'{col}{i}'] = v
L.sheet_state = 'hidden'

# ---------------- Instrucciones ----------------
I = wb.create_sheet('Instrucciones', 0)
I.column_dimensions['A'].width = 4; I.column_dimensions['B'].width = 28; I.column_dimensions['C'].width = 90
I['B1'] = 'ITVM — Información para el asistente virtual de WhatsApp'
I['B1'].font = Font(name=F, size=16, bold=True, color=AZUL)
I['B2'] = 'Todo lo que cargue en esta planilla es lo que el asistente le va a responder a los interesados. Lo que no esté acá, el asistente no lo dice: deriva la consulta a un asesor.'
I['B2'].font = Font(name=F, size=10, italic=True); I.merge_cells('B2:C2'); I['B2'].alignment = wrap; I.row_dimensions[2].height = 30
filas = [
 ('CÓMO COMPLETAR', None),
 ('Celdas amarillas', 'Son para completar o corregir.'),
 ('Celdas grises en cursiva', 'Son EJEMPLOS. Reemplácelas con el dato real o bórrelas.'),
 ('Listas desplegables', 'Algunas columnas tienen opciones fijas (flechita al seleccionar la celda). Use esas opciones.'),
 ('Una fila = un dato', 'No junte varios precios u horarios en una misma celda: use una fila para cada uno.'),
 ('Si un dato no aplica', 'Deje la celda vacía. Nunca escriba "consultar": el asistente ya sabe derivar lo que falta.'),
 ('Montos', 'En colones, solo el número (ejemplo: 410989). El formato ₡ se aplica solo.'),
 ('Fechas', 'Formato día/mes/año (ejemplo: 12/01/2027).'),
 (None, None),
 ('PESTAÑAS', None),
 ('1. Datos generales', 'Horario de atención, teléfonos, dirección, formas de pago, financiamiento. Ya viene precargado desde itvm.cr: revise que esté correcto.'),
 ('2. Programas', 'Las carreras y cursos que se ofrecen. Precargado desde itvm.cr y los folletos. Revise requisitos y duración; ponga "No" en Activo para que el asistente deje de ofrecer un programa.'),
 ('3. Precios', 'Lo más importante: sin esto el asistente no da precios. Una fila por concepto (matrícula, cuatrimestre, uniforme...).'),
 ('4. Horarios e inicios', 'Grupos que abren: jornada, días, horas, fecha de inicio y si hay cupos.'),
 ('5. Promociones', 'Descuentos o becas vigentes. Ponga fecha "hasta" para que se desactiven solas.'),
 ('6. Preguntas frecuentes', 'Preguntas que les hacen seguido y cómo quieren que se respondan.'),
 (None, None),
 ('CUÁNDO SE ACTUALIZA', 'El asistente lee esta planilla una vez por día, a las 6:00 a.m. Lo que se cambie hoy se aplica desde mañana temprano.'),
 ('DUDAS', 'Escríbale a su contacto de soporte del asistente.'),
]
r = 4
for a, b in filas:
    if a: I[f'B{r}'] = a
    if b: I[f'C{r}'] = b
    if a and b is None:
        I[f'B{r}'].font = Font(name=F, size=11, bold=True, color=AZUL)
    else:
        I[f'B{r}'].font = Font(name=F, size=10, bold=True); I[f'C{r}'].font = Font(name=F, size=10)
    I[f'C{r}'].alignment = wrap
    r += 1
I['B5'].fill = AMARILLO; I['B6'].fill = GRIS; I['B6'].font = Font(name=F, size=10, bold=True, italic=True, color='7F7F7F')
I.sheet_view.showGridLines = False

# ---------------- Datos generales ----------------
D = wb.create_sheet('Datos generales')
titulo(D, 'Datos generales de ITVM', 'Precargado desde itvm.cr. Corrija lo que haya cambiado y complete lo que falta.', 3)
datos = [
 ('Horario de atención (WhatsApp y oficina)', 'Lunes a sábado de 7:30 a.m. a 9:00 p.m.', ''),
 ('Teléfono WhatsApp', '7107-4722', ''),
 ('Teléfono central', '4002-1470', ''),
 ('Correo', 'info@itvm.cr', ''),
 ('Dirección', 'De Capris en La Uruca, 100 metros norte y 50 metros este, San José', ''),
 ('Cómo aparece en Waze', 'Instituto Técnico Vargas Matamoros', ''),
 ('Parqueo', 'Parqueo propio', ''),
 ('Formas de pago', 'ACAMSYS, SINPE, depósito, tarjeta', ''),
 ('Inversión inicial común a todos', 'Gabacha, camisa T-shirt y póliza del INS', 'Poner el monto en la pestaña Precios'),
 ('Financiamiento CONAPE', 'Sí, préstamos de CONAPE para estudios técnicos', ''),
 ('Financiamiento propio (letras de cambio)', None, 'Condiciones: prima, cantidad de cuotas, requisitos'),
 ('¿Se puede visitar el instituto?', None, 'Ej: Sí, con cita previa, de lunes a viernes'),
 ('¿Matrícula en línea?', 'Sí, trámites y pagos en línea', ''),
 ('Bolsa de empleo', 'Sí, alianzas con empleadores de la industria automotriz', ''),
 ('Sitio web', 'https://itvm.cr', ''),
 ('Otro dato importante', None, ''),
]
D['A4'], D['B4'], D['C4'] = 'Dato', 'Valor', 'Notas para quien completa'
for c in 'ABC':
    D[f'{c}4'].font = Font(name=F, bold=True, color='FFFFFF'); D[f'{c}4'].fill = HEAD; D[f'{c}4'].border = borde
D.column_dimensions['A'].width = 38; D.column_dimensions['B'].width = 60; D.column_dimensions['C'].width = 42
for i, (a, b, c) in enumerate(datos, 5):
    D[f'A{i}'] = a; D[f'A{i}'].font = Font(name=F, size=10, bold=True); D[f'A{i}'].fill = VERDE
    D[f'B{i}'] = b; D[f'B{i}'].font = Font(name=F, size=10); D[f'B{i}'].fill = AMARILLO
    D[f'C{i}'] = c; D[f'C{i}'].font = Font(name=F, size=9, italic=True, color='7F7F7F')
    for col in 'ABC': D[f'{col}{i}'].border = borde; D[f'{col}{i}'].alignment = wrap
D.freeze_panes = 'B5'

# ---------------- Programas ----------------
P = wb.create_sheet('Programas')
titulo(P, 'Programas (carreras y cursos)', 'Una fila por programa. El "Nombre" es el que se usa en las pestañas Precios y Horarios. Ponga "No" en Activo para que el asistente deje de ofrecerlo.', 9)
progs = [
 ('Técnico en Mecánica de Vehículos Livianos','Carrera técnica','Sí','Sí (resolución 2026-02)','Presencial','6 cuatrimestres (diurno/nocturno) u 8 cuatrimestres (sábados)','Mayor de 15 años. Sexto grado (VERIFICAR: la web dice noveno año). Cédula, documento de menor o DIMEX.','Nacionales: titulación INA. Solo pasaporte: programa sin acreditación.','https://itvm.cr/wp-content/uploads/2026/05/Folleto-Mecanica-de-Vehiculos-livianos-3.pdf'),
 ('Técnico en Mecánica de Motocicletas (intensivo)','Carrera técnica','Sí','No','Presencial','8 meses','Mayor de 18 años. Sexto grado. Cédula, residencia, pasaporte, DIMEX o carné de refugio.','Pasantías opcionales.','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Mecanica-de-Motocicletas-Intensivo-2.pdf'),
 ('Técnico en Peritaje Automotriz','Carrera técnica','Sí','No','Híbrida (presencial + virtual)','10 meses + pasantía','Noveno año. Mayor de 17 años. Cédula, residencia, pasaporte, DIMEX o carné de refugio.','Única institución con Peritaje en grado técnico.','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Peritaje-Automotriz-2.pdf'),
 ('Técnico en Electromecánica','Carrera técnica','Sí','No','Presencial + virtual','12 meses','Mayor de 18 años. Bachiller. Cédula. 9 horas semanales. Internet.','Horario nocturno. Pasantías opcionales.','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Electromecanica-2.pdf'),
 ('Técnico en Autotrónica','Carrera técnica','Sí','No','Presencial','288 horas / 8 meses (3 días por semana, 3 h)','Conocimientos básicos de mecánica. Noveno año. Documento de identidad.','','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Autotronica-3.pdf'),
 ('Técnico en Semiconductores','Carrera técnica','Sí','No','Bimodal (Teams + presencial)','3 cuatrimestres',None,'FALTAN REQUISITOS: el sitio no los publica.','https://itvm.cr/wp-content/uploads/2026/03/Folleto-Semiconductores-2.pdf'),
 ('Inyección electrónica para motocicletas','Curso libre','Sí','No','Presencial','216 horas / 6 meses','Título de mecánica o 1 año de experiencia. Sexto grado. Documento de identidad.','','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Inyeccion-Motos-2.pdf'),
 ('Motores de motocicletas 2 tiempos','Curso libre','Sí','No','Presencial','144 horas / 4 meses','Título de mecánica o 1 año de experiencia. Sexto grado. Documento de identidad.','','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Motores-2-tiempos-2.pdf'),
 ('Electricidad residencial','Curso libre','Sí','No','Presencial','288 horas / 8 meses','Noveno año. Documento de identidad.','','https://itvm.cr/wp-content/uploads/2024/03/Folleto-Instalaciones-Electricas-2024.pdf'),
 ('Inyección diésel Common Rail (CRDI)','Curso libre','Sí','No',None,'48 horas / 8 semanas','Conocimientos de electricidad y electrónica automotriz. Mayor de 17. Sexto grado.','FALTA MODALIDAD.','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Inyeccion-Diesel-Common-Rail-2.pdf'),
 ('Metrología para la industria médica','Curso libre','Sí','No','Bimodal','216 horas (3 días por semana, 3 h)','Mayor de 18 años. Bachillerato. Documento de identidad.','','https://itvm.cr/wp-content/uploads/2025/09/Folleto-Metrologia-1.pdf'),
 ('Manejo y uso de montacargas','Capacitación','Sí','No','Bimodal (teoría virtual + práctica presencial)','12 horas','Licencia D3. Mínimo 2 años de experiencia.','Pensado para empresas.','https://itvm.cr/wp-content/uploads/2026/09/Manejo-y-uso-de-montacargas-3.pdf'),
]
h = ['Nombre del programa','Tipo','Activo','Acreditado INA','Modalidad','Duración','Requisitos de ingreso','Notas para el asistente','Link del folleto']
ini, fin = tabla(P, h, [36,16,9,18,24,28,48,36,40], progs, n_vacias=8)
dv = DataValidation(type='list', formula1='=Listas!$A$2:$A$4', allow_blank=True); P.add_data_validation(dv); dv.add(f'B{ini}:B{fin}')
dv = DataValidation(type='list', formula1='=Listas!$B$2:$B$3', allow_blank=True); P.add_data_validation(dv); dv.add(f'C{ini}:C{fin}')
P.conditional_formatting.add(f'A{ini}:I{fin}', FormulaRule(formula=[f'$C{ini}="No"'], font=Font(color='A6A6A6', strike=True)))
for r in range(ini, ini+len(progs)):
    for c in range(1, 10):
        v = P.cell(r, c).value
        if isinstance(v, str) and ('VERIFICAR' in v or 'FALTA' in v):
            P.cell(r, c).fill = PatternFill('solid', fgColor='F8CBAD')
P['A3'] = 'Celdas en naranja: dato a verificar o que falta.'; P['A3'].font = Font(name=F, size=9, bold=True, color='C55A11')
PROG_RANGO = f'=Programas!$A${ini}:$A${fin}'

# ---------------- Precios ----------------
R = wb.create_sheet('Precios')
titulo(R, 'Precios', 'Una fila por concepto. Elija el programa de la lista. Monto en colones, solo el número. Si un precio vence, ponga la fecha en "Vigente hasta": cuando pase, la fila se marca como VENCIDO y el asistente la ignora.', 7)
ejemplos = [
 ('Técnico en Mecánica de Motocicletas (intensivo)','Matrícula',28789,None,None,'EJEMPLO (folleto abril 2025): confirmar o borrar'),
 ('Técnico en Mecánica de Motocicletas (intensivo)','Gabacha, camisa y póliza INS',42096,None,None,'EJEMPLO (folleto abril 2025): confirmar o borrar'),
 ('Técnico en Mecánica de Motocicletas (intensivo)','Costo por cuatrimestre',410989,'Bloque completo de 4 materias',None,'EJEMPLO (folleto abril 2025): confirmar o borrar'),
 ('Técnico en Mecánica de Motocicletas (intensivo)','Derecho de diploma',57178,None,None,'EJEMPLO (folleto abril 2025): confirmar o borrar'),
 ('Motores de motocicletas 2 tiempos','Costo total del curso',300000,'Matrícula gratuita',None,'EJEMPLO (folleto abril 2025): confirmar o borrar'),
 ('Electricidad residencial','Costo total del curso',400000,None,None,'EJEMPLO (folleto 2024): confirmar o borrar'),
]
h = ['Programa','Concepto','Monto (₡)','Detalle','Vigente hasta','Notas internas (el asistente no las lee)','Estado']
ini, fin = tabla(R, h, [40,28,14,32,14,40,12], ejemplos, n_vacias=40, ejemplo_filas=range(len(ejemplos)))
for r in range(ini, fin+1):
    R[f'C{r}'].number_format = '"₡"#,##0'
    R[f'E{r}'].number_format = 'DD/MM/YYYY'
    R[f'G{r}'] = f'=IF(A{r}="","",IF(AND(E{r}<>"",E{r}<TODAY()),"VENCIDO","Vigente"))'
    R[f'G{r}'].fill = PatternFill(None); R[f'G{r}'].font = Font(name=F, size=10, bold=True)
dv = DataValidation(type='list', formula1=PROG_RANGO, allow_blank=True, showErrorMessage=True, errorTitle='Programa', error='Elija un programa de la pestaña Programas.'); R.add_data_validation(dv); dv.add(f'A{ini}:A{fin}')
dv = DataValidation(type='list', formula1='=Listas!$C$2:$C$9', allow_blank=True); R.add_data_validation(dv); dv.add(f'B{ini}:B{fin}')
dv = DataValidation(type='decimal', operator='greaterThanOrEqual', formula1='0', allow_blank=True, showErrorMessage=True, error='Solo números, sin ₡ ni puntos.'); R.add_data_validation(dv); dv.add(f'C{ini}:C{fin}')
dv = DataValidation(type='date', operator='greaterThan', formula1='DATE(2020,1,1)', allow_blank=True, showErrorMessage=True, error='Escriba una fecha dd/mm/aaaa.'); R.add_data_validation(dv); dv.add(f'E{ini}:E{fin}')
R.conditional_formatting.add(f'G{ini}:G{fin}', FormulaRule(formula=[f'$G{ini}="VENCIDO"'], font=Font(color='C00000', bold=True)))
R.conditional_formatting.add(f'G{ini}:G{fin}', FormulaRule(formula=[f'$G{ini}="Vigente"'], font=Font(color='548235', bold=True)))
R['C3'] = 'Ej: 410989'; R['C3'].font = Font(name=F, size=9, italic=True, color='7F7F7F')

# ---------------- Horarios e inicios ----------------
H = wb.create_sheet('Horarios e inicios')
titulo(H, 'Horarios e inicios de grupos', 'Una fila por grupo que abre. Si un programa tiene grupo diurno y nocturno, son dos filas. Cuando el grupo empieza o se llena, actualice "Cupos".', 8)
ej = [('Técnico en Mecánica de Motocicletas (intensivo)','Nocturno','Lunes a miércoles','6:00 p.m.','9:00 p.m.',None,'Sin confirmar','EJEMPLO (folleto abril 2025): completar fecha de inicio'),
      ('Técnico en Mecánica de Motocicletas (intensivo)','Sábados','Sábados','8:00 a.m.','6:00 p.m.',None,'Sin confirmar','EJEMPLO (folleto abril 2025)')]
h = ['Programa','Jornada','Días','Hora inicio','Hora fin','Fecha de inicio','Cupos','Notas']
ini, fin = tabla(H, h, [40,12,24,12,12,15,15,40], ej, n_vacias=30, ejemplo_filas=range(len(ej)))
for r in range(ini, fin+1): H[f'F{r}'].number_format = 'DD/MM/YYYY'
dv = DataValidation(type='list', formula1=PROG_RANGO, allow_blank=True); H.add_data_validation(dv); dv.add(f'A{ini}:A{fin}')
dv = DataValidation(type='list', formula1='=Listas!$D$2:$D$6', allow_blank=True); H.add_data_validation(dv); dv.add(f'B{ini}:B{fin}')
dv = DataValidation(type='list', formula1='=Listas!$E$2:$E$5', allow_blank=True); H.add_data_validation(dv); dv.add(f'G{ini}:G{fin}')
dv = DataValidation(type='date', operator='greaterThan', formula1='DATE(2020,1,1)', allow_blank=True); H.add_data_validation(dv); dv.add(f'F{ini}:F{fin}')
H.conditional_formatting.add(f'A{ini}:H{fin}', FormulaRule(formula=[f'$G{ini}="Lleno"'], font=Font(color='A6A6A6', strike=True)))

# ---------------- Promociones ----------------
PR = wb.create_sheet('Promociones')
titulo(PR, 'Promociones, becas y descuentos', 'Solo lo vigente. Con fecha "Hasta", la promo se desactiva sola al vencer.', 7)
ej = [('Matrícula gratis enero','Matrícula sin costo para quienes se matriculen antes del inicio','Todos los programas',None,None,'Solo pago de contado del primer cuatrimestre')]
h = ['Promoción','Qué incluye','Aplica a','Desde','Hasta','Condiciones','Estado']
ini, fin = tabla(PR, h, [28,44,28,13,13,40,12], ej, n_vacias=15, ejemplo_filas=[0])
for r in range(ini, fin+1):
    for c in 'DE': PR[f'{c}{r}'].number_format = 'DD/MM/YYYY'
    PR[f'G{r}'] = f'=IF(A{r}="","",IF(AND(E{r}<>"",E{r}<TODAY()),"VENCIDA",IF(AND(D{r}<>"",D{r}>TODAY()),"Próxima","Vigente")))'
    PR[f'G{r}'].fill = PatternFill(None); PR[f'G{r}'].font = Font(name=F, size=10, bold=True)
PR.conditional_formatting.add(f'G{ini}:G{fin}', FormulaRule(formula=[f'$G{ini}="VENCIDA"'], font=Font(color='C00000', bold=True)))

# ---------------- Preguntas frecuentes ----------------
Q = wb.create_sheet('Preguntas frecuentes')
titulo(Q, 'Preguntas frecuentes', 'Escriba la respuesta como quiere que el asistente la diga (con sus palabras, corta).', 2)
ej = [('¿Las clases son presenciales o virtuales?','Depende del programa: Vehículos Livianos y Motocicletas son presenciales; Peritaje, Electromecánica y Semiconductores combinan presencial y virtual.'),
      ('¿Dan certificado o título?',None),
      ('¿Puedo pagar en cuotas?',None),
      ('¿Necesito tener herramientas propias?',None),
      ('¿Qué pasa si falto a clases?',None)]
ini, fin = tabla(Q, ['Pregunta','Respuesta'], [48,90], ej, n_vacias=20, ejemplo_filas=[0])
for r in range(ini+1, ini+len(ej)):
    Q[f'A{r}'].font = Font(name=F, size=10); Q[f'A{r}'].fill = AMARILLO

for ws in wb.worksheets:
    ws.sheet_properties.tabColor = {'Instrucciones':'1F3864','Precios':'C00000','Listas':'808080'}.get(ws.title, '2E75B6')
    ws.page_setup.orientation = 'landscape'; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
wb.move_sheet('Listas', offset=len(wb.sheetnames)-1-wb.sheetnames.index('Listas'))
wb.active = 0
wb.save(OUT)
print('ok')
