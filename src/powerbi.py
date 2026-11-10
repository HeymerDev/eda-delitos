"""Genera el proyecto de Power BI (.pbip) del tablero, conectado a las vistas de Neon.

Un proyecto .pbip es la versión en texto de un archivo .pbix: Power BI Desktop lo abre con doble clic y se
puede guardar como .pbix. Se generan:

  powerbi/Delitos_Bucaramanga.pbip            proyecto versionado en git; el servidor es un valor de ejemplo
  powerbi_local/Delitos_Bucaramanga.pbip      copia para abrir en este equipo, con el servidor y la base
                                              tomados de DATABASE_URL (.env); está en .gitignore

Ninguno contiene usuario ni contraseña: Power BI los pide la primera vez que se actualizan los datos y los
guarda en el almacén de credenciales de Windows, no en el proyecto.

Contenido:
  * modelo en estrella sobre las cinco vistas de sql/03_vistas_powerbi.sql, con relaciones, tabla de fechas,
    columnas ordenadas y claves ocultas;
  * medidas DAX: total, variación % anual, % hurto, % SIN DATO, comuna con más casos y su participación;
  * una página de tablero con indicadores, segmentadores (año, comuna, grupo de delito, género), serie
    mensual, barras por grupo y por comuna, y matriz mes × año.

Formatos elegidos por compatibilidad: modelo en TMSL (model.bim) e informe en el formato clásico
(report.json), que Power BI Desktop abre sin activar funciones en versión preliminar.

Uso:
    python -m src.powerbi
"""
from __future__ import annotations

import json

import uuid
from pathlib import Path

from src.utils import ROOT

NOMBRE = "Delitos_Bucaramanga"
SERVIDOR_EJEMPLO = "ep-xxxx-xxxx.us-east-2.aws.neon.tech"
BASE_EJEMPLO = "neondb"
FACT = "vw_fact_delitos"

# -----------------------------------------------------------------------------
# Tema visual "Seguridad ciudadana": fondo oscuro de centro de monitoreo, rojo de alerta y ámbar de advertencia
# -----------------------------------------------------------------------------
FONDO_PAGINA = "#0F1115"
FONDO_VISUAL = "#1A1D23"
BORDE = "#2E333B"
TEXTO = "#E8EAED"
TEXTO_2 = "#AEB4BC"
ROJO_ALERTA = "#E53935"
AMBAR = "#FFB300"
TEMA = "TemaSeguridadCiudadana.json"

# Un color fijo por grupo de delito, del más grave (rojo oscuro) a los de menor gravedad (grises)
COLOR_GRUPO = {
    "HOMICIDIO": "#8E0000",
    "HOMICIDIO EN ACCIDENTE DE TRANSITO": "#BF360C",
    "HURTO": "#E53935",
    "DELITOS SEXUALES": "#8E24AA",
    "VIOLENCIA INTRAFAMILIAR": "#D81B60",
    "LESIONES PERSONALES": "#FB8C00",
    "LESIONES EN ACCIDENTE DE TRANSITO": "#FFB300",
    "OTROS DELITOS": "#78909C",
    "SIN DATO": "#546E7A",
}


def _solido(color: str) -> dict:
    return {"solid": {"color": color}}


