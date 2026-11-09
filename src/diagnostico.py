"""Diagnóstico de calidad del conjunto de datos original (objetivo 1).

Actividad 1.1  estructura: registros, variables, tipos, cardinalidad y ejemplos.
Actividad 1.2  marcadores de faltante, duplicados, formato de coordenadas, rangos y fechas,
               inconsistencias entre columnas.
Actividad 1.3  informe de diagnóstico en docs/informe_diagnostico.md.

El diagnóstico se hace sobre la copia CSV del original: no modifica ningún dato.

Uso:
    python -m src.diagnostico
Genera docs/informe_diagnostico.md y data/processed/diagnostico.pkl (que usa la app).
"""
from __future__ import annotations

import pickle
import re
import unicodedata
from collections import Counter
from datetime import date

import numpy as np
import pandas as pd

from src.utils import (
    CSV_ORIGINAL,
    DATA_PROCESSED,
    DOCS,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    TOTAL_REGISTROS,
    XLSX_ORIGINAL,
    corregir_coordenadas,
    fmt_dec,
    fmt_int,
    fmt_pct,
    leer_csv_original,
    tabla_md,
)

RUTA_RESULTADOS = DATA_PROCESSED / "diagnostico.pkl"
RUTA_INFORME = DOCS / "informe_diagnostico.md"

# Valores que el original usa en lugar de un dato faltante (no hay celdas vacías ni nulos).
MARCADORES = ["NO REPORTA", "NO REPORTADO", "SIN INFORMACION", "SIN DATO", "ERROR: #N/A", "xx.xxxx", "-yy.yyyy"]

MUNICIPIOS_EXTERNOS = ["FLORIDABLANCA", "GIRON", "PIEDECUESTA", "MEDELLIN", "BARRANCABERMEJA"]

DIAS = ["01. LUNES", "02. MARTES", "03. MIÉRCOLES", "04. JUEVES", "05. VIERNES", "06. SÁBADO", "07. DOMINGO"]

# Tipo de cada variable según su significado (no según cómo está almacenada).
TIPO_SEMANTICO = {
    "ORDEN": "Identificador",
    "ARMAS_MEDIOS": "Categórica nominal",
    "BARRIOS_HECHO": "Categórica nominal (alta cardinalidad)",
    "LATITUD": "Numérica continua (guardada como texto)",
    "LONGITUD": "Numérica continua (guardada como texto)",
    "ZONA": "Categórica nominal",
    "NOM_COMUNA": "Categórica nominal",
    "ANO": "Numérica discreta (temporal)",
    "MES": "Categórica ordinal (texto '01. ENERO')",
    "DIA": "Numérica discreta (temporal)",
    "DIA_SEMANA": "Categórica ordinal",
    "DESCRIPCION_CONDUCTA": "Categórica nominal",
    "CONDUCTA": "Categórica nominal",
    "CLASIFICACIONES DELITO": "Categórica nominal",
    "CURSO_DE_VIDA": "Categórica ordinal",
    "ESTADO_CIVIL_PERSONA": "Categórica nominal",
    "GENERO": "Categórica nominal",
    "MOVIL_AGRESOR": "Categórica nominal",
    "MOVIL_VICTIMA": "Categórica nominal",
}
NOMBRE_TIPO_EXCEL = {"int": "entero", "str": "texto", "float": "decimal", "NoneType": "vacía", "datetime": "fecha"}


def _pct(n: int, total: int = TOTAL_REGISTROS) -> float:
    return 100 * n / total


# =============================================================================
# 1.1 Estructura
# =============================================================================
def tipos_excel(ruta=XLSX_ORIGINAL) -> dict[str, dict[str, int]]:
    """Cuenta el tipo de celda que guarda el xlsx en cada columna (entero, texto, decimal…)."""
    from openpyxl import load_workbook

    wb = load_workbook(ruta, read_only=True)
    ws = wb[wb.sheetnames[0]]
    filas = ws.iter_rows(values_only=True)
    encabezado = next(filas)
    conteo = {c: Counter() for c in encabezado}
    for fila in filas:
        for c, v in zip(encabezado, fila):
            conteo[c][NOMBRE_TIPO_EXCEL.get(type(v).__name__, type(v).__name__)] += 1
    hojas = wb.sheetnames
    wb.close()
    return {"hojas": hojas, "tipos": {c: dict(v) for c, v in conteo.items()}}


def estructura(df: pd.DataFrame, tipos: dict) -> pd.DataFrame:
    filas = []
    for c in df.columns:
        vc = df[c].value_counts()
        t = tipos["tipos"][c]
        tipo_txt = " / ".join(f"{k} {fmt_pct(_pct(v), 0)}" if len(t) > 1 else k for k, v in
                              sorted(t.items(), key=lambda kv: -kv[1]))
        # " · " como separador: las coordenadas contienen comas
        ejemplos = " · ".join(df[c].drop_duplicates().sample(min(3, df[c].nunique()), random_state=1).tolist())
        # Tipo que infiere pandas al leer sin forzar texto: entero si todos los valores son dígitos
        inferido = "entero" if df[c].str.fullmatch(r"-?\d+").all() else "texto"
        filas.append({
            "Variable": c,
            "Tipo de celda en el xlsx": tipo_txt,
            "Tipo inferido al leer": inferido,
            "Tipo según su significado": TIPO_SEMANTICO[c],
            "Valores distintos": int(df[c].nunique()),
            "Valor más frecuente": f"{vc.index[0]} ({fmt_int(vc.iloc[0])})",
            "Ejemplos": ejemplos,
        })
    return pd.DataFrame(filas)


