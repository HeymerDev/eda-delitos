"""Utilidades compartidas: rutas, lectura del dataset original y conexión a Neon.

La cadena de conexión se lee de la variable de entorno DATABASE_URL (archivo .env).
Nunca se imprime ni se registra en logs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

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