def tema() -> dict:
    """Tema de Power BI (JSON de tema de informe)."""
    ejes = {"labelColor": _solido(TEXTO_2), "titleColor": _solido(TEXTO_2)}
    return {
        "name": "Seguridad ciudadana",
        "dataColors": ["#E53935", "#FFB300", "#D81B60", "#8E24AA", "#FB8C00", "#8E0000", "#78909C", "#BF360C"],
        "background": FONDO_VISUAL,
        "foreground": TEXTO,
        "tableAccent": ROJO_ALERTA,
        "good": "#43A047", "neutral": AMBAR, "bad": ROJO_ALERTA,
        "maximum": ROJO_ALERTA, "center": AMBAR, "minimum": "#2B0F12",
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": "#FF5252"},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": TEXTO},
            "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": AMBAR},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": TEXTO_2},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": _solido(FONDO_VISUAL), "transparency": 0}],
                "border": [{"show": True, "color": _solido(BORDE), "radius": 6}],
                "title": [{"fontColor": _solido(TEXTO)}],
                "categoryAxis": [ejes],
                "valueAxis": [{**ejes, "gridlineColor": _solido(BORDE)}],
                "legend": [{"labelColor": _solido(TEXTO_2)}],
            }},
            "page": {"*": {
                "background": [{"color": _solido(FONDO_PAGINA), "transparency": 0}],
                "outspace": [{"color": _solido(FONDO_PAGINA), "transparency": 0}],
            }},
            "card": {"*": {
                "labels": [{"color": _solido("#FF5252")}],
                "categoryLabels": [{"color": _solido(TEXTO_2)}],
            }},
            "slicer": {"*": {
                "header": [{"fontColor": _solido(AMBAR)}],
                "items": [{"fontColor": _solido(TEXTO), "background": _solido(FONDO_VISUAL)}],
            }},
            "pivotTable": {"*": {
                "columnHeaders": [{"fontColor": _solido(TEXTO), "backColor": _solido("#3A1014")}],
                "rowHeaders": [{"fontColor": _solido(TEXTO), "backColor": _solido(FONDO_VISUAL)}],
                "values": [{"fontColorPrimary": _solido(TEXTO), "backColorPrimary": _solido(FONDO_VISUAL),
                            "backColorSecondary": _solido(FONDO_VISUAL)}],
            }},
        },
    }

# -----------------------------------------------------------------------------
# Modelo semántico
# -----------------------------------------------------------------------------
# Columnas de cada vista: (nombre, tipo, opciones). Los tipos siguen la conversión de PostgreSQL a Power Query:
# integer/smallint -> int64, numeric -> double, text -> string, date -> dateTime, boolean -> boolean.
TABLAS: dict[str, list[tuple[str, str, dict]]] = {
    FACT: [
        ("orden", "int64", {"isHidden": True, "summarizeBy": "none"}),
        ("fecha_hecho", "dateTime", {"formatString": "dd/mm/yyyy", "isHidden": True}),
        ("territorio_key", "string", {"isHidden": True}),
        ("conducta_key", "string", {"isHidden": True}),
        ("victima_key", "string", {"isHidden": True}),
        ("zona", "string", {}),
        ("armas_medios", "string", {}),
        ("movil_agresor", "string", {}),
        ("movil_victima", "string", {}),
        ("latitud", "double", {"dataCategory": "Latitude", "summarizeBy": "none"}),
        ("longitud", "double", {"dataCategory": "Longitude", "summarizeBy": "none"}),
        ("flag_coord_faltante", "boolean", {}),
        ("flag_dia_atipico", "boolean", {}),
        ("flag_barrio_atipico", "boolean", {}),
        ("flag_barrio_comuna", "boolean", {}),
    ],
    "vw_dim_tiempo": [
        ("fecha", "dateTime", {"formatString": "dd/mm/yyyy", "isKey": True}),
        ("anio", "int64", {"summarizeBy": "none"}),
        ("trimestre", "int64", {"summarizeBy": "none"}),
        ("mes", "int64", {"summarizeBy": "none", "isHidden": True}),
        ("mes_nombre", "string", {"sortByColumn": "mes"}),
        ("anio_mes", "string", {}),
        ("dia", "int64", {"summarizeBy": "none"}),
        ("dia_semana", "int64", {"summarizeBy": "none", "isHidden": True}),
        ("dia_semana_nombre", "string", {"sortByColumn": "dia_semana"}),
        ("fin_de_semana", "boolean", {}),
    ],
    "vw_dim_territorio": [
        ("territorio_key", "string", {"isHidden": True}),
        ("comuna", "string", {}),
        ("barrio", "string", {}),
        ("tipo_territorio", "string", {}),
        ("comuna_numero", "int64", {"summarizeBy": "none"}),
    ],
    "vw_dim_conducta": [
        ("conducta_key", "string", {"isHidden": True}),
        ("conducta", "string", {}),
        ("descripcion_conducta", "string", {}),
        ("grupo_delito", "string", {}),
        ("clasificacion_delito", "string", {}),
    ],
    "vw_dim_victima": [
        ("victima_key", "string", {"isHidden": True}),
        ("genero", "string", {}),
        ("curso_vida", "string", {}),
        ("estado_civil", "string", {}),
    ],
}

