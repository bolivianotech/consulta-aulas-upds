"""
==============================================================================
API - Consulta de Aulas por Docente
Universidad Privada Domingo Savio (UPDS)
==============================================================================

DESCRIPCIÓN GENERAL:
    API Flask para consultar aulas por docente/materia y administrar registros.
    - Consulta pública para estudiantes
    - Administración (CRUD) de registros
    - Carga de archivos Excel (formato LISTADO GENERAL POR GRUPOS)
    - Persistencia en Supabase
    - Auditoría de cambios (auditlog)
    - Advertencia por sesiones concurrentes (solo visual)

ENDPOINTS PÚBLICOS (Consulta):
    GET  /                    → Información general de la API
    GET  /api/health          → Verificación de estado del servicio
    GET  /api/docentes        → Lista todos los docentes disponibles
    GET  /api/sugerencias     → Autocompletado docentes/materias
    GET  /api/consulta        → Consulta aulas por docente o materia
    GET  /api/aulas           → Lista todas las asignaciones con filtros

ENDPOINTS ADMINISTRATIVOS (CRUD):
    GET    /api/admin/registros            → Lista todos los registros (paginación)
    POST   /api/admin/registros            → Crear nuevo registro
    GET    /api/admin/registros/<id>       → Obtener registro
    PUT    /api/admin/registros/<id>       → Actualizar registro
    DELETE /api/admin/registros/<id>       → Eliminar registro
    POST   /api/admin/upload               → Subir Excel y reemplazar datos
    GET    /api/admin/export               → Exportar datos actuales a JSON

ENDPOINTS ADMINISTRATIVOS (Sesiones):
    POST   /api/admin/session/heartbeat    → Registrar/renovar sesión
    GET    /api/admin/session/active       → Contar sesiones activas

DEPENDENCIAS:
    - Flask >= 3.0.0
    - openpyxl (lectura Excel)
    - supabase (persistencia)

==============================================================================
"""

# =============================================================================
# IMPORTACIONES
# =============================================================================
from flask import Flask, jsonify, request, send_file
import os
import json
import unicodedata
from datetime import datetime, timedelta
import io

from supabase import create_client

# Intentamos importar openpyxl para la carga de Excel
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    print("ADVERTENCIA: openpyxl no está instalado. La carga de Excel estará deshabilitada.")

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN FLASK
# =============================================================================
app = Flask(__name__)

# Configuración para subida de archivos
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo

# =============================================================================
# SUPABASE
# =============================================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Faltan variables de entorno SUPABASE_URL o SUPABASE_ANON_KEY")
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client

# =============================================================================
# UTILIDADES
# =============================================================================

