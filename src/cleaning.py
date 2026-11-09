"""Limpieza y preparación de los datos (objetivo 2).

Produce un dataset NUEVO (delitos_limpios) a partir del original, que no se modifica.
Cada registro excluido queda en delitos_eliminados con su motivo, y cada decisión se
documenta en docs/decisiones_limpieza.md (generado por este mismo script).

Orden de las reglas:
  2.1  normalizar texto -> mes a número y fecha_hecho -> recalcular día de la semana ->
       reconstruir coordenadas -> unificar variantes -> E1 fuera del municipio -> E2 duplicados
  2.2  recodificar los marcadores de faltante a 'SIN DATO' (categóricas); coordenadas
       irrecuperables -> nulas con aviso
  2.3  avisos de atípicos (área, conteos diarios y por barrio) e inconsistencias; validación

Uso:
    python -m src.cleaning
Genera data/processed/delitos_limpios.{parquet,csv}, delitos_eliminados.{parquet,csv},
data/processed/limpieza.pkl (resultados para la app) y docs/decisiones_limpieza.md.
"""
from __future__ import annotations

import pickle
import re
import unicodedata

import numpy as np
import pandas as pd

from src.utils import (
    DATA_PROCESSED,
    DOCS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    TOTAL_REGISTROS,
    corregir_coordenadas,
    fmt_int,
    fmt_pct,
    leer_csv_original,
    tabla_md,
)

RUTA_RESULTADOS = DATA_PROCESSED / "limpieza.pkl"
RUTA_DECISIONES = DOCS / "decisiones_limpieza.md"

SIN_DATO = "SIN DATO"
MARCADORES_FALTANTE = ["NO REPORTA", "NO REPORTADO", "SIN INFORMACION", "ERROR: #N/A"]
MUNICIPIOS_EXTERNOS = ["FLORIDABLANCA", "GIRON", "PIEDECUESTA", "MEDELLIN", "BARRANCABERMEJA"]
DIAS_SEMANA = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]

# Nombre original -> nombre en delitos_limpios (columnas categóricas)
CATEGORICAS = {
    "ARMAS_MEDIOS": "armas_medios",
    "BARRIOS_HECHO": "barrio",
    "ZONA": "zona",
    "NOM_COMUNA": "comuna",
    "DESCRIPCION_CONDUCTA": "descripcion_conducta",
    "CONDUCTA": "conducta",
    "CLASIFICACIONES DELITO": "clasificacion_delito",
    "CURSO_DE_VIDA": "curso_vida",
    "ESTADO_CIVIL_PERSONA": "estado_civil",
    "GENERO": "genero",
    "MOVIL_AGRESOR": "movil_agresor",
    "MOVIL_VICTIMA": "movil_victima",
}

# Variantes de escritura del mismo valor (después de normalizar), detectadas en el diagnóstico.
# Se elige la forma correcta del nombre, no la más frecuente.
UNIFICAR = {
    "barrio": {"QUINTADANIA": "QUINTA DANIA"},
    "descripcion_conducta": {
        "ARTICULO 239. HURTO ABIGEATO": "ARTICULO 239. HURTO A ABIGEATO",
        "LESION ACCIDENTAL EN TRANSITO": "ARTICULO 120. LESIONES CULPOSAS (EN ACCIDENTE DE TRANSITO)",
    },
}

# Columnas que se comparan para decidir si dos registros son duplicados (criterio aprobado E2):
# las 18 columnas del original salvo ORDEN, ya normalizadas. Año, mes, día y día de la semana
# están contenidos en fecha_hecho.
COLUMNAS_DUPLICADO = [
    "armas_medios", "barrio", "latitud", "longitud", "zona", "comuna", "fecha_hecho",
    "descripcion_conducta", "conducta", "clasificacion_delito", "curso_vida", "estado_civil",
    "genero", "movil_agresor", "movil_victima",
]

COLUMNAS_SALIDA = [
    "orden", "fecha_hecho", "anio", "mes", "dia", "dia_semana", "dia_semana_nombre",
    "barrio", "comuna", "tipo_territorio", "zona", "latitud", "longitud",
    "descripcion_conducta", "conducta", "grupo_delito", "clasificacion_delito", "armas_medios",
    "movil_agresor", "movil_victima", "curso_vida", "estado_civil", "genero",
    "flag_coord_faltante", "flag_coord_corregida", "flag_coord_fuera_area", "flag_dia_semana_corregido",
    "flag_barrio_comuna", "flag_curso_vida_estado_civil", "flag_dia_atipico", "flag_barrio_atipico",
]

# Umbrales de atípicos
Z_ROBUSTO = 3.5   # Iglewicz y Hoaglin (1993): |z modificado| > 3,5
K_IQR = 1.5       # Tukey: Q3 + 1,5·IQR