RELACIONES = [
    ("fecha_hecho", "vw_dim_tiempo", "fecha"),
    ("territorio_key", "vw_dim_territorio", "territorio_key"),
    ("conducta_key", "vw_dim_conducta", "conducta_key"),
    ("victima_key", "vw_dim_victima", "victima_key"),
]

PCT = "0.0 %;-0.0 %;0.0 %"
MEDIDAS = [
    ("Total delitos", "COUNTROWS ( vw_fact_delitos )", "#,0"),
    ("Total año anterior", "CALCULATE ( [Total delitos], SAMEPERIODLASTYEAR ( vw_dim_tiempo[fecha] ) )", "#,0"),
    ("Variación % anual", "DIVIDE ( [Total delitos] - [Total año anterior], [Total año anterior] )", PCT),
    ("% hurto",
     "DIVIDE (\n    CALCULATE ( [Total delitos], vw_dim_conducta[grupo_delito] = \"HURTO\" ),\n"
     "    CALCULATE ( [Total delitos], REMOVEFILTERS ( vw_dim_conducta ) )\n)", PCT),
    ("% SIN DATO (género)",
     "DIVIDE (\n    CALCULATE ( [Total delitos], vw_dim_victima[genero] = \"SIN DATO\" ),\n"
     "    CALCULATE ( [Total delitos], REMOVEFILTERS ( vw_dim_victima[genero] ) )\n)", PCT),
    ("Comuna con más casos",
     "VAR t = ADDCOLUMNS ( VALUES ( vw_dim_territorio[comuna] ), \"@n\", [Total delitos] )\n"
     "RETURN MAXX ( TOPN ( 1, t, [@n], DESC ), vw_dim_territorio[comuna] )", None),
    ("Participación comuna con más casos",
     "VAR t = ADDCOLUMNS ( VALUES ( vw_dim_territorio[comuna] ), \"@n\", [Total delitos] )\n"
     "RETURN DIVIDE ( MAXX ( t, [@n] ), [Total delitos] )", PCT),
    ("Promedio diario", "DIVIDE ( [Total delitos], COUNTROWS ( vw_dim_tiempo ) )", "#,0.0"),
]


def _consulta_m(vista: str) -> list[str]:
    return [
        "let",
        "    Origen = PostgreSQL.Database(Servidor, BaseDatos),",
        f"    Vista = Origen{{[Schema=\"public\",Item=\"{vista}\"]}}[Data]",
        "in",
        "    Vista",
    ]


