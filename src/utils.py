"""Utilidades compartidas: rutas, lectura del dataset original y conexión a Neon.

La cadena de conexión se lee de la variable de entorno DATABASE_URL (archivo .env).
Nunca se imprime ni se registra en logs.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"

NOMBRE_BASE = "40Delitos_ocurridos_en_el_Municipio_de_Bucaramanga_20261026"
XLSX_ORIGINAL = DATA_RAW / f"{NOMBRE_BASE}.xlsx"
CSV_ORIGINAL = DATA_RAW / f"{NOMBRE_BASE}.csv"
TOTAL_REGISTROS = 135_076

# Nombre original de la columna -> nombre en la tabla delitos_raw (snake_case, sin espacios)
COLUMNAS_RAW = {
    "ORDEN": "orden",
    "ARMAS_MEDIOS": "armas_medios",
    "BARRIOS_HECHO": "barrios_hecho",
    "LATITUD": "latitud",
    "LONGITUD": "longitud",
    "ZONA": "zona",
    "NOM_COMUNA": "nom_comuna",
    "ANO": "ano",
    "MES": "mes",
    "DIA": "dia",
    "DIA_SEMANA": "dia_semana",
    "DESCRIPCION_CONDUCTA": "descripcion_conducta",
    "CONDUCTA": "conducta",
    "CLASIFICACIONES DELITO": "clasificaciones_delito",
    "CURSO_DE_VIDA": "curso_de_vida",
    "ESTADO_CIVIL_PERSONA": "estado_civil_persona",
    "GENERO": "genero",
    "MOVIL_AGRESOR": "movil_agresor",
    "MOVIL_VICTIMA": "movil_victima",
}


def sha256(ruta: Path) -> str:
    """Huella SHA-256 de un archivo: permite demostrar que el original no cambió."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_xlsx_original(ruta: Path = XLSX_ORIGINAL) -> pd.DataFrame:
    """Lee el xlsx original sin ninguna conversión: todas las celdas como texto.

    keep_default_na=False evita que pandas convierta textos como "NA" en nulos,
    de modo que el DataFrame refleja exactamente lo publicado.
    """
    return pd.read_excel(ruta, dtype=str, keep_default_na=False, na_values=[], engine="openpyxl")


def leer_csv_original(ruta: Path = CSV_ORIGINAL) -> pd.DataFrame:
    """Lee la copia CSV del original, también como texto y sin interpretar faltantes."""
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, na_values=[], encoding="utf-8")


def get_engine():
    """Crea el engine de SQLAlchemy hacia Neon a partir de DATABASE_URL (.env).

    Se fuerza sslmode=require porque Neon solo acepta conexiones cifradas.
    """
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "No se encontró DATABASE_URL. Copie .env.example como .env y escriba su cadena de Neon."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True, connect_args={"sslmode": "require"})


# =============================================================================
# Coordenadas
# =============================================================================
# Área de referencia de Bucaramanga (rectángulo aproximado que contiene el municipio).
LAT_MIN, LAT_MAX = 7.0, 7.25
LON_MIN, LON_MAX = -73.25, -73.0


def reconstruir_coordenada(texto: str, digitos_enteros: int) -> float | None:
    """Reconstruye una coordenada publicada con separadores de miles mal puestos.

    El original guarda las coordenadas como texto con comas en posiciones arbitrarias
    ('7,170,557,382', '-7,312,605', '71,303,582,541'). Como en Bucaramanga la latitud
    siempre tiene 1 dígito entero (7.xxx) y la longitud 2 (-73.xxx), basta con quitar
    todo lo que no sea dígito e insertar el punto decimal en la posición conocida:
        '7,170,557,382'  (1 entero) -> 7.170557382
        '-7,312,605'     (2 enteros) -> -73.12605
    Devuelve None si el texto no contiene dígitos (marcadores 'xx.xxxx' / '-yy.yyyy').
    """
    if texto is None:
        return None
    t = str(texto).strip()
    digitos = re.sub(r"\D", "", t)
    if not digitos:
        return None
    valor = float(f"{digitos[:digitos_enteros]}.{digitos[digitos_enteros:] or '0'}")
    return -valor if t.startswith("-") else valor