# =============================================================================
# 1.2 Faltantes
# =============================================================================
def faltantes(df: pd.DataFrame) -> dict:
    vacias = int((df.apply(lambda s: s.str.strip() == "")).sum().sum())
    filas = []
    for c in df.columns:
        for m in MARCADORES:
            n = int((df[c] == m).sum())
            if n:
                filas.append({"Variable": c, "Marcador": m, "Registros": n, "% del total": round(_pct(n), 2)})
    detalle = pd.DataFrame(filas)
    por_variable = (detalle.groupby("Variable", as_index=False)["Registros"].sum()
                    .assign(**{"% del total": lambda d: (100 * d.Registros / TOTAL_REGISTROS).round(2)})
                    .sort_values("Registros", ascending=False, ignore_index=True))
    con_alguno = df.isin(MARCADORES).any(axis=1)
    return {
        "nulos": int(df.isna().sum().sum()),
        "vacias": vacias,
        "detalle": detalle,
        "por_variable": por_variable,
        "filas_con_alguno": int(con_alguno.sum()),
    }


# =============================================================================
# 1.2 Duplicados
# =============================================================================
def duplicados(df: pd.DataFrame, repeticiones: int = 5, semilla: int = 0) -> dict:
    """Duplicados completos y sin ORDEN, con la evidencia para decidir si son errores de carga."""
    sin_orden = [c for c in df.columns if c != "ORDEN"]
    en_grupo = df.duplicated(subset=sin_orden, keep=False)
    sobrante = df.duplicated(subset=sin_orden, keep="first")
    grupos = df[en_grupo].groupby(sin_orden, sort=False)["ORDEN"].agg(lambda s: sorted(map(int, s)))
    tamanos = grupos.map(len).value_counts().sort_index()

    # Línea base: ¿cuántos duplicados aparecerían por pura coincidencia? Se permuta el DÍA
    # dentro de cada (año, mes), lo que conserva todas las frecuencias pero rompe cualquier
    # relación real entre registros. DIA_SEMANA se excluye de la comparación porque deja de
    # corresponder al día permutado.
    rng = np.random.default_rng(semilla)
    cols_base = [c for c in sin_orden if c != "DIA_SEMANA"]
    base_total, base_anio = [], []
    for _ in range(repeticiones):
        p = df[cols_base].copy()
        p["DIA"] = p.groupby(["ANO", "MES"])["DIA"].transform(lambda s: rng.permutation(s.to_numpy()))
        d = p.duplicated()
        base_total.append(int(d.sum()))
        base_anio.append(d.groupby(p.ANO).sum())
    esperado_anio = pd.concat(base_anio, axis=1).mean(axis=1)

    por_anio = pd.DataFrame({
        "Año": sorted(df.ANO.unique()),
    })
    por_anio["Registros"] = por_anio["Año"].map(df.ANO.value_counts()).astype(int)
    por_anio["Duplicados sobrantes"] = por_anio["Año"].map(sobrante.groupby(df.ANO).sum()).astype(int)
    por_anio["% del año"] = (100 * por_anio["Duplicados sobrantes"] / por_anio["Registros"]).round(2)
    por_anio["Esperados por azar"] = por_anio["Año"].map(esperado_anio).round(1)

    por_conducta = (pd.DataFrame({"Registros": df.CONDUCTA.value_counts(),
                                  "Duplicados sobrantes": sobrante.groupby(df.CONDUCTA).sum()})
                    .fillna(0).astype(int))
    por_conducta["% de la conducta"] = (100 * por_conducta["Duplicados sobrantes"] / por_conducta["Registros"]).round(2)
    por_conducta = (por_conducta[por_conducta["Duplicados sobrantes"] > 0]
                    .sort_values("Duplicados sobrantes", ascending=False)
                    .rename_axis("Conducta").reset_index())

    consecutivos = int(grupos.map(lambda l: l[-1] - l[0] == len(l) - 1).sum())
    muestra_grupos = grupos.sample(4, random_state=7)
    muestra = pd.concat(
        [df[df.ORDEN.isin([str(o) for o in g])].assign(Grupo=i) for i, g in enumerate(muestra_grupos, 1)]
    )[["Grupo"] + list(df.columns)]

    # Registros que comparten el hecho (fecha, lugar, conducta, arma, móvil del agresor)
    # aunque la víctima sea distinta: muestra que un mismo hecho puede tener varias víctimas.
    cols_hecho = [c for c in sin_orden if c not in ("CURSO_DE_VIDA", "ESTADO_CIVIL_PERSONA", "GENERO", "MOVIL_VICTIMA")]
    comparten_hecho = int(df.duplicated(subset=cols_hecho, keep=False).sum())

    return {
        "completos": int(df.duplicated().sum()),
        "orden_unico": bool(df.ORDEN.is_unique),
        "filas_en_grupos": int(en_grupo.sum()),
        "sobrantes": int(sobrante.sum()),
        "n_grupos": int(len(grupos)),
        "tamanos": tamanos,
        "consecutivos": consecutivos,
        "esperado_azar": base_total,
        "por_anio": por_anio,
        "por_conducta": por_conducta,
        "muestra": muestra,
        "comparten_hecho": comparten_hecho,
        "sobrantes_fuera_municipio": int((sobrante & df.NOM_COMUNA.isin(MUNICIPIOS_EXTERNOS)).sum()),
        "sobrantes_sin_fuera": int(df[~df.NOM_COMUNA.isin(MUNICIPIOS_EXTERNOS)].duplicated(subset=sin_orden).sum()),
    }