def modelo(servidor: str, base: str) -> dict:
    tablas = []
    for nombre, columnas in TABLAS.items():
        cols = []
        for col, tipo, opciones in columnas:
            c = {"name": col, "dataType": tipo, "sourceColumn": col, "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{nombre}.{col}"))}
            if tipo in ("int64", "double") and "summarizeBy" not in opciones:
                c["summarizeBy"] = "sum"
            c.update(opciones)
            cols.append(c)
        tabla = {
            "name": nombre,
            "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, nombre)),
            "columns": cols,
            "partitions": [{"name": nombre, "mode": "import", "source": {"type": "m", "expression": _consulta_m(nombre)}}],
        }
        if nombre == "vw_dim_tiempo":
            tabla["dataCategory"] = "Time"  # marcada como tabla de fechas (columna clave: fecha)
        if nombre == FACT:
            tabla["measures"] = [
                {"name": n, "expression": e, "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, f"medida.{n}")),
                 **({"formatString": f} if f else {})}
                for n, e, f in MEDIDAS
            ]
        tablas.append(tabla)

    def parametro(valor: str) -> str:
        return f'"{valor}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'

    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-ES",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "es-CO",
            "tables": tablas,
            "relationships": [
                {"name": f"r_{a}", "fromTable": FACT, "fromColumn": a, "toTable": t, "toColumn": b}
                for a, t, b in RELACIONES
            ],
            "expressions": [
                {"name": "Servidor", "kind": "m", "expression": parametro(servidor),
                 "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "param.Servidor"))},
                {"name": "BaseDatos", "kind": "m", "expression": parametro(base),
                 "lineageTag": str(uuid.uuid5(uuid.NAMESPACE_URL, "param.BaseDatos"))},
            ],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(["Servidor", "BaseDatos", *TABLAS])},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


# -----------------------------------------------------------------------------
# Informe (formato clásico report.json)
# -----------------------------------------------------------------------------
def _lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


ALIAS = {FACT: "f", "vw_dim_tiempo": "t", "vw_dim_territorio": "r", "vw_dim_conducta": "c", "vw_dim_victima": "v"}


def _campo(tabla: str, nombre: str, medida: bool = False) -> tuple[dict, str]:
    alias = ALIAS[tabla]  # alias único por tabla dentro de la consulta del visual
    tipo = "Measure" if medida else "Column"
    sel = {tipo: {"Expression": {"SourceRef": {"Source": alias}}, "Property": nombre}, "Name": f"{tabla}.{nombre}"}
    return sel, alias


def _visual(nombre: str, tipo: str, pos: tuple[int, int, int, int], roles: dict[str, list[tuple[str, str, bool]]],
            titulo: str | None = None, ordenar_por: tuple[str, str, bool] | None = None, objetos: dict | None = None) -> dict:
    x, y, w, h = pos
    selects, origen = [], {}
    proyecciones = {}
    for rol, campos in roles.items():
        proyecciones[rol] = []
        for tabla, campo, medida in campos:
            sel, alias = _campo(tabla, campo, medida)
            origen[alias] = tabla
            selects.append(sel)
            proyecciones[rol].append({"queryRef": sel["Name"]})
    consulta = {"Version": 2, "From": [{"Name": a, "Entity": t, "Type": 0} for a, t in origen.items()], "Select": selects}
    if ordenar_por:
        sel, _ = _campo(*ordenar_por)
        expr = {k: v for k, v in sel.items() if k != "Name"}
        consulta["OrderBy"] = [{"Direction": 2, "Expression": expr}]
    single = {"visualType": tipo, "projections": proyecciones, "prototypeQuery": consulta, "drillFilterOtherVisuals": True}
    if objetos:
        single["objects"] = objetos
    if titulo:
        single["vcObjects"] = {"title": [{"properties": {"show": _lit("true"), "text": _lit(f"'{titulo}'")}}]}
    config = {"name": nombre, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
              "singleVisual": single}
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(config, ensure_ascii=False),
            "filters": "[]"}


def _color_por_grupo() -> dict:
    """dataPoint con un selector por cada grupo de delito: el color sigue al grupo, no a su posición."""
    reglas = []
    for grupo, color in COLOR_GRUPO.items():
        reglas.append({
            "properties": {"fill": {"solid": {"color": _lit(f"'{color}'")}}},
            "selector": {"data": [{"scopeId": {"Comparison": {
                "ComparisonKind": 0,
                "Left": {"Column": {"Expression": {"SourceRef": {"Entity": "vw_dim_conducta"}}, "Property": "grupo_delito"}},
                "Right": {"Literal": {"Value": f"'{grupo}'"}},
            }}}]},
        })
    return {"dataPoint": reglas}