def corregir_coordenadas(latitud: pd.Series, longitud: pd.Series) -> pd.DataFrame:
    """Aplica la reconstrucción a cada par (latitud, longitud) y clasifica el resultado.

    Pasos:
      1. Si la latitud trae signo '-' y la longitud no, las columnas vienen intercambiadas
         (caso de 2020): se intercambian antes de reconstruir.
      2. Se reconstruye cada valor con reconstruir_coordenada.
      3. Bucaramanga está al occidente de Greenwich: una longitud positiva se corrige a negativa.
      4. Si el par cae fuera del área de Bucaramanga, no es recuperable: se anula.

    Devuelve un DataFrame con lat, lon y estado: ok, intercambiada, signo, faltante o fuera_area.
    """
    lat_txt = latitud.astype(str).str.strip()
    lon_txt = longitud.astype(str).str.strip()
    intercambio = (lat_txt.str.startswith("-") & ~lon_txt.str.startswith("-")).to_numpy()
    lat_fuente = np.where(intercambio, lon_txt, lat_txt)
    lon_fuente = np.where(intercambio, lat_txt, lon_txt)

    lat = pd.Series([reconstruir_coordenada(t, 1) for t in lat_fuente], index=latitud.index, dtype="float64")
    lon = pd.Series([reconstruir_coordenada(t, 2) for t in lon_fuente], index=latitud.index, dtype="float64")
    signo = (lon > 0) & ~intercambio
    lon = -lon.abs()

    estado = pd.Series("ok", index=latitud.index, dtype="object")
    estado[intercambio] = "intercambiada"
    estado[signo] = "signo"
    faltante = lat.isna() | lon.isna()
    estado[faltante] = "faltante"
    fuera = ~faltante & ~(lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX))
    estado[fuera] = "fuera_area"
    lat[faltante | fuera] = np.nan
    lon[faltante | fuera] = np.nan
    return pd.DataFrame({"lat": lat, "lon": lon, "estado": estado})


# =============================================================================
# Formato (cifras en español: 135.076 y 12,5 %)
# =============================================================================
def fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_pct(x, decimales: int = 1) -> str:
    return f"{x:.{decimales}f}".replace(".", ",") + " %"