def normalizar(texto: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, sin espacios extra."""
    if texto is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


def normalizar_turno(turno: str) -> str:
    """Normaliza turno a los valores esperados en la UI/API."""
    if turno is None:
        return ""
    t = str(turno).strip().upper()
    t = t.replace("DÍA", "DIA")
    t = t.replace("MEDIODIA", "MEDIO DIA")
    if t in ("MANANA", "MAÑANA"):
        return "MAÑANA"
    if t in ("MEDIO DIA", "MEDIO DÍA"):
        return "MEDIO DIA"
    if t in ("TARDE", "NOCHE"):
        return t
    return t


def audit_log(action: str, record_id=None, old_value=None, new_value=None, extra=None):
    """Registra cambios en la tabla auditlog usando user-agent y client-id."""
    try:
        supabase = get_supabase()
        user_agent = request.headers.get("X-User-Agent") or request.headers.get("User-Agent")
        client_id = request.headers.get("X-Client-Id")
        payload = {
            "action": action,
            "record_id": record_id,
            "user_agent": user_agent,
            "client_id": client_id,
            "old_value": old_value,
            "new_value": new_value,
            "extra": extra,
        }
        supabase.table("auditlog").insert(payload).execute()
    except Exception as e:
        print(f"ADVERTENCIA: No se pudo escribir auditlog: {e}")


def chunked(lst, size=1000):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def ultima_fila_columna_b(ws) -> int:
    """Encuentra la última fila con datos en la columna B."""
    for fila in range(ws.max_row, 0, -1):
        valor = ws.cell(row=fila, column=2).value
        if valor is not None and str(valor).strip() != "":
            return fila
    return ws.max_row


def validar_registro(datos: dict, es_actualizacion: bool = False) -> tuple[bool, str]:
    """Valida que un registro tenga todos los campos requeridos."""
    campos_requeridos = ["turno", "materia", "docente", "aula", "horario"]

    if not es_actualizacion:
        for campo in campos_requeridos:
            if campo not in datos or not str(datos[campo]).strip():
                return False, f"El campo '{campo}' es obligatorio"

    turnos_validos = ["MAÑANA", "MEDIO DIA", "TARDE", "NOCHE"]
    if "turno" in datos and datos["turno"]:
        turno_upper = normalizar_turno(datos["turno"])
        if turno_upper not in turnos_validos:
            return False, f"Turno inválido. Valores permitidos: {', '.join(turnos_validos)}"

    return True, ""

# =============================================================================
# ENDPOINTS PÚBLICOS - CONSULTA
# =============================================================================

@app.route("/", methods=["GET"])
def raiz():
    return jsonify({
        "message": "API de Consulta de Aulas - UPDS",
        "version": "3.0",
        "docs": "https://github.com/bolivianotech/consulta-aulas-upds",
        "endpoints": {
            "/api/health": "Verificación de estado del servicio",
            "/api/docentes": "Lista docentes (opcional: ?q=filtro)",
            "/api/sugerencias": "Autocompletado (docentes/materias)",
            "/api/consulta": "Consulta por docente o materia (?q=...)",
            "/api/aulas": "Lista asignaciones con filtros",
            "/api/admin/registros": "CRUD de registros (admin)",
            "/api/admin/upload": "Subir Excel (admin)"
        }
    })


@app.route("/api/health", methods=["GET"])
def health():
    try:
        supabase = get_supabase()
        res = supabase.table("asignaciones").select("id", count="exact").execute()
        total = res.count or 0

        res_docs = supabase.table("asignaciones").select("docente").execute()
        docs = set()
        for item in res_docs.data or []:
            nombre = (item.get("docente") or "").strip()
            if nombre and nombre.upper() != "NO DEFINIDO":
                docs.add(nombre)

        return jsonify({
            "status": "ok",
            "total_asignaciones": total,
            "total_docentes": len(docs),
            "excel_support": EXCEL_SUPPORT,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/api/docentes", methods=["GET"])
def docentes():
    q = request.args.get("q", "").strip()

    supabase = get_supabase()
    res = supabase.table("asignaciones").select("docente").execute()

    docs = set()
    for item in res.data or []:
        nombre = (item.get("docente") or "").strip()
        if nombre and nombre.upper() != "NO DEFINIDO":
            docs.add(nombre)

    docs_list = sorted(docs, key=lambda x: normalizar(x))

    if q:
        q_norm = normalizar(q)
        docs_list = [d for d in docs_list if q_norm in normalizar(d)]

    return jsonify({"docentes": docs_list, "total": len(docs_list)})


@app.route("/api/sugerencias", methods=["GET"])
def sugerencias():
    q = request.args.get("q", "").strip()

    if len(q) < 2:
        return jsonify({"sugerencias": [], "total": 0})

    q_norm = normalizar(q)
    supabase = get_supabase()

    res_docs = supabase.table("asignaciones").select("docente").execute()
    res_mats = supabase.table("asignaciones").select("materia").execute()

    docentes = sorted({(d.get("docente") or "").strip() for d in res_docs.data or [] if (d.get("docente") or "").strip()}, key=lambda x: normalizar(x))
    materias = sorted({(m.get("materia") or "").strip() for m in res_mats.data or [] if (m.get("materia") or "").strip()}, key=lambda x: normalizar(x))

    sugerencias_list = []
    for docente in docentes:
        if q_norm in normalizar(docente):
            sugerencias_list.append({"texto": docente, "tipo": "docente"})
    for materia in materias:
        if q_norm in normalizar(materia):
            sugerencias_list.append({"texto": materia, "tipo": "materia"})

    docentes_sug = [s for s in sugerencias_list if s["tipo"] == "docente"][:5]
    materias_sug = [s for s in sugerencias_list if s["tipo"] == "materia"][:5]
    sugerencias_list = docentes_sug + materias_sug

    return jsonify({"sugerencias": sugerencias_list, "total": len(sugerencias_list)})


@app.route("/api/consulta", methods=["GET"])
def consulta():
    query = request.args.get("q", "").strip() or request.args.get("docente", "").strip()
    turno_filtro = request.args.get("turno", "").strip()

    if not query:
        return jsonify({
            "error": "Parámetro 'q' o 'docente' es requerido.",
            "ejemplo": "/api/consulta?q=Miranda o /api/consulta?q=Calculo"
        }), 400

    supabase = get_supabase()
    q_norm = normalizar(query)

    # Buscar por docente
    res = supabase.table("asignaciones").select("*").ilike("docente_norm", f"%{q_norm}%").execute()
    resultados = res.data or []
    tipo_busqueda = "docente"

    # Si no hay resultados por docente, buscar por materia
    if not resultados:
        res = supabase.table("asignaciones").select("*").ilike("materia_norm", f"%{q_norm}%").execute()
        resultados = res.data or []
        tipo_busqueda = "materia"

    # Filtrar por turno si se proporcionó
    if turno_filtro:
        turno_filtro = normalizar_turno(turno_filtro)
        resultados = [r for r in resultados if normalizar_turno(r.get("turno", "")) == turno_filtro]

    if resultados:
        encontrado = resultados[0]["docente"] if tipo_busqueda == "docente" else resultados[0]["materia"]
    else:
        encontrado = None

    return jsonify({
        "tipo_busqueda": tipo_busqueda,
        "encontrado": encontrado,
        "consulta": query,
        "turno_filtro": turno_filtro or None,
        "total_asignaciones": len(resultados),
        "asignaciones": resultados
    })


@app.route("/api/aulas", methods=["GET"])
def aulas():
    turno = request.args.get("turno", "").strip()
    materia = request.args.get("materia", "").strip()
    aula = request.args.get("aula", "").strip()

    supabase = get_supabase()
    query = supabase.table("asignaciones").select("*")

    if turno:
        query = query.eq("turno", normalizar_turno(turno))
    if materia:
        query = query.ilike("materia_norm", f"%{normalizar(materia)}%")
    if aula:
        query = query.ilike("aula_norm", f"%{normalizar(aula)}%")

    res = query.execute()
    resultados = res.data or []

    return jsonify({
        "total": len(resultados),
        "filtros": {
            "turno": normalizar_turno(turno) if turno else None,
            "materia": materia or None,
            "aula": aula or None
        },
        "asignaciones": resultados
    })

# =============================================================================
# ENDPOINTS ADMINISTRATIVOS - CRUD
# =============================================================================

@app.route("/api/admin/registros", methods=["GET"])
def admin_listar_registros():
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        page = 1
        per_page = 20

    search = request.args.get("search", "").strip()
    turno = request.args.get("turno", "").strip()

    supabase = get_supabase()
    query = supabase.table("asignaciones").select("*", count="exact")

    if turno:
        query = query.eq("turno", normalizar_turno(turno))

    if search:
        s = normalizar(search)
        query = query.or_(
            f"docente_norm.ilike.%{s}%,materia_norm.ilike.%{s}%,aula_norm.ilike.%{s}%,horario_norm.ilike.%{s}%"
        )

    total_start = (page - 1) * per_page
    total_end = total_start + per_page - 1

    res = query.range(total_start, total_end).execute()
    registros = res.data or []
    total = res.count or 0

    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    return jsonify({
        "registros": registros,
        "paginacion": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "filtros": {
            "search": search or None,
            "turno": normalizar_turno(turno) if turno else None
        }
    })


@app.route("/api/admin/registros", methods=["POST"])
def admin_crear_registro():
    if not request.is_json:
        return jsonify({"error": "Se requiere Content-Type: application/json"}), 400

    datos = request.get_json()
    es_valido, mensaje_error = validar_registro(datos)
    if not es_valido:
        return jsonify({"error": mensaje_error}), 400

    nuevo = {
        "turno": normalizar_turno(datos["turno"]),
        "materia": datos["materia"].strip(),
        "docente": datos["docente"].strip(),
        "aula": datos["aula"].strip(),
        "horario": datos["horario"].strip(),
        "docente_norm": normalizar(datos["docente"]),
        "materia_norm": normalizar(datos["materia"]),
        "aula_norm": normalizar(datos["aula"]),
        "horario_norm": normalizar(datos["horario"]),
        "updated_at": datetime.utcnow().isoformat()
    }

    supabase = get_supabase()
    res = supabase.table("asignaciones").insert(nuevo).execute()
    creado = (res.data or [None])[0]

    audit_log("CREATE", record_id=creado.get("id") if creado else None, old_value=None, new_value=creado)

    return jsonify({"mensaje": "Registro creado exitosamente", "registro": creado}), 201


@app.route("/api/admin/registros/<int:registro_id>", methods=["GET"])
def admin_obtener_registro(registro_id):
    supabase = get_supabase()
    res = supabase.table("asignaciones").select("*").eq("id", registro_id).limit(1).execute()

    if not res.data:
        return jsonify({"error": f"Registro con ID {registro_id} no encontrado"}), 404

    return jsonify({"registro": res.data[0]})


@app.route("/api/admin/registros/<int:registro_id>", methods=["PUT"])
def admin_actualizar_registro(registro_id):
    if not request.is_json:
        return jsonify({"error": "Se requiere Content-Type: application/json"}), 400

    datos = request.get_json()
    es_valido, mensaje_error = validar_registro(datos, es_actualizacion=True)
    if not es_valido:
        return jsonify({"error": mensaje_error}), 400

    supabase = get_supabase()
    res = supabase.table("asignaciones").select("*").eq("id", registro_id).limit(1).execute()
    if not res.data:
        return jsonify({"error": f"Registro con ID {registro_id} no encontrado"}), 404

    anterior = res.data[0]

    actualizacion = {}
    if "turno" in datos and datos["turno"]:
        actualizacion["turno"] = normalizar_turno(datos["turno"])
    if "materia" in datos and datos["materia"]:
        actualizacion["materia"] = datos["materia"].strip()
        actualizacion["materia_norm"] = normalizar(datos["materia"])
    if "docente" in datos and datos["docente"]:
        actualizacion["docente"] = datos["docente"].strip()
        actualizacion["docente_norm"] = normalizar(datos["docente"])
    if "aula" in datos and datos["aula"]:
        actualizacion["aula"] = datos["aula"].strip()
        actualizacion["aula_norm"] = normalizar(datos["aula"])
    if "horario" in datos and datos["horario"]:
        actualizacion["horario"] = datos["horario"].strip()
        actualizacion["horario_norm"] = normalizar(datos["horario"])

    if not actualizacion:
        return jsonify({"error": "No se proporcionaron campos válidos para actualizar"}), 400

    actualizacion["updated_at"] = datetime.utcnow().isoformat()

    res_upd = supabase.table("asignaciones").update(actualizacion).eq("id", registro_id).execute()
    actualizado = (res_upd.data or [None])[0]

    audit_log("UPDATE", record_id=registro_id, old_value=anterior, new_value=actualizado)

    return jsonify({"mensaje": "Registro actualizado exitosamente", "registro": actualizado})


@app.route("/api/admin/registros/<int:registro_id>", methods=["DELETE"])
def admin_eliminar_registro(registro_id):
    supabase = get_supabase()
    res = supabase.table("asignaciones").select("*").eq("id", registro_id).limit(1).execute()
    if not res.data:
        return jsonify({"error": f"Registro con ID {registro_id} no encontrado"}), 404

    eliminado = res.data[0]
    supabase.table("asignaciones").delete().eq("id", registro_id).execute()

    audit_log("DELETE", record_id=registro_id, old_value=eliminado, new_value=None)

    return jsonify({"mensaje": "Registro eliminado exitosamente", "registro_eliminado": eliminado})

# =============================================================================
# ENDPOINTS ADMINISTRATIVOS - CARGA DE EXCEL
# =============================================================================

@app.route("/api/admin/upload", methods=["POST"])
def admin_upload_excel():
    if not EXCEL_SUPPORT:
        return jsonify({"error": "La carga de Excel no está disponible. Instale openpyxl: pip install openpyxl"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo. Use el campo 'file'"}), 400

    archivo = request.files["file"]

    if archivo.filename == "":
        return jsonify({"error": "El archivo no tiene nombre"}), 400

    if not archivo.filename.lower().endswith((".xlsx", ".xls", ".xlsm")):
        return jsonify({"error": "Solo se permiten archivos Excel (.xlsx, .xls, .xlsm)"}), 400

    try:
        wb = openpyxl.load_workbook(archivo, data_only=True)
        ws = wb.active

        # Validación de formato
        celda_b2 = str(ws["B2"].value or "")
        if "LISTADO GENERAL POR GRUPOS" not in celda_b2.upper():
            return jsonify({
                "error": "No es un reporte válido. Celda B2 no contiene 'LISTADO GENERAL POR GRUPOS'.",
                "detalle": celda_b2
            }), 400

        ultima_fila = ultima_fila_columna_b(ws)
        nuevos_registros = []
        errores = []

        turno_actual = ""
        cont_datos = 0

        for fila in range(8, ultima_fila + 1):
            valor_b = str(ws.cell(row=fila, column=2).value or "").strip()

            if valor_b == "Turno:":
                valor_d = str(ws.cell(row=fila, column=4).value or "DESCONOCIDO").strip()
                turno_actual = normalizar_turno(valor_d)
                continue

            if valor_b == "" or valor_b == "0":
                continue
            if "TOTALES" in valor_b.upper():
                continue
            if valor_b == "Nro":
                continue

            check_subtotal = str(ws.cell(row=fila, column=12).value or "")
            if "SUB TOTAL" in check_subtotal.upper():
                continue

            valor_b_num = ws.cell(row=fila, column=2).value
            if not (isinstance(valor_b_num, (int, float)) or valor_b.startswith(".")):
                continue

            if not turno_actual:
                continue

            materia = str(ws.cell(row=fila, column=7).value or "").strip()
            if materia == "" or materia == "0":
                continue

            nro = ws.cell(row=fila, column=2).value
            docente = str(ws.cell(row=fila, column=11).value or "NO DEFINIDO").strip() or "NO DEFINIDO"
            aula = str(ws.cell(row=fila, column=16).value or "").strip()
            horario = str(ws.cell(row=fila, column=18).value or "").strip()

            cont_datos += 1

            nuevos_registros.append({
                "turno": turno_actual,
                "materia": materia,
                "docente": docente,
                "aula": aula,
                "horario": horario,
                "docente_norm": normalizar(docente),
                "materia_norm": normalizar(materia),
                "aula_norm": normalizar(aula),
                "horario_norm": normalizar(horario),
                "updated_at": datetime.utcnow().isoformat()
            })

        if not nuevos_registros:
            return jsonify({"error": "No se encontraron registros válidos en el archivo", "errores": errores}), 400

        supabase = get_supabase()
        res_prev = supabase.table("asignaciones").select("id", count="exact").execute()
        registros_anteriores = res_prev.count or 0

        # Eliminar todo antes de insertar
        supabase.table("asignaciones").delete().neq("id", 0).execute()

        for bloque in chunked(nuevos_registros, 1000):
            supabase.table("asignaciones").insert(bloque).execute()

        # Estadísticas
        res_total = supabase.table("asignaciones").select("id", count="exact").execute()
        total_nuevo = res_total.count or len(nuevos_registros)

        res_docs = supabase.table("asignaciones").select("docente").execute()
        docentes = set()
        for item in res_docs.data or []:
            nombre = (item.get("docente") or "").strip()
            if nombre and nombre.upper() != "NO DEFINIDO":
                docentes.add(nombre)

        audit_log(
            "UPLOAD_EXCEL",
            record_id=None,
            old_value=None,
            new_value=None,
            extra={
                "filename": archivo.filename,
                "registros_nuevos": total_nuevo,
                "errores": errores
            }
        )

        return jsonify({
            "mensaje": "Archivo procesado exitosamente",
            "estadisticas": {
                "registros_anteriores": registros_anteriores,
                "registros_nuevos": total_nuevo,
                "docentes_unicos": len(docentes),
                "errores_encontrados": len(errores)
            },
            "errores": errores if errores else None
        })

    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500


@app.route("/api/admin/export", methods=["GET"])
def admin_exportar_json():
    supabase = get_supabase()
    res = supabase.table("asignaciones").select("*").execute()
    contenido = res.data or []

    json_content = io.BytesIO()
    json_content.write(bytes(json.dumps(contenido, ensure_ascii=False, indent=2), "utf-8"))
    json_content.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"consultas_backup_{timestamp}.json"

    return send_file(
        json_content,
        mimetype="application/json",
        as_attachment=True,
        download_name=nombre_archivo
    )

# =============================================================================
# ENDPOINTS ADMINISTRATIVOS - SESIONES
# =============================================================================

@app.route("/api/admin/session/heartbeat", methods=["POST"])
def admin_session_heartbeat():
    supabase = get_supabase()
    client_id = request.headers.get("X-Client-Id")
    user_agent = request.headers.get("X-User-Agent") or request.headers.get("User-Agent")

    if not client_id:
        return jsonify({"error": "X-Client-Id es requerido"}), 400

    payload = {
        "client_id": client_id,
        "user_agent": user_agent,
        "last_seen": datetime.utcnow().isoformat()
    }

    supabase.table("admin_sessions").upsert(payload, on_conflict="client_id").execute()

    return jsonify({"ok": True})


@app.route("/api/admin/session/active", methods=["GET"])
def admin_session_active():
    supabase = get_supabase()
    minutos = int(request.args.get("minutes", 5))
    corte = datetime.utcnow() - timedelta(minutes=minutos)

    res = supabase.table("admin_sessions").select("client_id", count="exact").gte("last_seen", corte.isoformat()).execute()
    activos = res.count or 0

    return jsonify({"active": activos, "window_minutes": minutos})

# =============================================================================
# CONFIGURACIÓN CORS
# =============================================================================

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Client-Id, X-User-Agent"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("API de Consulta de Aulas - UPDS")
    print("=" * 60)
    print("Soporte Excel:", "Sí" if EXCEL_SUPPORT else "No")
    print("=" * 60 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
