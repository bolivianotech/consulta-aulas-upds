"""
API - Consulta de Aulas por Docente
Universidad Privada Domingo Savio (UPDS)

Endpoints:
    GET /api/docentes          → Lista todos los docentes disponibles
    GET /api/consulta          → Consulta aulas por nombre de docente (query param: ?docente=...)
    GET /api/aulas             → Lista todas las asignaciones (con filtros opcionales)
    GET /api/health            → Verificación de estado del servicio
"""

from flask import Flask, jsonify, request
import json
import os
import unicodedata

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Carga de datos desde el JSON exportado del xlsx
# ---------------------------------------------------------------------------
DATA_PATH = os.path.join(os.path.dirname(__file__), "consultas_data.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    ASIGNACIONES: list[dict] = json.load(f)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Normaliza texto para búsqueda: minúsculas, sin acentos, sin espacios extra."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


def buscar_docente(query: str) -> list[dict]:
    """Retorna todas las asignaciones que coinciden con el query del docente (búsqueda parcial)."""
    q = normalizar(query)
    resultados = []
    for item in ASIGNACIONES:
        docente_norm = normalizar(item["docente"])
        if q in docente_norm:
            resultados.append(item)
    return resultados


def get_docentes_unicos() -> list[str]:
    """Retorna lista ordenada de docentes únicos, excluyendo 'NO DEFINIDO'."""
    docs = set()
    for item in ASIGNACIONES:
        nombre = item["docente"].strip()
        if nombre and nombre.upper() != "NO DEFINIDO":
            docs.add(nombre)
    return sorted(docs, key=lambda x: normalizar(x))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    """Verificación de estado del servicio."""
    return jsonify({
        "status": "ok",
        "total_asignaciones": len(ASIGNACIONES),
        "total_docentes": len(get_docentes_unicos())
    })


@app.route("/api/docentes", methods=["GET"])
def docentes():
    """
    Lista todos los docentes disponibles.
    Query params opcionales:
        ?q=<texto>   → Filtro por nombre (búsqueda parcial)
    """
    q = request.args.get("q", "").strip()
    if q:
        # Filtrar docentes que coincidan con el query
        q_norm = normalizar(q)
        docs = [
            d for d in get_docentes_unicos()
            if q_norm in normalizar(d)
        ]
    else:
        docs = get_docentes_unicos()

    return jsonify({
        "docentes": docs,
        "total": len(docs)
    })


@app.route("/api/consulta", methods=["GET"])
def consulta():
    """
    Consulta principal: busca aulas asignadas a un docente.
    
    Query params:
        ?docente=<nombre>   (OBLIGATORIO) Nombre o parte del nombre del docente
        ?turno=<turno>      (opcional)    Filtrar por turno: MAÑANA | MEDIO DIA | TARDE | NOCHE
    
    Ejemplo:
        GET /api/consulta?docente=Miranda
        GET /api/consulta?docente=Miranda+Hoyos&turno=MAÑANA
    """
    docente_query = request.args.get("docente", "").strip()
    turno_filtro = request.args.get("turno", "").strip().upper()

    if not docente_query:
        return jsonify({
            "error": "Parámetro 'docente' es requerido.",
            "ejemplo": "/api/consulta?docente=Miranda"
        }), 400

    resultados = buscar_docente(docente_query)

    # Filtro por turno si se proporcionó
    if turno_filtro:
        resultados = [r for r in resultados if r["turno"].upper() == turno_filtro]

    # Determinar nombre canónico del docente (si hay resultados)
    nombre_docente = resultados[0]["docente"] if resultados else None

    return jsonify({
        "docente": nombre_docente,
        "consulta": docente_query,
        "turno_filtro": turno_filtro or None,
        "total_asignaciones": len(resultados),
        "asignaciones": resultados
    })


@app.route("/api/aulas", methods=["GET"])
def aulas():
    """
    Lista todas las asignaciones con filtros opcionales.
    
    Query params opcionales:
        ?turno=<turno>       Filtrar por turno
        ?materia=<nombre>    Filtrar por materia (búsqueda parcial)
        ?aula=<codigo>       Filtrar por código de aula (búsqueda parcial)
    """
    turno = request.args.get("turno", "").strip().upper()
    materia = request.args.get("materia", "").strip()
    aula = request.args.get("aula", "").strip()

    resultados = ASIGNACIONES

    if turno:
        resultados = [r for r in resultados if r["turno"].upper() == turno]
    if materia:
        mat_norm = normalizar(materia)
        resultados = [r for r in resultados if mat_norm in normalizar(r["materia"])]
    if aula:
        aula_norm = normalizar(aula)
        resultados = [r for r in resultados if aula_norm in normalizar(r["aula"])]

    return jsonify({
        "total": len(resultados),
        "filtros": {
            "turno": turno or None,
            "materia": materia or None,
            "aula": aula or None
        },
        "asignaciones": resultados
    })


# ---------------------------------------------------------------------------
# CORS (para que la landing pueda consumir la API desde otro origen)
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