def fmt_dec(x, decimales: int = 2) -> str:
    return f"{x:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabla_md(df: pd.DataFrame, max_filas: int | None = None) -> str:
    """Convierte un DataFrame en tabla Markdown. Los enteros se escriben con punto de miles."""
    if max_filas is not None:
        df = df.head(max_filas)

    def celda(v):
        if isinstance(v, (bool, np.bool_)):
            return "Sí" if v else "No"
        if isinstance(v, (int, np.integer)):
            return fmt_int(v)
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else fmt_dec(v)
        return str(v).replace("|", "\\|").replace("\n", " ")

    filas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * df.shape[1]]
    filas += ["| " + " | ".join(celda(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join(filas)


# =============================================================================
# Estilo de los gráficos (plotly) y catálogo de figuras
# =============================================================================
FUENTE_FIGURAS = "Fuente: Elaboración propia con datos de la Alcaldía de Bucaramanga (2023)."

# Paleta de referencia validada para daltonismo (modo claro).
COLOR = {
    "superficie": "#fcfcfb", "tinta": "#0b0b0b", "tinta2": "#52514e", "tenue": "#898781",
    "rejilla": "#e1e0d9", "eje": "#c3c2b7",
    "serie": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "critico": "#d03b3b",
}
SECUENCIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Orden de las figuras en el artículo (docs/resultados.md). El número de cada figura es su
# posición en esta lista, así la app, los PNG y el documento usan siempre la misma numeración.
FIGURAS: list[tuple[str, str]] = [
    # Objetivo 1 · Actividad 1.1
    ("neon_proyecto", "Proyecto y base de datos creados en Neon"),
    ("sql_create_raw", "Definición de la tabla delitos_raw en PostgreSQL"),
    ("neon_verificacion", "Verificación de la carga de delitos_raw en el editor SQL de Neon"),
    ("estructura", "Estructura del conjunto de datos original: variables, tipos y cardinalidad"),
    # Actividad 1.2
    ("faltantes", "Marcadores de dato faltante por variable en el conjunto original"),
    ("duplicados_anio", "Registros duplicados (sin considerar ORDEN) por año: observados frente a esperados por azar"),
    ("duplicados_muestra", "Muestra de grupos de registros duplicados"),
    ("coord_formatos", "Formatos de texto encontrados en las coordenadas"),
    ("inconsistencias", "Resumen de errores de formato e inconsistencias entre columnas"),
    # Actividad 1.3
    ("informe", "Informe de diagnóstico de calidad generado por la aplicación"),
    # Objetivo 2 · Actividad 2.1
    ("decisiones", "Tabla de decisiones de limpieza"),
    ("codigo_coordenadas", "Función de reconstrucción de las coordenadas"),
    ("coord_antes", "Coordenadas con solo la reconstrucción decimal, antes de corregir intercambios y signos"),
    ("coord_despues", "Ubicación de los delitos con coordenadas válidas después de la corrección"),
    ("antes_despues", "Registros del conjunto original y del conjunto limpio, y registros eliminados por motivo"),
    # Actividad 2.2
    ("faltantes_tratamiento", "Tratamiento de los valores faltantes según el tipo de variable"),
    # Actividad 2.3
    ("box_diario", "Diagramas de caja del número de delitos por día, por año"),
    ("box_barrio", "Diagramas de caja del número de delitos por barrio en escala lineal y logarítmica"),
    ("validacion", "Validación del conjunto de datos limpio"),
    ("neon_limpios", "Verificación de la carga de delitos_limpios y delitos_eliminados en el editor SQL de Neon"),
    # Objetivo 3 · Actividad 3.1
    ("frecuencias", "Frecuencias y porcentajes de las categorías principales de las variables del delito y de la víctima"),
    ("frec_grupo", "Registros por grupo de delito, 2010–2021"),
    ("desc_conteos", "Estadísticas descriptivas de los conteos de delitos por día, mes, barrio y comuna"),
    ("hist_diario", "Histograma del número de delitos registrados por día"),
    ("hist_barrio", "Histograma del número de delitos registrados por barrio"),
    # Actividad 3.2
    ("serie_anual", "Registros por año de los cinco grupos de delito más frecuentes"),
    ("serie_mensual", "Serie mensual de registros de delitos, 2010–2021"),
    ("dia_semana", "Registros por día de la semana"),
    ("heat_mes_anio", "Mapa de calor de registros por mes y año"),
    ("heat_dia_mes", "Mapa de calor del promedio diario de delitos por día de la semana y mes"),
    ("cambio_2020", "Variación de los registros de 2020 frente al promedio 2017–2019, por grupo de delito"),
    ("comunas", "Registros por comuna y corregimiento"),
    ("top_barrios", "Los veinte barrios con más registros de delitos"),
    ("concentracion_hurto", "Curva de concentración de los hurtos por barrio"),
    # Actividad 3.3
    ("cont_genero", "Tabla de contingencia del grupo de delito por género de la víctima (porcentaje por fila)"),
    ("cont_curso", "Tabla de contingencia del grupo de delito por curso de vida de la víctima (porcentaje por fila)"),
    ("cont_estado", "Tabla de contingencia del grupo de delito por estado civil de la víctima (porcentaje por fila)"),
    ("chi2", "Pruebas de chi-cuadrado y V de Cramér entre el grupo de delito y las características de la víctima"),
    ("spearman", "Correlación de Spearman entre los conteos de grupos de delito por barrio y año"),
    ("dispersion", "Dispersión de hurtos y casos de violencia intrafamiliar por barrio y año"),
    # Objetivo 4 · Actividad 4.1
    ("seleccion_graficos", "Criterios de selección del tipo de gráfico según la variable y el análisis"),
    # Actividad 4.2
    ("mapa_densidad", "Mapa de densidad de los delitos con ubicación válida, 2010–2021"),
    ("mapa_grupos", "Mapas de densidad por grupo de delito"),
    ("sql_vistas", "Vista de hechos para Power BI en PostgreSQL"),
    ("pbi_modelo", "Modelo de datos en estrella en Power BI"),
    ("pbi_tablero", "Tablero de Power BI con indicadores, segmentadores y visualizaciones"),
    # Actividad 4.3
    ("hallazgos", "Página de hallazgos de la aplicación: patrón, cifra, evidencia y contraste con los antecedentes"),
]


def figura(clave: str) -> tuple[int, str]:
    """Devuelve (número, título) de una figura del catálogo."""
    for i, (k, titulo) in enumerate(FIGURAS, 1):
        if k == clave:
            return i, titulo
    raise KeyError(f"Figura no registrada en utils.FIGURAS: {clave}")


def titulo_figura(clave: str) -> str:
    n, t = figura(clave)
    return f"Figura {n}. {t}"


def estilo_figura(fig, clave: str, alto: int = 420):
    """Aplica el estilo común: título numerado arriba, fuente abajo, ejes y rejilla discretos."""
    fig.update_layout(
        title={"text": f"<b>{titulo_figura(clave)}</b>", "x": 0, "xanchor": "left",
               "yref": "container", "y": 0.985, "yanchor": "top",
               "font": {"size": 15, "color": COLOR["tinta"]}},
        height=alto,
        paper_bgcolor=COLOR["superficie"], plot_bgcolor=COLOR["superficie"],
        font={"family": "system-ui, -apple-system, 'Segoe UI', sans-serif", "size": 12, "color": COLOR["tinta2"]},
        margin={"l": 10, "r": 20, "t": 75, "b": 100},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "title": None},
        hoverlabel={"bgcolor": "white", "font_size": 12},
        separators=",.",
    )
    fig.update_xaxes(gridcolor=COLOR["rejilla"], linecolor=COLOR["eje"], zeroline=False, title_font_color=COLOR["tinta2"])
    fig.update_yaxes(gridcolor=COLOR["rejilla"], linecolor=COLOR["eje"], zeroline=False, title_font_color=COLOR["tinta2"])
    fig.add_annotation(text=FUENTE_FIGURAS, xref="paper", yref="paper", x=0, y=0, yshift=-95,
                       xanchor="left", yanchor="bottom", showarrow=False,
                       font={"size": 11, "color": COLOR["tenue"]})
    return fig