# =============================================================================
# 2.1 Formato
# =============================================================================
def normalizar_texto(valor: str) -> str:
    """Mayúsculas, sin tildes (se conserva la Ñ), sin espacios repetidos ni espacios junto a paréntesis."""
    t = str(valor).strip().upper().replace("Ñ", "\0")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).replace("\0", "Ñ")
    t = re.sub(r"\s+", " ", t)
    return t.replace("( ", "(").replace(" )", ")")


def grupo_delito(conducta: str, clasificacion: str) -> str:
    """Agrupa las 41 conductas en familias para el análisis exploratorio."""
    if conducta == SIN_DATO or conducta in MARCADORES_FALTANTE:
        return SIN_DATO
    if clasificacion == "VIOLENCIA SEXUAL":
        return "DELITOS SEXUALES"
    if conducta.startswith("HURTO"):
        return "HURTO"
    if conducta == "LESIONES CULPOSAS (EN ACCIDENTE DE TRANSITO)":
        return "LESIONES EN ACCIDENTE DE TRANSITO"
    if conducta.startswith("LESIONES PERSONALES") or conducta == "INCAPACIDAD PARA TRABAJAR O ENFERMEDAD":
        return "LESIONES PERSONALES"
    if conducta == "VIOLENCIA INTRAFAMILIAR":
        return "VIOLENCIA INTRAFAMILIAR"
    if conducta in ("HOMICIDIO", "FEMINICIDIO"):
        return "HOMICIDIO"
    if conducta == "HOMICIDIO CULPOSO (EN ACCIDENTE DE TRANSITO)":
        return "HOMICIDIO EN ACCIDENTE DE TRANSITO"
    return "OTROS DELITOS"