def _degradado_matriz() -> dict:
    """Formato condicional de la matriz: fondo de oscuro (pocos delitos) a rojo de alerta (muchos)."""
    medida = {"Measure": {"Expression": {"SourceRef": {"Entity": FACT}}, "Property": "Total delitos"}}
    regla = {"FillRule": {"Input": medida, "FillRule": {"linearGradient2": {
        "min": {"color": {"Literal": {"Value": "'#2B0F12'"}}},
        "max": {"color": {"Literal": {"Value": f"'{ROJO_ALERTA}'"}}},
        "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
    }}}}
    return {"values": [{
        "properties": {"backColor": {"solid": {"color": {"expr": regla}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{FACT}.Total delitos"},
    }]}


def informe() -> dict:
    T, R, C, V = "vw_dim_tiempo", "vw_dim_territorio", "vw_dim_conducta", "vw_dim_victima"
    color_barras = {"dataPoint": [{"properties": {"fill": {"solid": {"color": _lit(f"'{ROJO_ALERTA}'")}}}}]}
    color_linea = {"dataPoint": [{"properties": {"fill": {"solid": {"color": _lit(f"'{ROJO_ALERTA}'")}}}}],
                   "lineStyles": [{"properties": {"strokeWidth": _lit("3D")}}]}
    lista_desplegable = {"data": [{"properties": {"mode": _lit("'Dropdown'")}}]}
    visuales = [
        # Fila de indicadores
        _visual("kpi_total", "card", (20, 20, 190, 100), {"Values": [(FACT, "Total delitos", True)]}),
        _visual("kpi_var", "card", (220, 20, 190, 100), {"Values": [(FACT, "Variación % anual", True)]}),
        _visual("kpi_hurto", "card", (420, 20, 190, 100), {"Values": [(FACT, "% hurto", True)]}),
        _visual("kpi_sindato", "card", (620, 20, 190, 100), {"Values": [(FACT, "% SIN DATO (género)", True)]}),
        _visual("kpi_comuna", "card", (820, 20, 240, 100), {"Values": [(FACT, "Comuna con más casos", True)]}),
        _visual("kpi_part", "card", (1070, 20, 190, 100), {"Values": [(FACT, "Participación comuna con más casos", True)]}),
        # Segmentadores
        _visual("seg_anio", "slicer", (20, 135, 300, 70), {"Values": [(T, "anio", False)]}, "Año",
                objetos={"data": [{"properties": {"mode": _lit("'Between'")}}]}),
        _visual("seg_comuna", "slicer", (330, 135, 300, 70), {"Values": [(R, "comuna", False)]}, "Comuna",
                objetos=lista_desplegable),
        _visual("seg_grupo", "slicer", (640, 135, 300, 70), {"Values": [(C, "grupo_delito", False)]}, "Grupo de delito",
                objetos=lista_desplegable),
        _visual("seg_genero", "slicer", (950, 135, 310, 70), {"Values": [(V, "genero", False)]}, "Género de la víctima",
                objetos=lista_desplegable),
        # Visualizaciones
        _visual("serie_mensual", "lineChart", (20, 220, 760, 230),
                {"Category": [(T, "anio_mes", False)], "Y": [(FACT, "Total delitos", True)]}, "Delitos por mes",
                objetos=color_linea),
        _visual("barras_grupo", "clusteredBarChart", (790, 220, 470, 230),
                {"Category": [(C, "grupo_delito", False)], "Y": [(FACT, "Total delitos", True)]}, "Delitos por grupo",
                ordenar_por=(FACT, "Total delitos", True), objetos=_color_por_grupo()),
        _visual("barras_comuna", "clusteredBarChart", (20, 460, 470, 250),
                {"Category": [(R, "comuna", False)], "Y": [(FACT, "Total delitos", True)]}, "Delitos por comuna",
                ordenar_por=(FACT, "Total delitos", True), objetos=color_barras),
        _visual("matriz_mes_anio", "pivotTable", (500, 460, 760, 250),
                {"Rows": [(T, "mes_nombre", False)], "Columns": [(T, "anio", False)],
                 "Values": [(FACT, "Total delitos", True)]}, "Delitos por mes y año", objetos=_degradado_matriz()),
    ]
    config = {
        "version": "5.43",
        # El tema propio se registra como recurso del informe (StaticResources/RegisteredResources)
        "themeCollection": {"customTheme": {"name": TEMA, "version": "5.43", "type": 1}},
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                     "useStylableVisualContainerHeader": True, "exportDataMode": 1, "useEnhancedTooltips": True},
    }
    return {
        "config": json.dumps(config),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {
            "name": "RegisteredResources", "type": 1, "disabled": False,
            "items": [{"type": 202, "path": TEMA, "name": TEMA}],
        }}],
        "sections": [{
            "name": "ReportSectionTablero",
            "displayName": "Tablero",
            "displayOption": 1,
            "width": 1280,
            "height": 720,
            # Fondo oscuro también en la página (además del tema), por si el tema no se carga
            "config": json.dumps({"objects": {
                "background": [{"properties": {"color": {"solid": {"color": _lit(f"'{FONDO_PAGINA}'")}},
                                               "transparency": _lit("0D")}}],
                "outspace": [{"properties": {"color": {"solid": {"color": _lit(f"'{FONDO_PAGINA}'")}}}}],
            }}),
            "filters": "[]",
            "visualContainers": visuales,
        }],
    }