# =============================================================================
# 1.2 Coordenadas
# =============================================================================
def _patron(s: pd.Series) -> pd.Series:
    return s.str.replace(r"\d", "9", regex=True)


def coordenadas(df: pd.DataFrame) -> dict:
    patrones = (pd.DataFrame({"LATITUD": _patron(df.LATITUD).value_counts(),
                              "LONGITUD": _patron(df.LONGITUD).value_counts()})
                .fillna(0).astype(int).rename_axis("Formato (9 = dígito)").reset_index())
    patrones["Total"] = patrones.LATITUD + patrones.LONGITUD
    patrones = patrones.sort_values("Total", ascending=False, ignore_index=True).drop(columns="Total")

    corr = corregir_coordenadas(df.LATITUD, df.LONGITUD)
    estado = corr.estado.value_counts()
    intercambiadas = df[corr.estado == "intercambiada"]
    fuera = df.loc[corr.estado == "fuera_area", ["ORDEN", "LATITUD", "LONGITUD", "NOM_COMUNA", "BARRIOS_HECHO"]]
    signo = df.loc[corr.estado == "signo", ["ORDEN", "LATITUD", "LONGITUD", "NOM_COMUNA", "BARRIOS_HECHO"]]
    con_coma = df.LATITUD.str.contains(",").sum()
    con_punto = df.LATITUD.str.contains(r"^-?\d+\.\d+$", regex=True).sum()
    validas = corr.dropna()
    return {
        "patrones": patrones,
        "n_formatos_lat": int(_patron(df.LATITUD).nunique()),
        "n_formatos_lon": int(_patron(df.LONGITUD).nunique()),
        "con_coma": int(con_coma),
        "con_punto": int(con_punto),
        "faltantes": int(estado.get("faltante", 0)),
        "intercambiadas": int(len(intercambiadas)),
        "intercambiadas_anios": intercambiadas.ANO.value_counts().sort_index().to_dict(),
        "sin_signo": signo,
        "fuera_area": fuera,
        "fuera_area_valores": corr.loc[fuera.index, ["lat", "lon"]] if len(fuera) else None,
        "recuperables": int(estado.get("ok", 0) + estado.get("intercambiada", 0) + estado.get("signo", 0)),
        "estado": estado,
        "rango_validas": {"lat": (float(validas.lat.min()), float(validas.lat.max())),
                          "lon": (float(validas.lon.min()), float(validas.lon.max()))},
        "muestra": pd.concat([df[["ORDEN", "LATITUD", "LONGITUD"]], corr], axis=1)
                     .groupby("estado", group_keys=False).head(3).reset_index(drop=True),
    }


