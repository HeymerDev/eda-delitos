"""Funciones compartidas por las páginas de la aplicación Streamlit."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import diagnostico  # noqa: E402
from src.utils import COLUMNAS_RAW, FUENTE_FIGURAS, leer_csv_original, titulo_figura  # noqa: E402

FUENTE_TEXTO = FUENTE_FIGURAS.removeprefix("Fuente: ")


def configurar_pagina(titulo: str) -> None:
    st.set_page_config(page_title=f"{titulo} · Delitos Bucaramanga", layout="wide")
    st.markdown(
        """
        <style>
          .block-container {padding-top: 2.2rem; max-width: 1250px;}
          .fig-titulo {font-weight: 700; font-size: 1.0rem; margin: 0.6rem 0 0.3rem 0;}
          .fig-fuente {color: #898781; font-size: 0.8rem; margin: 0.2rem 0 1.2rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _neon_habilitado() -> bool:
    """Neon se usa si hay DATABASE_URL y no se forzó la fuente local (FUENTE_DATOS=local)."""
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    return os.getenv("FUENTE_DATOS", "auto").lower() != "local" and bool(os.getenv("DATABASE_URL"))


@st.cache_data(show_spinner="Cargando el conjunto original…")
def cargar_original() -> tuple[pd.DataFrame, str]:
    """Lee el original desde delitos_raw en Neon; si no es posible, desde la copia CSV local."""
    if _neon_habilitado():
        try:
            from src.utils import get_engine

            with get_engine().connect() as conn:
                df = pd.read_sql_query("SELECT * FROM delitos_raw ORDER BY orden", conn)
            inverso = {v: k for k, v in COLUMNAS_RAW.items()}
            df = df.rename(columns=inverso).astype(str)
            return df, "Neon (tabla delitos_raw)"
        except Exception:  # noqa: BLE001 - cualquier fallo de red o de tabla usa el respaldo local
            pass
    return leer_csv_original(), "copia CSV local del original"


@st.cache_data(show_spinner="Calculando el diagnóstico…")
def cargar_diagnostico() -> dict:
    """Usa los resultados de `python -m src.diagnostico` si existen; si no, los calcula."""
    r = diagnostico.cargar_resultados()
    if r is None:
        df, _ = cargar_original()
        r = diagnostico.diagnosticar(df)
        diagnostico.guardar(r)
    return r


def titulo(clave: str) -> None:
    st.markdown(f'<div class="fig-titulo" id="fig-{clave}">{titulo_figura(clave)}</div>', unsafe_allow_html=True)


def fuente() -> None:
    st.markdown(f'<div class="fig-fuente"><i>Fuente:</i> {FUENTE_TEXTO}</div>', unsafe_allow_html=True)


def _formatear(df: pd.DataFrame) -> pd.DataFrame:
    """Cifras en formato español para tablas estáticas (135.076 y 12,34)."""
    from src.utils import fmt_dec, fmt_int

    out = df.reset_index(drop=True).copy()
    for c in out.columns:
        if pd.api.types.is_integer_dtype(out[c]):
            out[c] = out[c].map(fmt_int)
        elif pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].map(lambda v: "" if pd.isna(v) else fmt_dec(v))
        else:
            # st.table interpreta Markdown: '03. SAN FRANCISCO' se volvería una lista numerada.
            out[c] = out[c].astype(str).str.replace(r"^(\d+)\. ", r"\1\\. ", regex=True)
    return out


def tabla_estatica(df: pd.DataFrame) -> None:
    st.table(_formatear(df).style.hide(axis="index"))


def tabla_figura(df: pd.DataFrame, clave: str, **_) -> None:
    """Tabla presentada como figura: título numerado, tabla y fuente, dentro de un contenedor capturable.

    Se usa una tabla estática (no la interactiva) para que el texto completo de cada celda sea
    visible en las capturas del artículo.
    """
    with st.container(key=f"figura_{clave}"):
        titulo(clave)
        tabla_estatica(df)
        fuente()


def grafico_figura(fig, clave: str) -> None:
    """Gráfico plotly presentado como figura (el título numerado y la fuente van dentro del gráfico)."""
    with st.container(key=f"figura_{clave}"):
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def aviso_filtros_no_aplican() -> None:
    with st.sidebar:
        st.markdown("**Filtros**")
        st.caption("El diagnóstico describe el conjunto original completo, así que aquí no se aplican filtros. "
                   "Los filtros de años, comuna, conducta y género están en las páginas de análisis y visualización.")