def preparar(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica las correcciones de formato a una COPIA del original (actividad 2.1)."""
    c = {}
    df = pd.DataFrame({"orden": raw.ORDEN.astype(int)})

    # Texto
    cambios_texto = 0
    for orig, nuevo in CATEGORICAS.items():
        norm = raw[orig].map(normalizar_texto)
        cambios_texto += int((norm != raw[orig]).sum())
        df[nuevo] = norm
    c["texto_modificado"] = cambios_texto

    # Unificación de variantes
    c["unificados"] = {}
    for col, mapa in UNIFICAR.items():
        for viejo, nuevo in mapa.items():
            n = int((df[col] == viejo).sum())
            c["unificados"][f"{col}: {viejo} → {nuevo}"] = n
            df.loc[df[col] == viejo, col] = nuevo

    # Fecha
    df["anio"] = raw.ANO.astype(int)
    df["mes"] = raw.MES.str.extract(r"^(\d{2})\.")[0].astype(int)
    df["dia"] = raw.DIA.astype(int)
    df["fecha_hecho"] = pd.to_datetime(pd.DataFrame({"year": df.anio, "month": df.mes, "day": df.dia}))
    df["dia_semana"] = df.fecha_hecho.dt.day_of_week + 1          # ISO: 1 = lunes
    df["dia_semana_nombre"] = df.dia_semana.map(lambda d: DIAS_SEMANA[d - 1])
    original = raw.DIA_SEMANA.map(normalizar_texto).str.replace(r"^\d+\. ", "", regex=True)
    df["flag_dia_semana_corregido"] = (original != df.dia_semana_nombre).to_numpy()

    # Coordenadas
    coord = corregir_coordenadas(raw.LATITUD, raw.LONGITUD)
    df["latitud"] = coord.lat.round(7).to_numpy()
    df["longitud"] = coord.lon.round(7).to_numpy()
    df["flag_coord_faltante"] = (coord.estado == "faltante").to_numpy()
    df["flag_coord_corregida"] = coord.estado.isin(["intercambiada", "signo"]).to_numpy()
    df["flag_coord_fuera_area"] = (coord.estado == "fuera_area").to_numpy()
    c["coordenadas"] = coord.estado.value_counts().to_dict()
    return df, c


def eliminar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """E1 (fuera del municipio) y E2 (duplicados exactos). Devuelve (limpios, eliminados, conteos)."""
    eliminados = []

    # E1: hechos asignados a otro municipio
    fuera = df.comuna.isin(MUNICIPIOS_EXTERNOS)
    e1 = df.loc[fuera, ["orden", "comuna"]]
    eliminados.append(pd.DataFrame({
        "orden": e1.orden, "motivo": "FUERA_DEL_MUNICIPIO",
        "detalle": "NOM_COMUNA = " + e1.comuna + " (fuera del alcance: el estudio se limita a Bucaramanga)",
        "orden_conservado": pd.NA,
    }))
    df = df[~fuera]

    # E2: duplicados exactos según el criterio aprobado; se conserva el ORDEN menor de cada grupo
    df = df.sort_values("orden")
    grupo = df.groupby(COLUMNAS_DUPLICADO, dropna=False, sort=False).orden.transform("min")
    dup = df.orden != grupo
    e2 = pd.DataFrame({"orden": df.orden[dup], "conservado": grupo[dup]})
    eliminados.append(pd.DataFrame({
        "orden": e2.orden, "motivo": "DUPLICADO_EXACTO",
        "detalle": "Idéntico en las 18 columnas (salvo ORDEN) al registro ORDEN " + e2.conservado.astype(str),
        "orden_conservado": e2.conservado,
    }))
    limpios = df[~dup].copy()
    elim = pd.concat(eliminados, ignore_index=True)
    elim["orden_conservado"] = elim.orden_conservado.astype("Int64")
    conteos = {"fuera_municipio": int(fuera.sum()), "duplicados": int(dup.sum()),
                "grupos_duplicados": int(df[dup].groupby(grupo[dup]).ngroups)}
    return limpios, elim.sort_values("orden", ignore_index=True), conteos


# =============================================================================
# 2.2 Faltantes
# =============================================================================
def tratar_faltantes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recodifica los marcadores de faltante de cada variable categórica como 'SIN DATO'.

    No se imputa con la moda: en variables como género o estado civil, asignar la categoría más
    frecuente inventaría víctimas y sesgaría los cruces del objetivo 3. 'SIN DATO' conserva el
    registro (el resto de sus columnas es válido) y hace visible la magnitud del faltante.
    """
    filas = []
    for col in CATEGORICAS.values():
        for m in MARCADORES_FALTANTE:
            n = int((df[col] == m).sum())
            if n:
                filas.append({"Variable": col, "Marcador original": m, "Registros": n,
                              "Técnica": "Recodificación a la categoría 'SIN DATO'"})
        df.loc[df[col].isin(MARCADORES_FALTANTE), col] = SIN_DATO
    n_coord = int(df.latitud.isna().sum())
    filas.append({"Variable": "latitud, longitud", "Marcador original": "xx.xxxx / -yy.yyyy y coordenada irrecuperable",
                  "Registros": n_coord, "Técnica": "Valor nulo + aviso (flag_coord_faltante / flag_coord_fuera_area)"})
    return df, pd.DataFrame(filas)


def derivar(df: pd.DataFrame) -> pd.DataFrame:
    df["tipo_territorio"] = np.select(
        [df.comuna.str.match(r"^\d{2}\. "), df.comuna.str.startswith("CORREGIMIENTO")],
        ["COMUNA", "CORREGIMIENTO"], default=SIN_DATO)
    df["grupo_delito"] = [grupo_delito(c, k) for c, k in zip(df.conducta, df.clasificacion_delito)]
    return df


# =============================================================================
# 2.3 Atípicos e inconsistencias
# =============================================================================
def _z_robusto(x: pd.Series) -> pd.Series:
    """z modificado de Iglewicz y Hoaglin: (x - mediana) / (1,4826 · MAD)."""
    med = x.median()
    mad = (x - med).abs().median() * 1.4826
    return (x - med) / mad if mad else pd.Series(0.0, index=x.index)


def _limite_iqr(x: pd.Series) -> float:
    q1, q3 = x.quantile([0.25, 0.75])
    return float(q3 + K_IQR * (q3 - q1))


def atipicos(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    r = {}
    # Conteo diario: todos los días del calendario (los días sin delitos cuentan como 0).
    # Los umbrales se calculan dentro de cada año, porque el nivel general cambia entre años (p. ej. 2020).
    calendario = pd.date_range("2010-01-01", "2021-12-31")
    diario = df.fecha_hecho.value_counts().reindex(calendario, fill_value=0).rename("delitos").to_frame()
    diario["anio"] = diario.index.year
    diario["limite_iqr"] = diario.groupby("anio").delitos.transform(_limite_iqr)
    diario["z_robusto"] = diario.groupby("anio").delitos.transform(_z_robusto)
    diario["atipico_iqr"] = diario.delitos > diario.limite_iqr
    diario["atipico_z"] = diario.z_robusto > Z_ROBUSTO
    diario["atipico"] = diario.atipico_iqr & diario.atipico_z
    dias_atipicos = diario.index[diario.atipico]
    df["flag_dia_atipico"] = df.fecha_hecho.isin(dias_atipicos)
    r["diario"] = diario.rename_axis("fecha").reset_index()

    # Conteo por barrio (todo el periodo). 'SIN DATO' no es un barrio y se excluye.
    barrios = df.loc[df.barrio != SIN_DATO, "barrio"].value_counts().rename("delitos").to_frame()
    barrios["limite_iqr"] = _limite_iqr(barrios.delitos)
    barrios["z_robusto"] = _z_robusto(barrios.delitos)
    barrios["z_robusto_log"] = _z_robusto(np.log10(barrios.delitos))
    barrios["atipico_iqr"] = barrios.delitos > barrios.limite_iqr
    barrios["atipico_z"] = barrios.z_robusto > Z_ROBUSTO
    barrios["atipico"] = barrios.atipico_iqr & barrios.atipico_z
    df["flag_barrio_atipico"] = df.barrio.isin(barrios.index[barrios.atipico])
    r["barrios"] = barrios.rename_axis("barrio").reset_index()

    # Día del mes: el día 1 aparece más de lo esperado (posible fecha por defecto)
    por_dia = df.dia.value_counts().sort_index()
    r["dia_1"] = {"registros": int(por_dia[1]), "media_dias_2_28": float(por_dia.loc[2:28].mean())}

    # Inconsistencias que se marcan sin corregir
    validos = df[df.barrio != SIN_DATO]
    moda = validos.groupby("barrio").comuna.agg(lambda s: s.value_counts().index[0])
    df["flag_barrio_comuna"] = (df.barrio != SIN_DATO) & (df.comuna != df.barrio.map(moda))
    df["flag_curso_vida_estado_civil"] = (
        df.curso_vida.isin(["01. PRIMERA INFANCIA", "02. INFANCIA"])
        & df.estado_civil.isin(["CASADO", "UNION LIBRE", "VIUDO", "DIVORCIADO", "SEPARADO"]))
    return df, r


# =============================================================================
# 2.3 Validación
# =============================================================================
PERMITIDOS = {
    "zona": {"URBANA", "RURAL", "OTROS", SIN_DATO},
    "tipo_territorio": {"COMUNA", "CORREGIMIENTO", SIN_DATO},
    "clasificacion_delito": {"LESIONES NO FATALES", "LESIONES FATALES", "VIOLENCIA SEXUAL", SIN_DATO},
    "curso_vida": {"01. PRIMERA INFANCIA", "02. INFANCIA", "03. ADOLESCENCIA", "04. JOVENES",
                   "05. ADULTEZ", "06. PERSONA MAYOR", SIN_DATO},
    "estado_civil": {"SOLTERO", "CASADO", "UNION LIBRE", "DIVORCIADO", "SEPARADO", "VIUDO", SIN_DATO},
    "genero": {"MASCULINO", "FEMENINO", SIN_DATO},
}


def validar(limpios: pd.DataFrame, elim: pd.DataFrame) -> pd.DataFrame:
    chk = []

    def add(prueba, ok, detalle):
        chk.append({"Prueba": prueba, "Resultado": "OK" if ok else "ERROR", "Detalle": detalle})

    total = len(limpios) + len(elim)
    add("Limpios + eliminados = original", total == TOTAL_REGISTROS,
        f"{fmt_int(len(limpios))} + {fmt_int(len(elim))} = {fmt_int(total)}")
    todos = set(limpios.orden) | set(elim.orden)
    add("Cada ORDEN está en una sola tabla", not (set(limpios.orden) & set(elim.orden)) and len(todos) == TOTAL_REGISTROS,
        "Sin solapamiento y sin registros perdidos")
    add("ORDEN único en delitos_limpios", limpios.orden.is_unique, "Clave primaria válida")
    n_dup = int(limpios.duplicated(subset=COLUMNAS_DUPLICADO).sum())
    add("Sin duplicados según el criterio aprobado", n_dup == 0, f"{n_dup} duplicados")
    add("Sin registros de otros municipios", not limpios.comuna.isin(MUNICIPIOS_EXTERNOS).any(), "")
    restos = {c: int(limpios[c].isin(MARCADORES_FALTANTE).sum()) for c in CATEGORICAS.values()}
    add("Sin marcadores de faltante (todos recodificados)", sum(restos.values()) == 0,
        "Ningún 'NO REPORTA', 'ERROR: #N/A', etc.")
    add("Sin valores nulos fuera de las coordenadas",
        int(limpios.drop(columns=["latitud", "longitud"]).isna().sum().sum()) == 0, "")
    ok_fecha = ((limpios.fecha_hecho.dt.year == limpios.anio) & (limpios.fecha_hecho.dt.month == limpios.mes)
                & (limpios.fecha_hecho.dt.day == limpios.dia)
                & (limpios.fecha_hecho.dt.day_of_week + 1 == limpios.dia_semana)).all()
    add("Fecha coherente con año, mes, día y día de la semana", bool(ok_fecha),
        f"{limpios.fecha_hecho.min().date()} a {limpios.fecha_hecho.max().date()}")
    lat, lon = limpios.latitud.dropna(), limpios.longitud.dropna()
    add("Coordenadas dentro del área de Bucaramanga",
        bool(lat.between(LAT_MIN, LAT_MAX).all() and lon.between(LON_MIN, LON_MAX).all()),
        f"lat {lat.min():.4f}–{lat.max():.4f}; lon {lon.min():.4f}–{lon.max():.4f}")
    add("Latitud y longitud nulas a la vez", bool((limpios.latitud.isna() == limpios.longitud.isna()).all()), "")
    for col, perm in PERMITIDOS.items():
        fuera = set(limpios[col].unique()) - perm
        add(f"Categorías válidas en {col}", not fuera, ", ".join(sorted(fuera)) or "")
    unica = limpios.groupby("conducta").descripcion_conducta.nunique().max() == 1
    add("Cada conducta tiene una sola descripción", bool(unica), "")
    tipos_ok = (limpios.anio.dtype.kind == "i" and limpios.latitud.dtype.kind == "f"
                and limpios.fecha_hecho.dtype.kind == "M"
                and all(limpios[c].dtype == bool for c in limpios.columns if c.startswith("flag_")))
    add("Tipos de dato correctos", bool(tipos_ok), "enteros, decimales, fecha y booleanos")
    return pd.DataFrame(chk)


# =============================================================================
# Ejecución completa
# =============================================================================
def limpiar(raw: pd.DataFrame | None = None) -> dict:
    raw = leer_csv_original() if raw is None else raw
    df, formato = preparar(raw)
    limpios, elim, conteos = eliminar(df)
    limpios, faltantes = tratar_faltantes(limpios)
    limpios = derivar(limpios)
    limpios, atip = atipicos(limpios)
    limpios = limpios[COLUMNAS_SALIDA].sort_values("orden").reset_index(drop=True)
    for c in ["anio", "mes", "dia", "dia_semana"]:
        limpios[c] = limpios[c].astype("int16")
    validacion = validar(limpios, elim)

    r = {
        "formato": formato, "conteos": conteos, "faltantes": faltantes, "atipicos": atip,
        "validacion": validacion, "limpios": limpios, "eliminados": elim,
        "coord_antes": coordenadas_antes(raw),
    }
    r["decisiones"] = decisiones(r)
    r["antes_despues"] = antes_despues(raw, limpios, elim)
    return r


def coordenadas_antes(raw: pd.DataFrame) -> pd.DataFrame:
    """Coordenadas aplicando solo la reconstrucción decimal, sin corregir intercambios ni signos:
    muestra cómo quedarían los datos sin la corrección (para el mapa «antes»)."""
    from src.utils import reconstruir_coordenada

    lat = raw.LATITUD.map(lambda t: reconstruir_coordenada(t, 1)).astype(float)
    lon = raw.LONGITUD.map(lambda t: reconstruir_coordenada(t, 2)).astype(float)
    estado = corregir_coordenadas(raw.LATITUD, raw.LONGITUD).estado
    return pd.DataFrame({"lat": lat, "lon": lon, "estado": estado}).dropna()


def antes_despues(raw, limpios, elim) -> pd.DataFrame:
    filas = [
        ("Registros del conjunto original", TOTAL_REGISTROS),
        ("Eliminados: hecho asignado a otro municipio", int((elim.motivo == "FUERA_DEL_MUNICIPIO").sum())),
        ("Eliminados: duplicado exacto", int((elim.motivo == "DUPLICADO_EXACTO").sum())),
        ("Eliminados: error irrecuperable", int((elim.motivo == "ERROR_IRRECUPERABLE").sum())),
        ("Registros del conjunto limpio", len(limpios)),
    ]
    out = pd.DataFrame(filas, columns=["Concepto", "Registros"])
    out["% del original"] = (100 * out.Registros / TOTAL_REGISTROS).round(2)
    return out


def decisiones(r: dict) -> pd.DataFrame:
    f, k, a, lim = r["formato"], r["conteos"], r["atipicos"], r["limpios"]
    falt = r["faltantes"]
    dias_at = int(a["diario"].atipico.sum())
    barrios_at = int(a["barrios"].atipico.sum())
    filas = [
        # 2.1
        ("D01", "2.1", "Todas las categóricas", "Transformación",
         "Normalizar el texto: mayúsculas, sin tildes (se conserva la Ñ), sin espacios dobles ni espacios junto a paréntesis",
         k_fmt(f["texto_modificado"]) + " celdas",
         "El original mezcla 'GARCÍA'/'GARCIA', 'TRÁNSITO'/'TRANSITO' y espacios dobles; sin normalizar, un mismo valor contaría como categorías distintas."),
        ("D02", "2.1", "barrio, descripcion_conducta", "Recodificación",
         "Unificar variantes del mismo valor: " + "; ".join(f"{t} ({n})" for t, n in f["unificados"].items()),
         k_fmt(sum(f["unificados"].values())),
         "Son la misma categoría escrita de dos formas (diagnóstico 1.2). Se elige la forma correcta del nombre."),
        ("D03", "2.1", "MES, ANO, DIA", "Transformación",
         "Convertir el mes '01. ENERO' a número (1–12) y construir fecha_hecho (DATE)",
         k_fmt(len(lim)),
         "Permite series de tiempo, filtros por rango y comprobar la coherencia de la fecha."),
        ("D04", "2.1", "DIA_SEMANA", "Corrección",
         "Recalcular el día de la semana a partir de la fecha (ISO: 1 = lunes)",
         k_fmt(int(lim.flag_dia_semana_corregido.sum())) + " corregidos",
         "En agosto de 2020 el 84 % de los registros tenía un día de la semana que no corresponde a su fecha. La fecha es la referencia; el día se deriva de ella."),
        ("D05", "2.1", "LATITUD, LONGITUD", "Transformación",
         "Reconstruir el valor decimal: solo dígitos, punto tras el 1.er dígito (latitud) o tras el 2.º (longitud)",
         k_fmt(f["coordenadas"].get("ok", 0) + f["coordenadas"].get("intercambiada", 0) + f["coordenadas"].get("signo", 0)) + " recuperadas",
         "Los separadores de miles están en posiciones arbitrarias; en Bucaramanga la latitud es 7,xx y la longitud −73,xx, así que la posición del punto es conocida."),
        ("D06", "2.1", "LATITUD, LONGITUD", "Corrección",
         "Intercambiar latitud y longitud cuando vienen cruzadas y corregir el signo de la longitud",
         k_fmt(f["coordenadas"].get("intercambiada", 0) + f["coordenadas"].get("signo", 0)) + " (aviso flag_coord_corregida)",
         "Error de carga verificable: el valor de cada columna corresponde al rango de la otra; Bucaramanga está al occidente de Greenwich."),
        ("E1", "2.1", "NOM_COMUNA", "Eliminación",
         "Eliminar los registros asignados a otro municipio (motivo FUERA_DEL_MUNICIPIO)",
         k_fmt(k["fuera_municipio"]),
         "El estudio se limita a Bucaramanga; 115 de 166 traen ZONA = OTROS; no pueden asignarse a ninguna comuna. Aprobada."),
        ("E2", "2.1", "18 columnas (todas salvo ORDEN)", "Eliminación",
         "Eliminar duplicados exactos y conservar el ORDEN menor de cada grupo (motivo DUPLICADO_EXACTO)",
         k_fmt(k["duplicados"]) + f" ({k_fmt(k['grupos_duplicados'])} grupos)",
         "12 veces más duplicados de los esperados por azar, concentrados en 2019–2021 junto con otros errores de carga e idénticos hasta en el perfil de la víctima. Aprobada."),
        # 2.2
        ("D07", "2.2", "12 variables categóricas", "Recodificación",
         "Recodificar 'NO REPORTA', 'NO REPORTADO', 'SIN INFORMACION' y 'ERROR: #N/A' como la categoría 'SIN DATO'",
         k_fmt(int(falt[falt.Variable != "latitud, longitud"].Registros.sum())) + " celdas",
         "Son variables nominales u ordinales: imputar la moda inventaría categorías (p. ej., asignar 'MASCULINO' a 15.105 víctimas) y sesgaría los cruces. 'SIN DATO' conserva el registro y hace visible el faltante."),
        ("D08", "2.2", "CURSO_DE_VIDA", "Recodificación",
         "Recodificar el error de Excel 'ERROR: #N/A' como 'SIN DATO' sin eliminar el registro",
         k_fmt(int(falt[(falt.Variable == "curso_vida") & (falt["Marcador original"] == "ERROR: #N/A")].Registros.sum())),
         "Es un error de fórmula en la fuente, no un dato inválido del hecho: el resto de las columnas del registro es válido."),
        ("D09", "2.2", "latitud, longitud", "Valor nulo + aviso",
         "Dejar nulas las coordenadas inexistentes o irrecuperables y marcarlas (flag_coord_faltante, flag_coord_fuera_area)",
         k_fmt(int(lim.latitud.isna().sum())),
         "Una ubicación no puede imputarse sin inventar el lugar del hecho. Los registros se conservan para los análisis no espaciales y se excluyen solo de los mapas."),
        # 2.3
        ("A1", "2.3", "latitud, longitud", "Atípico (aviso)",
         "Coordenada fuera del área de Bucaramanga (lat 7,0–7,25; lon −73,25 a −73,0): anular y marcar",
         k_fmt(int(lim.flag_coord_fuera_area.sum())),
         "Error imposible de corregir (punto en Bogotá); no se elimina el registro porque el resto es válido."),
        ("A2", "2.3", "Conteo diario", "Atípico (aviso)",
         f"Marcar los días cuyo conteo supera Q3 + {K_IQR}·IQR y tiene z robusto > {Z_ROBUSTO} (ambos dentro de su año): flag_dia_atipico",
         f"{dias_at} días · {k_fmt(int(lim.flag_dia_atipico.sum()))} registros",
         "En datos de conteo un atípico es un día con muchos más delitos de lo normal (fiestas de fin de año, 1 de enero, eventos). Es información real, no un error: se marca para poder analizarlo, no se elimina."),
        ("A3", "2.3", "Conteo por barrio", "Atípico (aviso)",
         f"Marcar los barrios cuyo conteo supera Q3 + {K_IQR}·IQR y tiene z robusto > {Z_ROBUSTO}: flag_barrio_atipico",
         f"{barrios_at} barrios · {k_fmt(int(lim.flag_barrio_atipico.sum()))} registros",
         "La distribución por barrio es muy asimétrica: los atípicos son focos de concentración (CENTRO, SAN FRANCISCO…), no errores. En escala logarítmica ningún barrio es atípico."),
        ("A4", "2.3", "barrio, comuna", "Inconsistencia (aviso)",
         "Marcar los registros cuya comuna no es la habitual de su barrio: flag_barrio_comuna",
         k_fmt(int(lim.flag_barrio_comuna.sum())),
         "No se corrige con la moda porque no se puede saber si el error está en el barrio o en la comuna; el aviso permite excluirlos en análisis espaciales finos."),
        ("A5", "2.3", "curso_vida, estado_civil", "Inconsistencia (aviso)",
         "Marcar primera infancia o infancia con estado civil de adulto: flag_curso_vida_estado_civil",
         k_fmt(int(lim.flag_curso_vida_estado_civil.sum())),
         "Combinación imposible, pero no se sabe cuál de los dos valores es el erróneo; son 3 registros sin efecto en las frecuencias."),
        ("D10", "2.3", "CONDUCTA", "Transformación",
         "Agrupar las 41 conductas en familias (grupo_delito): hurto, lesiones personales, lesiones en tránsito, violencia intrafamiliar, delitos sexuales, homicidio, homicidio en tránsito y otros",
         k_fmt(len(lim)),
         "Facilita comparar tipos de delito con las características de la víctima (objetivo 3) sin perder la conducta original."),
    ]
    return pd.DataFrame(filas, columns=["ID", "Actividad", "Variable", "Tipo", "Decisión", "Registros afectados", "Justificación"])


def k_fmt(n) -> str:
    return fmt_int(n)


# =============================================================================
# Salidas
# =============================================================================
def decisiones_markdown(r: dict) -> str:
    k, a = r["conteos"], r["atipicos"]
    d1 = a["dia_1"]
    top_dias = a["diario"][a["diario"].atipico].sort_values("delitos", ascending=False).head(8)
    top_barrios = a["barrios"][a["barrios"].atipico].head(8)
    return "\n".join([
        "# Decisiones de limpieza",
        "",
        "Registro de cada decisión de limpieza (eliminación, recodificación, transformación, tratamiento de",
        "atípicos) con el número de registros afectados y su justificación. Este archivo lo genera",
        "`python -m src.cleaning` con las cifras de la ejecución; la misma tabla se muestra en la página",
        "*Limpieza* de la aplicación.",
        "",
        "**Principios**",
        "",
        "- **El original no se modifica.** El xlsx, su copia CSV y `delitos_raw` conservan los 135.076 registros.",
        "  Las decisiones se aplican solo al dataset nuevo `delitos_limpios`.",
        "- **Toda eliminación queda registrada** en `delitos_eliminados` (orden, motivo, detalle y, en los",
        "  duplicados, el ORDEN conservado), de modo que `delitos_limpios` + `delitos_eliminados` = 135.076.",
        "- **Un solo motivo por registro.** Primero se aplica el filtro de alcance (E1) y después la",
        "  eliminación de duplicados (E2) sobre los registros restantes.",
        "- **No se imputa con la moda.** Los faltantes de las variables categóricas se recodifican como 'SIN DATO'.",
        "- **Los atípicos y las inconsistencias se marcan con avisos (`flag_…`), no se eliminan.** Solo se anula",
        "  un valor cuando es un error imposible de corregir.",
        "",
        "## Tabla de decisiones",
        "",
        tabla_md(r["decisiones"]),
        "",
        "## Resultado",
        "",
        tabla_md(r["antes_despues"]),
        "",
        "## Notas sobre las decisiones aprobadas",
        "",
        f"**E1 · Registros de otros municipios ({fmt_int(k['fuera_municipio'])}).** El objeto de estudio son los",
        "delitos ocurridos en Bucaramanga, y el conjunto se titula así. Estas filas declaran otro municipio en",
        "`NOM_COMUNA` (Floridablanca 121, Girón 38, Medellín 3, Piedecuesta 3, Barrancabermeja 1). 115 de ellas",
        "traen `ZONA = OTROS`, la única zona que no es urbana ni rural. Las coordenadas no permiten corregirlas,",
        "porque el área de referencia también cubre a Floridablanca y Girón. Los 45 registros con",
        "'SIN INFORMACION' en la comuna no se eliminan: falta el dato, pero no indican otro municipio.",
        "",
        f"**E2 · Duplicados exactos ({fmt_int(k['duplicados'])} en {fmt_int(k['grupos_duplicados'])} grupos).**",
        "El criterio compara las 18 columnas del original salvo `ORDEN`, después de normalizar el texto,",
        "reconstruir las coordenadas y recalcular el día de la semana, y antes de recodificar los faltantes",
        "(dos registros que solo difieren en 'NO REPORTA' frente a 'ERROR: #N/A' no se consideran iguales).",
        "Evidencia (ver `docs/informe_diagnostico.md`):",
        "",
        "- **No son coincidencias:** al permutar al azar el día dentro de cada mes se esperan 360–399",
        "  duplicados; se observan unas 12 veces más.",
        "- **Coinciden con otros errores de carga:** la tasa pasa del 1–3 % anual (2010–2018) al 6,5–8,8 %",
        "  (2019–2021), los años con coordenadas intercambiadas y días de la semana errados.",
        "- **Son idénticos hasta en el perfil de la víctima.**",
        "",
        "*Limitación:* sin hora ni identificador de víctima no puede descartarse que algunos grupos sean",
        "víctimas distintas de un mismo hecho con el mismo perfil, sobre todo en lesiones de tránsito.",
        "",
        "## Qué significa un atípico en datos de conteo de delitos",
        "",
        "Las variables del conjunto son categóricas; las únicas magnitudes son los **conteos** que resultan de",
        "agregar los registros (delitos por día, por barrio). En un conteo, un valor atípico no es un dato",
        "mal digitado sino un **periodo o un lugar con muchos más delitos de lo habitual**. Puede deberse a",
        "un fenómeno real (fiestas, eventos, focos de criminalidad) o a la forma de registro (cargas masivas,",
        "fechas por defecto). Por eso los atípicos se **marcan** para analizarlos y no se eliminan: borrarlos",
        "subestimaría justamente los momentos y lugares de mayor riesgo.",
        "",
        f"- **Métodos:** límite superior de Tukey (Q3 + {K_IQR}·IQR) y z robusto (Iglewicz y Hoaglin, 1993),",
        f"  z = (x − mediana) / (1,4826 · MAD), con umbral {Z_ROBUSTO}. Se marca un valor como atípico solo",
        "  si ambos métodos coinciden. El z robusto usa la mediana y la MAD, que no se distorsionan por los",
        "  mismos valores extremos que se quiere detectar, a diferencia de la media y la desviación estándar.",
        "- **Días:** los umbrales se calculan dentro de cada año, porque el nivel general cambia entre años",
        "  (por ejemplo, la caída de 2020). Días atípicos de mayor conteo:",
        "",
        tabla_md(top_dias[["fecha", "delitos", "limite_iqr", "z_robusto"]].assign(fecha=lambda d: d.fecha.dt.date.astype(str))),
        "",
        "- **Barrios:** la distribución es muy asimétrica (mediana de "
        f"{fmt_int(a['barrios'].delitos.median())} delitos por barrio frente a {fmt_int(a['barrios'].delitos.max())} en CENTRO).",
        "  Los barrios marcados son focos de concentración. En escala logarítmica ningún barrio supera",
        f"  |z| = {Z_ROBUSTO}, lo que confirma que no hay valores imposibles sino una cola larga. Barrios marcados con más delitos:",
        "",
        tabla_md(top_barrios[["barrio", "delitos", "z_robusto", "z_robusto_log"]]),
        "",
        f"- **Día 1 del mes:** tiene {fmt_int(d1['registros'])} registros frente a una media de",
        f"  {fmt_int(round(d1['media_dias_2_28']))} en los días 2 a 28. El exceso puede deberse a fechas",
        "  registradas por defecto cuando se desconocía el día exacto. No hay forma de identificarlas",
        "  registro a registro, así que se documenta como limitación y no se modifica.",
        "",
    ])


def guardar(r: dict) -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    lim, elim = r["limpios"], r["eliminados"]
    lim.to_parquet(DATA_PROCESSED / "delitos_limpios.parquet", index=False)
    lim.to_csv(DATA_PROCESSED / "delitos_limpios.csv", index=False, encoding="utf-8")
    elim.to_parquet(DATA_PROCESSED / "delitos_eliminados.parquet", index=False)
    elim.to_csv(DATA_PROCESSED / "delitos_eliminados.csv", index=False, encoding="utf-8")
    with open(RUTA_RESULTADOS, "wb") as fh:
        pickle.dump({k: v for k, v in r.items() if k not in ("limpios", "eliminados")}, fh)
    RUTA_DECISIONES.write_text(decisiones_markdown(r), encoding="utf-8")


def cargar_resultados() -> dict | None:
    if not RUTA_RESULTADOS.exists():
        return None
    with open(RUTA_RESULTADOS, "rb") as fh:
        return pickle.load(fh)


def main() -> None:
    r = limpiar()
    guardar(r)
    print(r["antes_despues"].to_string(index=False))
    print()
    print(r["validacion"].to_string(index=False))
    if (r["validacion"].Resultado != "OK").any():
        raise SystemExit("La validación encontró errores.")


if __name__ == "__main__":
    main()