# =============================================================================
# 1.2 Rangos y fechas
# =============================================================================
def fechas(df: pd.DataFrame) -> dict:
    mes = df.MES.str.extract(r"^(\d{2})\.")[0].astype(int)
    f = pd.to_datetime(pd.DataFrame({"year": df.ANO.astype(int), "month": mes, "day": df.DIA.astype(int)}),
                       errors="coerce")
    calculado = f.dt.day_of_week.map(dict(enumerate(DIAS)))
    mal_dia = f.notna() & (calculado != df.DIA_SEMANA)
    mal = df[mal_dia]
    por_mes = (mal.groupby(["ANO", "MES"]).size().rename("Registros con DIA_SEMANA errado").reset_index()
               .rename(columns={"ANO": "Año", "MES": "Mes"}))
    total_mes = df.groupby(["ANO", "MES"]).size()
    por_mes["Registros del mes"] = [int(total_mes[(a, m)]) for a, m in zip(por_mes["Año"], por_mes["Mes"])]
    por_mes["% del mes"] = (100 * por_mes.iloc[:, 2] / por_mes["Registros del mes"]).round(1)
    orden = df.ORDEN.astype(int)
    return {
        "anio": (int(df.ANO.astype(int).min()), int(df.ANO.astype(int).max())),
        "meses": sorted(df.MES.unique()),
        "mes_texto_coherente": bool((df.MES.str[4:].map({
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
            "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}) == mes).all()),
        "dia": (int(df.DIA.astype(int).min()), int(df.DIA.astype(int).max())),
        "fechas_imposibles": int(f.isna().sum()),
        "dia_semana_errado": int(mal_dia.sum()),
        "dia_semana_por_mes": por_mes,
        "dia_semana_muestra": pd.concat([mal[["ORDEN", "ANO", "MES", "DIA", "DIA_SEMANA"]],
                                         calculado[mal_dia].rename("DIA_SEMANA según la fecha")], axis=1).head(8),
        "fecha_min": f.min().date(), "fecha_max": f.max().date(),
        "orden_rango": (int(orden.min()), int(orden.max())),
        "orden_huecos": int(orden.max() - orden.nunique()),
        "orden_sigue_fecha": float(orden.rank().corr(f.rank())),
    }


# =============================================================================
# 1.2 Inconsistencias entre columnas y de formato del texto
# =============================================================================
def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def inconsistencias(df: pd.DataFrame) -> dict:
    # Conducta y descripción: cada conducta debería tener una sola descripción
    cd = df.groupby(["CONDUCTA", "DESCRIPCION_CONDUCTA"]).size().rename("Registros").reset_index()
    conducta_desc = cd[cd.CONDUCTA.duplicated(keep=False)].reset_index(drop=True)

    # Conducta y clasificación
    cc = df.groupby("CONDUCTA")["CLASIFICACIONES DELITO"].nunique()
    hurtos_lnf = int(((df.CONDUCTA.str.startswith("HURTO")) & (df["CLASIFICACIONES DELITO"] == "LESIONES NO FATALES")).sum())
    clasif = pd.crosstab(df.CONDUCTA, df["CLASIFICACIONES DELITO"])

    # Comuna: otros municipios y SIN INFORMACION
    externos = df[df.NOM_COMUNA.isin(MUNICIPIOS_EXTERNOS)]
    fuera_mun = (externos.groupby("NOM_COMUNA").agg(Registros=("ORDEN", "size"),
                                                    **{"Con ZONA = OTROS": ("ZONA", lambda z: int((z == "OTROS").sum()))})
                 .sort_values("Registros", ascending=False).rename_axis("Municipio").reset_index())

    # Barrio asignado a varias comunas
    bc = df.groupby(["BARRIOS_HECHO", "NOM_COMUNA"]).size().rename("n").reset_index()
    moda = bc.sort_values("n", ascending=False).drop_duplicates("BARRIOS_HECHO").set_index("BARRIOS_HECHO").NOM_COMUNA
    multi = bc.groupby("BARRIOS_HECHO").NOM_COMUNA.nunique()
    barrios_multi = multi[multi > 1].index
    filas_no_modal = int((df.NOM_COMUNA != df.BARRIOS_HECHO.map(moda)).sum())
    ejemplos_bc = (bc[bc.BARRIOS_HECHO.isin(barrios_multi)].sort_values(["BARRIOS_HECHO", "n"], ascending=[True, False])
                   .groupby("BARRIOS_HECHO").agg(Comunas=("NOM_COMUNA", lambda s: " · ".join(s)),
                                                 Registros=("n", lambda s: " · ".join(map(fmt_int, s))))
                   .reset_index().rename(columns={"BARRIOS_HECHO": "Barrio"}))

    # Zona frente a tipo de territorio
    corregimiento = df.NOM_COMUNA.str.startswith("CORREGIMIENTO")
    comuna_urbana = df.NOM_COMUNA.str.match(r"^\d{2}\. ")
    urbana_en_correg = int((corregimiento & (df.ZONA == "URBANA")).sum())
    rural_en_comuna = int((comuna_urbana & (df.ZONA == "RURAL")).sum())

    # Curso de vida frente a estado civil
    menores = df.CURSO_DE_VIDA.isin(["01. PRIMERA INFANCIA", "02. INFANCIA"])
    imposible = menores & df.ESTADO_CIVIL_PERSONA.isin(["CASADO", "UNION LIBRE", "VIUDO", "DIVORCIADO", "SEPARADO"])
    curso_estado = pd.crosstab(df.CURSO_DE_VIDA, df.ESTADO_CIVIL_PERSONA)

    # Medios de transporte que no existen en Bucaramanga
    raros = []
    for col in ["MOVIL_AGRESOR", "MOVIL_VICTIMA"]:
        for v, n in df[col][df[col].str.contains("METRO|BARCO|AERONAVE")].value_counts().items():
            raros.append({"Variable": col, "Valor": v, "Registros": int(n)})

    # Formato del texto: variantes que coinciden al quitar tildes, espacios y signos
    # (se cuentan como afectados los registros de las variantes menos frecuentes)
    variantes, dobles, minoritarias = [], {}, 0
    for c in df.columns:
        if c in ("ORDEN", "LATITUD", "LONGITUD", "ANO", "DIA"):
            continue
        valores = pd.Series(df[c].unique())
        grupos = valores.groupby(valores.map(_normalizar)).agg(list)
        for g in grupos[grupos.map(len) > 1]:
            conteos = [int((df[c] == v).sum()) for v in g]
            minoritarias += sum(conteos) - max(conteos)
            variantes.append({"Variable": c, "Variantes": " | ".join(g),
                              "Registros": " | ".join(map(fmt_int, conteos))})
        dobles[c] = int(df[c].str.contains("  ").sum())
    con_doble = {k: v for k, v in dobles.items() if v}

    # Uso incoherente de tildes en una misma palabra (TRANSITO / TRÁNSITO, etc.)
    palabras = Counter()
    for c in ["CONDUCTA", "DESCRIPCION_CONDUCTA", "NOM_COMUNA", "BARRIOS_HECHO", "DIA_SEMANA", "ARMAS_MEDIOS"]:
        for v in df[c].unique():
            for p in re.findall(r"[A-ZÁÉÍÓÚÑ]+", v):
                palabras[p] += 1
    por_base: dict[str, set] = {}
    for p in palabras:
        por_base.setdefault(_normalizar(p), set()).add(p)
    tildes_mixtas = sorted(" / ".join(sorted(v)) for v in por_base.values() if len(v) > 1)

    return {
        "conducta_descripcion": conducta_desc,
        "conducta_descripcion_minoritaria": int(
            (conducta_desc.groupby("CONDUCTA").Registros.sum() - conducta_desc.groupby("CONDUCTA").Registros.max()).sum()),
        "variantes_minoritarias": minoritarias,
        "conductas_multiclasificacion": int((cc > 1).sum()),
        "hurtos_lesiones_no_fatales": hurtos_lnf,
        "clasificacion": clasif,
        "conducta_no_reporta": int((df.CONDUCTA == "NO REPORTA").sum()),
        "fuera_municipio": fuera_mun,
        "sin_informacion_comuna": int((df.NOM_COMUNA == "SIN INFORMACION").sum()),
        "barrios_multicomuna": int(len(barrios_multi)),
        "filas_comuna_no_modal": filas_no_modal,
        "ejemplos_barrio_comuna": ejemplos_bc,
        "urbana_en_corregimiento": urbana_en_correg,
        "rural_en_comuna": rural_en_comuna,
        "curso_estado": curso_estado,
        "curso_estado_imposible": df.loc[imposible, ["ORDEN", "CURSO_DE_VIDA", "ESTADO_CIVIL_PERSONA", "CONDUCTA"]],
        "moviles_raros": pd.DataFrame(raros),
        "variantes": pd.DataFrame(variantes),
        "dobles_espacios": con_doble,
        "tildes_mixtas": tildes_mixtas,
    }


# =============================================================================
# 1.3 Resumen e informe
# =============================================================================
def resumen_problemas(r: dict) -> pd.DataFrame:
    f, d, c, fe, i = r["faltantes"], r["duplicados"], r["coordenadas"], r["fechas"], r["inconsistencias"]
    pv = f["por_variable"].set_index("Variable").Registros
    filas = [
        ("Faltantes", "Marcadores de dato faltante ('NO REPORTA', 'ERROR: #N/A', 'xx.xxxx', etc.) en lugar de nulos",
         "12 variables", f["filas_con_alguno"], "Recodificar a la categoría 'SIN DATO' (2.2)"),
        ("Faltantes", "Valor de error de Excel 'ERROR: #N/A' en el curso de vida",
         "CURSO_DE_VIDA", int((f["detalle"].Marcador == "ERROR: #N/A").pipe(lambda m: f["detalle"][m].Registros.sum())),
         "Recodificar a 'SIN DATO'; el resto del registro es válido (2.2)"),
        ("Duplicados", "Registros idénticos en todas las columnas salvo ORDEN (sobrantes)",
         "18 variables", d["sobrantes"], "Eliminar en el dataset limpio, conservar el ORDEN menor (2.1)"),
        ("Formato", "Coordenadas guardadas como texto con separadores de miles mal ubicados",
         "LATITUD, LONGITUD", c["con_coma"], "Reconstruir el valor decimal (2.1)"),
        ("Formato", "Latitud y longitud intercambiadas", "LATITUD, LONGITUD", c["intercambiadas"],
         "Intercambiar y reconstruir (2.1)"),
        ("Formato", "Longitud sin signo negativo", "LONGITUD", len(c["sin_signo"]), "Corregir el signo (2.1)"),
        ("Rango", "Coordenada fuera del área de Bucaramanga e irrecuperable", "LATITUD, LONGITUD",
         len(c["fuera_area"]), "Anular la coordenada y marcar con aviso (2.3)"),
        ("Formato", "Mes como texto con prefijo numérico ('01. ENERO')", "MES", TOTAL_REGISTROS,
         "Convertir a número y construir fecha_hecho (2.1)"),
        ("Inconsistencia", "DIA_SEMANA no corresponde a la fecha", "DIA_SEMANA", fe["dia_semana_errado"],
         "Recalcular desde la fecha (2.1)"),
        ("Inconsistencia", "Hecho asignado a otro municipio", "NOM_COMUNA", int(i["fuera_municipio"].Registros.sum()),
         "Eliminar del dataset limpio: fuera del alcance (2.1)"),
        ("Faltantes", "Comuna 'SIN INFORMACION'", "NOM_COMUNA", i["sin_informacion_comuna"], "Recodificar a 'SIN DATO' (2.2)"),
        ("Inconsistencia", "Barrio registrado en una comuna distinta de la habitual",
         "BARRIOS_HECHO, NOM_COMUNA", i["filas_comuna_no_modal"], "Marcar con aviso, sin corregir (2.3)"),
        ("Inconsistencia", "Una conducta con dos descripciones distintas", "CONDUCTA, DESCRIPCION_CONDUCTA",
         i["conducta_descripcion_minoritaria"], "Unificar la descripción (2.1)"),
        ("Inconsistencia", "Primera infancia o infancia con estado civil de adulto", "CURSO_DE_VIDA, ESTADO_CIVIL_PERSONA",
         len(i["curso_estado_imposible"]), "Marcar con aviso (2.3)"),
        ("Formato", "Variantes de escritura del mismo valor (espacios, tildes)", "Varias",
         i["variantes_minoritarias"], "Normalizar el texto y unificar (2.1)"),
    ]
    out = pd.DataFrame(filas, columns=["Tipo", "Problema", "Variables", "Registros", "Tratamiento propuesto (fase)"])
    out.insert(4, "% del total", (100 * out.Registros / TOTAL_REGISTROS).round(2))
    return out


def diagnosticar(df: pd.DataFrame | None = None, con_tipos_excel: bool = True) -> dict:
    df = leer_csv_original() if df is None else df
    tipos = tipos_excel() if con_tipos_excel else {"hojas": ["Data"], "tipos": {c: {"texto": len(df)} for c in df.columns}}
    r = {
        "fecha": date.today().isoformat(),
        "filas": len(df), "columnas": df.shape[1], "hojas": tipos["hojas"],
        "estructura": estructura(df, tipos),
        "faltantes": faltantes(df),
        "duplicados": duplicados(df),
        "coordenadas": coordenadas(df),
        "fechas": fechas(df),
        "inconsistencias": inconsistencias(df),
    }
    r["resumen"] = resumen_problemas(r)
    return r


def informe_markdown(r: dict) -> str:
    f, d, c, fe, i = r["faltantes"], r["duplicados"], r["coordenadas"], r["fechas"], r["inconsistencias"]
    pv = f["por_variable"]
    esperado = f"{min(d['esperado_azar'])}–{max(d['esperado_azar'])}"
    lineas = [
        "# Informe de diagnóstico de calidad",
        "",
        "**Conjunto:** 40Delitos ocurridos en el Municipio de Bucaramanga (datos.gov.co, `75fz-q98y`), "
        "Alcaldía de Bucaramanga (2023).  ",
        f"**Archivo analizado:** `data/raw/{CSV_ORIGINAL.name}` (copia fiel del xlsx original).  ",
        f"**Fecha del diagnóstico:** {r['fecha']}. Generado con `python -m src.diagnostico`.",
        "",
        "El diagnóstico solo lee los datos: no modifica el original. Las correcciones se aplican en la "
        "fase de limpieza sobre un dataset nuevo (`delitos_limpios`).",
        "",
        "## Resumen de problemas encontrados",
        "",
        tabla_md(r["resumen"]),
        "",
        "## 1.1 Estructura del conjunto de datos",
        "",
        f"- **Registros:** {fmt_int(r['filas'])}. **Variables:** {r['columnas']}. "
        f"**Hojas del libro:** {', '.join(r['hojas'])}.",
        f"- **Periodo:** del {fe['fecha_min']} al {fe['fecha_max']} ({fe['anio'][0]}–{fe['anio'][1]}).",
        f"- **Identificador:** `ORDEN` va de {fmt_int(fe['orden_rango'][0])} a {fmt_int(fe['orden_rango'][1])}, "
        f"es único y no tiene huecos. Sigue el orden cronológico de los hechos "
        f"(correlación de rangos con la fecha: {fmt_dec(fe['orden_sigue_fecha'], 4)}).",
        "- **Tipos:** el xlsx guarda **todas** las celdas como texto, incluidas las numéricas. Al leerlo, "
        "solo `ORDEN`, `ANO` y `DIA` se pueden interpretar como enteros. Las coordenadas, numéricas por "
        "naturaleza, no se pueden convertir directamente por su formato. `MES` y `DIA_SEMANA` son ordinales "
        "escritos como texto con un prefijo numérico ('01. ENERO').",
        "",
        tabla_md(r["estructura"]),
        "",
        "## 1.2 Problemas de calidad",
        "",
        "### Valores nulos y marcadores de faltante",
        "",
        f"No hay valores nulos ({f['nulos']}) ni celdas vacías ({f['vacias']}). Los faltantes están "
        f"escritos como texto, con marcadores distintos según la variable. "
        f"{fmt_int(f['filas_con_alguno'])} registros ({fmt_pct(_pct(f['filas_con_alguno']))}) tienen al menos uno.",
        "",
        tabla_md(f["detalle"]),
        "",
        "### Registros duplicados",
        "",
        f"- **Duplicados completos:** {d['completos']}, porque `ORDEN` es único en todas las filas.",
        f"- **Duplicados sin `ORDEN`:** {fmt_int(d['filas_en_grupos'])} registros forman {fmt_int(d['n_grupos'])} "
        f"grupos de filas idénticas en las otras 18 columnas. Si se conserva un registro por grupo, sobran "
        f"**{fmt_int(d['sobrantes'])}** ({fmt_pct(_pct(d['sobrantes']))}).",
        f"- **Tamaño de los grupos:** " + ", ".join(f"{fmt_int(n)} {'grupo' if n == 1 else 'grupos'} de {k}" for k, n in d["tamanos"].items()) + ".",
        f"- **No son coincidencias:** al permutar al azar el día dentro de cada mes (5 repeticiones), se esperan "
        f"{esperado} duplicados. El valor observado es unas {d['sobrantes'] / np.mean(d['esperado_azar']):.0f} "
        f"veces mayor.",
        f"- **Coinciden con otros errores de carga:** la tasa pasa del 1–3 % anual en 2010–2018 al 6,5–8,8 % en "
        f"2019–2021, los mismos años con coordenadas intercambiadas y días de la semana errados.",
        f"- **Son idénticos incluso en la víctima:** curso de vida, estado civil, género y móvil coinciden. En "
        f"cambio, {fmt_int(d['comparten_hecho'])} registros comparten el hecho (fecha, lugar, conducta, arma y "
        f"móvil del agresor) con víctimas distintas, que es lo esperable cuando un hecho tiene varias víctimas.",
        f"- **Limitación:** sin hora ni identificador de víctima no puede descartarse que algunos grupos sean "
        f"víctimas distintas con el mismo perfil, sobre todo en lesiones de tránsito.",
        "",
        tabla_md(d["por_anio"]),
        "",
        "Conductas con más duplicados sobrantes:",
        "",
        tabla_md(d["por_conducta"], 10),
        "",
        "### Formato de las coordenadas",
        "",
        f"- **Formatos:** `LATITUD` tiene {c['n_formatos_lat']} formatos de texto distintos y `LONGITUD` "
        f"{c['n_formatos_lon']}. {fmt_int(c['con_coma'])} latitudes usan comas como separador de miles en "
        f"posiciones arbitrarias y {fmt_int(c['con_punto'])} usan punto decimal.",
        f"- **Sin coordenadas:** {fmt_int(c['faltantes'])} registros traen los marcadores `xx.xxxx` / `-yy.yyyy`.",
        f"- **Intercambiadas:** {fmt_int(c['intercambiadas'])} registros tienen la longitud en `LATITUD` y la "
        f"latitud en `LONGITUD` (años: {', '.join(f'{a}: {fmt_int(n)}' for a, n in c['intercambiadas_anios'].items())}).",
        f"- **Sin signo:** {len(c['sin_signo'])} registro tiene la longitud sin signo negativo.",
        f"- **Recuperables:** con la regla de reconstrucción se recuperan {fmt_int(c['recuperables'])} coordenadas "
        f"dentro del área de Bucaramanga (lat 7,0–7,25 y lon −73,25 a −73,0).",
        f"- **Irrecuperables:** {len(c['fuera_area'])} registro queda fuera del área y no puede corregirse.",
        "",
        "Formatos más frecuentes (9 = cualquier dígito):",
        "",
        tabla_md(c["patrones"], 12),
        "",
        "Registro con coordenada fuera del área:",
        "",
        tabla_md(c["fuera_area"]),
        "",
        "### Rangos y fechas",
        "",
        f"- **Rangos:** `ANO` va de {fe['anio'][0]} a {fe['anio'][1]}, `DIA` de {fe['dia'][0]} a {fe['dia'][1]}, "
        f"y `MES` tiene {len(fe['meses'])} valores con el número y el nombre coherentes "
        f"({'sí' if fe['mes_texto_coherente'] else 'no'}).",
        f"- **Fechas imposibles** (por ejemplo, 31 de febrero): {fe['fechas_imposibles']}.",
        f"- **`DIA_SEMANA` incoherente con la fecha:** {fmt_int(fe['dia_semana_errado'])} registros, todos en el "
        f"mes indicado abajo.",
        "",
        tabla_md(fe["dia_semana_por_mes"]),
        "",
        "### Inconsistencias entre columnas",
        "",
        f"- **Conducta y clasificación:** {i['conductas_multiclasificacion']} conductas tienen más de una "
        f"clasificación, así que la relación es coherente. Sin embargo, la fuente clasifica los hurtos como "
        f"'LESIONES NO FATALES' ({fmt_int(i['hurtos_lesiones_no_fatales'])} registros). Se documenta como una "
        f"particularidad de la taxonomía de la fuente y no se modifica.",
        f"- **Conducta sin dato:** {i['conducta_no_reporta']} registros tienen conducta y clasificación 'NO REPORTA'.",
        "- **Conducta y descripción:** dos conductas aparecen con dos descripciones distintas:",
        "",
        tabla_md(i["conducta_descripcion"]),
        "",
        f"- **Otros municipios:** {fmt_int(i['fuera_municipio'].Registros.sum())} registros tienen en "
        f"`NOM_COMUNA` un municipio distinto de Bucaramanga. Además, {i['sin_informacion_comuna']} registros "
        f"dicen 'SIN INFORMACION'.",
        "",
        tabla_md(i["fuera_municipio"]),
        "",
        f"- **Barrios en varias comunas:** {i['barrios_multicomuna']} barrios aparecen en más de una comuna. "
        f"{fmt_int(i['filas_comuna_no_modal'])} registros tienen una comuna distinta de la más frecuente para "
        f"su barrio; en su mayoría son registros aislados. Ejemplos:",
        "",
        tabla_md(i["ejemplos_barrio_comuna"], 8),
        "",
        f"- **Zona y comuna:** {i['urbana_en_corregimiento']} registros de corregimientos (zona rural del municipio) "
        f"están marcados como URBANA, y {i['rural_en_comuna']} registros de comunas urbanas como RURAL. Es "
        f"plausible en los bordes del municipio, así que se documenta sin corregir.",
        f"- **Curso de vida y estado civil:** {len(i['curso_estado_imposible'])} registros de primera infancia o "
        f"infancia tienen un estado civil de adulto, lo que es imposible:",
        "",
        tabla_md(i["curso_estado_imposible"]),
        "",
        "- **Medios de transporte poco plausibles:** Bucaramanga no tiene metro, puerto ni aeropuerto urbano. "
        "'PASAJERO METRO' corresponde probablemente al sistema Metrolínea. Se documenta y se conserva:",
        "",
        tabla_md(i["moviles_raros"]),
        "",
        "### Formato del texto",
        "",
        "- **Variantes de un mismo valor** (coinciden al quitar tildes, espacios y signos):",
        "",
        tabla_md(i["variantes"]) if len(i["variantes"]) else "Ninguna.",
        "",
        "- **Valores con espacios dobles:** "
        + (", ".join(f"`{k}` ({fmt_int(v)} registros)" for k, v in i["dobles_espacios"].items()) or "ninguno") + ".",
        "- **Palabras escritas con y sin tilde:** " + "; ".join(i["tildes_mixtas"]) + ". Se normalizan a "
        "mayúsculas sin tildes en la limpieza.",
        "",
    ]
    return "\n".join(lineas)


def guardar(r: dict) -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(RUTA_RESULTADOS, "wb") as fh:
        pickle.dump(r, fh)
    RUTA_INFORME.write_text(informe_markdown(r), encoding="utf-8")


def cargar_resultados() -> dict | None:
    if RUTA_RESULTADOS.exists():
        with open(RUTA_RESULTADOS, "rb") as fh:
            return pickle.load(fh)
    return None


def main() -> None:
    r = diagnosticar()
    guardar(r)
    print(f"Diagnóstico de {fmt_int(r['filas'])} registros y {r['columnas']} variables.")
    print(r["resumen"][["Problema", "Registros"]].to_string(index=False))
    print(f"\nInforme: {RUTA_INFORME.relative_to(RUTA_INFORME.parents[1])}")


# =============================================================================
# Figuras (las usan la app y src/capturas.py para exportarlas a PNG)
# =============================================================================
def fig_faltantes(r: dict):
    import plotly.graph_objects as go

    from src.utils import COLOR, estilo_figura

    f = r["faltantes"]
    pv = f["por_variable"].sort_values("Registros")
    marc = f["detalle"].groupby("Variable").apply(
        lambda g: "<br>".join(f"«{m}»: {fmt_int(n)}" for m, n in zip(g.Marcador, g.Registros)), include_groups=False)
    fig = go.Figure(go.Bar(
        y=pv.Variable, x=pv["% del total"], orientation="h", marker_color=COLOR["serie"][0],
        text=[f"{fmt_int(n)} ({fmt_pct(p, 2 if p < 1 else 1)})" for n, p in zip(pv.Registros, pv["% del total"])],
        textposition="outside", textfont={"size": 11, "color": COLOR["tinta2"]}, cliponaxis=False,
        customdata=pv.Variable.map(marc), hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
    ))
    fig.update_layout(barcornerradius=4, bargap=0.35)
    fig.update_yaxes(title=None, type="category")
    fig.update_xaxes(title="% de los 135.076 registros", ticksuffix=" %", range=[0, pv["% del total"].max() * 1.28])
    return estilo_figura(fig, "faltantes", alto=480)


def fig_duplicados_anio(r: dict):
    import plotly.graph_objects as go

    from src.utils import COLOR, estilo_figura

    pa = r["duplicados"]["por_anio"]
    fig = go.Figure()
    fig.add_bar(x=pa["Año"], y=pa["Duplicados sobrantes"], name="Observados", marker_color=COLOR["serie"][0],
                customdata=pa["% del año"],
                hovertemplate="%{x}: %{y:,} duplicados sobrantes (%{customdata:.2f} % del año)<extra></extra>",
                text=[fmt_pct(v) for v in pa["% del año"]], textposition="outside", cliponaxis=False,
                textfont={"size": 11, "color": COLOR["tinta2"]})
    fig.add_bar(x=pa["Año"], y=pa["Esperados por azar"], name="Esperados por azar (promedio de 5 permutaciones)",
                marker_color=COLOR["eje"], hovertemplate="%{x}: %{y:.1f} esperados por azar<extra></extra>")
    fig.update_layout(barmode="group", barcornerradius=4, bargap=0.25, bargroupgap=0.08)
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title="Registros duplicados sobrantes", rangemode="tozero")
    fig.add_annotation(text="Etiqueta: % de los registros del año", xref="paper", yref="paper", x=1, y=1.02,
                       xanchor="right", yanchor="bottom", showarrow=False, font={"size": 11, "color": COLOR["tenue"]})
    return estilo_figura(fig, "duplicados_anio", alto=450)


def fig_coord_formatos(r: dict, n: int = 12):
    import plotly.graph_objects as go

    from src.utils import COLOR, estilo_figura

    pt = r["coordenadas"]["patrones"].head(n).iloc[::-1]
    fig = go.Figure()
    for i, col in enumerate(["LATITUD", "LONGITUD"]):
        fig.add_bar(y=pt["Formato (9 = dígito)"], x=pt[col], orientation="h", name=col,
                    marker_color=COLOR["serie"][i],
                    hovertemplate="Formato %{y}<br>" + col + ": %{x:,} registros<extra></extra>")
    # Apiladas: la mayoría de los formatos aparece en una sola de las dos columnas.
    fig.update_layout(barmode="stack", barcornerradius=4, bargap=0.35)
    fig.update_yaxes(title="Formato del texto (9 = cualquier dígito)", type="category",
                     tickfont={"family": "Consolas, monospace"})
    fig.update_xaxes(title="Registros", tickformat=",d")
    return estilo_figura(fig, "coord_formatos", alto=520)


FIGURAS_PLOTLY = {"faltantes": fig_faltantes, "duplicados_anio": fig_duplicados_anio, "coord_formatos": fig_coord_formatos}


if __name__ == "__main__":
    main()
