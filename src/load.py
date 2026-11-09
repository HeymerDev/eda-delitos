"""Copia CSV del original y carga de las tablas en PostgreSQL (Neon).

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m src.load csv          # xlsx original -> copia CSV UTF-8 (sin modificar nada) + verificación
    python -m src.load schema       # ejecuta sql/01_schema.sql en Neon
    python -m src.load raw          # carga la copia CSV en delitos_raw (135.076 filas)
    python -m src.load limpios      # carga delitos_limpios y delitos_eliminados (Fase 2)
    python -m src.load verificar    # ejecuta sql/02_carga_verificacion.sql y muestra los resultados
"""
from __future__ import annotations

import argparse
import io
import sys

import pandas as pd

from src.utils import (
    COLUMNAS_RAW,
    CSV_ORIGINAL,
    DATA_PROCESSED,
    DATA_RAW,
    SQL_DIR,
    TOTAL_REGISTROS,
    XLSX_ORIGINAL,
    get_engine,
    leer_csv_original,
    leer_xlsx_original,
    sha256,
)


# --------------------------------------------------------------------------- CSV
def exportar_csv() -> None:
    """Exporta el xlsx a CSV UTF-8 sin transformar ningún valor y verifica la copia."""
    huella_antes = sha256(XLSX_ORIGINAL)
    df = leer_xlsx_original()
    if len(df) != TOTAL_REGISTROS:
        sys.exit(f"El xlsx tiene {len(df)} filas; se esperaban {TOTAL_REGISTROS}.")
    df.to_csv(CSV_ORIGINAL, index=False, encoding="utf-8", lineterminator="\n")

    copia = leer_csv_original()
    identicos = copia.equals(df)
    huella_despues = sha256(XLSX_ORIGINAL)
    print(f"Filas xlsx: {len(df):,} | filas CSV: {len(copia):,} | columnas: {df.shape[1]}")
    print(f"Contenido CSV idéntico al xlsx (celda a celda): {identicos}")
    print(f"xlsx sin cambios tras la exportación (SHA-256 igual): {huella_antes == huella_despues}")
    if not identicos or huella_antes != huella_despues:
        sys.exit("La copia no es fiel al original.")

    (DATA_RAW / "SHA256SUMS.txt").write_text(
        f"{huella_despues}  {XLSX_ORIGINAL.name}\n{sha256(CSV_ORIGINAL)}  {CSV_ORIGINAL.name}\n",
        encoding="utf-8",
    )
    print("Huellas guardadas en data/raw/SHA256SUMS.txt")


# --------------------------------------------------------------------------- Neon
def _ejecutar_archivo_sql(nombre: str) -> None:
    sql = (SQL_DIR / nombre).read_text(encoding="utf-8")
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
    print(f"{nombre} ejecutado correctamente.")


def _copy(cur, tabla: str, columnas: list[str], df: pd.DataFrame) -> None:
    """Carga masiva con COPY ... FROM STDIN (mucho más rápida que INSERT por fila)."""
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N", lineterminator="\n")
    buf.seek(0)
    cur.copy_expert(
        f"COPY {tabla} ({', '.join(columnas)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf
    )


def cargar_raw() -> None:
    """Carga la copia CSV en delitos_raw tal cual (solo se renombran las columnas)."""
    df = leer_csv_original()
    if len(df) != TOTAL_REGISTROS:
        sys.exit(f"La copia CSV tiene {len(df)} filas; se esperaban {TOTAL_REGISTROS}.")
    df = df.rename(columns=COLUMNAS_RAW)[list(COLUMNAS_RAW.values())]
    conn = get_engine().raw_connection()
    try:
        with conn.cursor() as cur:
            # Una sola transacción: si algo falla, la tabla queda como estaba.
            cur.execute("TRUNCATE delitos_raw CASCADE")
            _copy(cur, "delitos_raw", list(df.columns), df)
            cur.execute("SELECT COUNT(*) FROM delitos_raw")
            n = cur.fetchone()[0]
        if n != TOTAL_REGISTROS:
            conn.rollback()
            sys.exit(f"Se cargaron {n} filas; se esperaban {TOTAL_REGISTROS}. Se revirtió la carga.")
        conn.commit()
        print(f"delitos_raw cargada: {n:,} filas.")
    finally:
        conn.close()


def cargar_limpios() -> None:
    """Carga el dataset limpio y el registro de eliminaciones generados por src/cleaning.py."""
    limpios = pd.read_parquet(DATA_PROCESSED / "delitos_limpios.parquet")
    eliminados = pd.read_parquet(DATA_PROCESSED / "delitos_eliminados.parquet")
    total = len(limpios) + len(eliminados)
    if total != TOTAL_REGISTROS:
        sys.exit(f"limpios + eliminados = {total}; se esperaban {TOTAL_REGISTROS}.")
    conn = get_engine().raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE delitos_limpios, delitos_eliminados")
            _copy(cur, "delitos_limpios", list(limpios.columns), limpios)
            _copy(cur, "delitos_eliminados", list(eliminados.columns), eliminados)
        conn.commit()
        print(f"delitos_limpios: {len(limpios):,} filas | delitos_eliminados: {len(eliminados):,} filas.")
    finally:
        conn.close()


def _sentencias(sql: str) -> list[str]:
    """Divide un archivo SQL en sentencias (una sentencia termina en una línea con ';')."""
    sentencias, actual = [], []
    for linea in sql.splitlines():
        actual.append(linea)
        if linea.rstrip().endswith(";"):
            texto = "\n".join(actual).strip()
            if any(l.strip() and not l.strip().startswith("--") for l in actual):
                sentencias.append(texto)
            actual = []
    return sentencias


def verificar() -> None:
    from sqlalchemy import text

    sql = (SQL_DIR / "02_carga_verificacion.sql").read_text(encoding="utf-8")
    engine = get_engine()
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 100)
    with engine.connect() as conn:
        for i, s in enumerate(_sentencias(sql), 1):
            # El título es el primer comentario numerado ("-- 1. ...") que precede a la consulta
            titulo = next((l[3:].strip() for l in s.splitlines() if l[:3] == "-- " and l[3:4].isdigit()),
                          f"Consulta {i}")
            print(f"\n=== {titulo} ===")
            print(pd.read_sql_query(text(s), conn).to_string(index=False))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("accion", choices=["csv", "schema", "raw", "limpios", "verificar"])
    a = p.parse_args()
    {
        "csv": exportar_csv,
        "schema": lambda: _ejecutar_archivo_sql("01_schema.sql"),
        "raw": cargar_raw,
        "limpios": cargar_limpios,
        "verificar": verificar,
    }[a.accion]()


if __name__ == "__main__":
    main()