# -----------------------------------------------------------------------------
# Escritura del proyecto
# -----------------------------------------------------------------------------
def _escribir(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido, ensure_ascii=False, indent=2)
    ruta.write_text(texto, encoding="utf-8")


def generar(destino: Path, servidor: str, base: str) -> Path:
    # Se sobrescriben los archivos uno a uno (sin borrar la carpeta) para conservar la caché .pbi de
    # Power BI Desktop si existe, y para no fallar si Power BI tiene la carpeta abierta.
    _escribir(destino / f"{NOMBRE}.Report" / "StaticResources" / "RegisteredResources" / TEMA, tema())
    _escribir(destino / f"{NOMBRE}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    _escribir(destino / f"{NOMBRE}.SemanticModel" / "definition.pbism", {"version": "1.0", "settings": {}})
    _escribir(destino / f"{NOMBRE}.SemanticModel" / "model.bim", modelo(servidor, base))
    _escribir(destino / f"{NOMBRE}.Report" / "definition.pbir", {
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}, "byConnection": None},
    })
    _escribir(destino / f"{NOMBRE}.Report" / "report.json", informe())
    return destino / f"{NOMBRE}.pbip"


def servidor_y_base() -> tuple[str, str] | None:
    """Host y nombre de la base desde DATABASE_URL, sin leer ni mostrar usuario ni contraseña."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy.engine import make_url

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    u = make_url(url.replace("postgres://", "postgresql://", 1))
    return (u.host, u.database) if u.host and u.database else None


def main() -> None:
    publico = generar(ROOT / "powerbi", SERVIDOR_EJEMPLO, BASE_EJEMPLO)
    print(f"Proyecto versionado: {publico.relative_to(ROOT)} (servidor de ejemplo)")
    datos = servidor_y_base()
    if datos:
        local = generar(ROOT / "powerbi_local", *datos)
        print(f"Copia local lista para abrir: {local.relative_to(ROOT)} (servidor y base tomados de .env)")
    else:
        print("No hay DATABASE_URL en .env: abra el proyecto versionado y cambie los parámetros "
              "Servidor y BaseDatos en Inicio > Transformar datos > Editar parámetros.")


if __name__ == "__main__":
    main()
