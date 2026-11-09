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


@st.cache_data(show_spinner="Cargando el conjunto limpio…")
def cargar_limpios() -> tuple[pd.DataFrame, str]:
    """Lee delitos_limpios desde Neon; si no es posible o está vacía, desde data/processed."""
    from src.utils import DATA_PROCESSED

    if _neon_habilitado():
        try:
            from src.utils import get_engine

            with get_engine().connect() as conn:
                df = pd.read_sql_query("SELECT * FROM delitos_limpios ORDER BY orden", conn,
                                       parse_dates=["fecha_hecho"])
            if len(df):
                df["latitud"] = df.latitud.astype(float)
                df["longitud"] = df.longitud.astype(float)
                return df, "Neon (tabla delitos_limpios)"
        except Exception:  # noqa: BLE001
            pass
    ruta = DATA_PROCESSED / "delitos_limpios.parquet"
    if not ruta.exists():
        from src import cleaning

        cleaning.guardar(cleaning.limpiar())
    return pd.read_parquet(ruta), "archivo local data/processed/delitos_limpios.parquet"


@st.cache_data(show_spinner="Cargando los resultados de la limpieza…")
def cargar_limpieza() -> dict:
    from src import cleaning

    r = cleaning.cargar_resultados()
    if r is None:
        cleaning.guardar(cleaning.limpiar())
        r = cleaning.cargar_resultados()
    return r


@st.cache_data(show_spinner="Cargando los registros eliminados…")
def cargar_eliminados() -> pd.DataFrame:
    from src.utils import DATA_PROCESSED

    return pd.read_parquet(DATA_PROCESSED / "delitos_eliminados.parquet")


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


def filtros_sidebar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Filtros de la barra lateral: rango de años, comuna, tipo de delito (grupo y conducta) y género.

    Los valores se guardan en st.session_state para que se mantengan al cambiar de página.
    Devuelve el DataFrame filtrado y una lista legible de los filtros activos.
    """
    from src.eda import ETIQUETA_GRUPO, GRUPOS

    estado = st.session_state.setdefault("filtros", {})
    amin, amax = int(df.anio.min()), int(df.anio.max())
    comunas = sorted(df.comuna.unique(), key=lambda c: (not c[:2].isdigit(), c))
    grupos = [g for g in GRUPOS if g in set(df.grupo_delito)]
    generos = ["MASCULINO", "FEMENINO", "SIN DATO"]

    with st.sidebar:
        st.markdown("**Filtros**")
        anios = st.slider("Rango de años", amin, amax, estado.get("anios", (amin, amax)))
        sel_comunas = st.multiselect("Comuna o corregimiento", comunas, estado.get("comunas", []),
                                     placeholder="Todas")
        sel_grupos = st.multiselect("Tipo de delito (grupo)", grupos, estado.get("grupos", []),
                                    format_func=lambda g: ETIQUETA_GRUPO[g], placeholder="Todos")
        opciones_conducta = sorted(df[df.grupo_delito.isin(sel_grupos or grupos)].conducta.unique())
        sel_conductas = st.multiselect("Conducta", opciones_conducta,
                                       [c for c in estado.get("conductas", []) if c in opciones_conducta],
                                       placeholder="Todas")
        sel_generos = st.multiselect("Género de la víctima", generos, estado.get("generos", []), placeholder="Todos")
        if st.button("Quitar filtros"):
            st.session_state["filtros"] = {}
            st.rerun()
    st.session_state["filtros"] = {"anios": anios, "comunas": sel_comunas, "grupos": sel_grupos,
                                   "conductas": sel_conductas, "generos": sel_generos}

    m = df.anio.between(*anios)
    activos = [] if anios == (amin, amax) else [f"años {anios[0]}–{anios[1]}"]
    if sel_comunas:
        m &= df.comuna.isin(sel_comunas)
        activos.append("comuna: " + ", ".join(sel_comunas))
    if sel_grupos:
        m &= df.grupo_delito.isin(sel_grupos)
        activos.append("grupo: " + ", ".join(ETIQUETA_GRUPO[g] for g in sel_grupos))
    if sel_conductas:
        m &= df.conducta.isin(sel_conductas)
        activos.append("conducta: " + ", ".join(sel_conductas))
    if sel_generos:
        m &= df.genero.isin(sel_generos)
        activos.append("género: " + ", ".join(sel_generos))
    with st.sidebar:
        st.caption(f"{int(m.sum()):,} de {len(df):,} registros".replace(",", "."))
    return df[m], activos


def aviso_filtros_activos(activos: list[str]) -> None:
    if activos:
        st.info("**Filtros activos:** " + " · ".join(activos) + ". Las cifras y figuras reflejan la selección; "
                "las del artículo se calculan con el conjunto completo.")


def aviso_filtros_no_aplican() -> None:
    with st.sidebar:
        st.markdown("**Filtros**")
        st.caption("El diagnóstico describe el conjunto original completo, así que aquí no se aplican filtros. "
                   "Los filtros de años, comuna, conducta y género están en las páginas de análisis y visualización.")
