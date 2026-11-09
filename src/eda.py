"""Análisis exploratorio del conjunto limpio (objetivo 3).

3.1  estadísticas descriptivas y frecuencias de cada variable; distribución de los conteos
3.2  distribución temporal (año, mes, día de la semana, cambio en 2020) y espacial (comuna, barrio,
     concentración de los hurtos)
3.3  tablas de contingencia entre el tipo de delito y la víctima (chi-cuadrado y V de Cramér),
     correlación de Spearman y dispersión sobre conteos agregados por barrio y año

Todas las funciones reciben el DataFrame de delitos_limpios (completo o filtrado en la app).
Uso:  python -m src.eda   (imprime un resumen de los resultados con los datos completos)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils import COLOR, SECUENCIAL, estilo_figura, fmt_int, fmt_pct

SIN_DATO = "SIN DATO"

# Orden fijo de los grupos de delito: el color sigue a la entidad, no a su posición en un filtro.
GRUPOS = [
    "HURTO", "LESIONES PERSONALES", "LESIONES EN ACCIDENTE DE TRANSITO", "VIOLENCIA INTRAFAMILIAR",
    "DELITOS SEXUALES", "HOMICIDIO", "HOMICIDIO EN ACCIDENTE DE TRANSITO", "OTROS DELITOS", SIN_DATO,
]
ETIQUETA_GRUPO = {
    "HURTO": "Hurto", "LESIONES PERSONALES": "Lesiones personales",
    "LESIONES EN ACCIDENTE DE TRANSITO": "Lesiones en tránsito", "VIOLENCIA INTRAFAMILIAR": "Violencia intrafamiliar",
    "DELITOS SEXUALES": "Delitos sexuales", "HOMICIDIO": "Homicidio",
    "HOMICIDIO EN ACCIDENTE DE TRANSITO": "Homicidio en tránsito", "OTROS DELITOS": "Otros delitos", SIN_DATO: "Sin dato",
}
COLOR_GRUPO = {g: (COLOR["serie"][i] if i < 8 else COLOR["eje"]) for i, g in enumerate(GRUPOS)}
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
CURSO_VIDA = ["01. PRIMERA INFANCIA", "02. INFANCIA", "03. ADOLESCENCIA", "04. JOVENES", "05. ADULTEZ", "06. PERSONA MAYOR"]

VARIABLES_FRECUENCIA = {
    "grupo_delito": "Grupo de delito", "conducta": "Conducta", "clasificacion_delito": "Clasificación",
    "armas_medios": "Arma o medio", "genero": "Género", "curso_vida": "Curso de vida",
    "estado_civil": "Estado civil", "movil_agresor": "Móvil del agresor", "movil_victima": "Móvil de la víctima",
    "zona": "Zona", "tipo_territorio": "Tipo de territorio", "comuna": "Comuna", "barrio": "Barrio",
    "dia_semana_nombre": "Día de la semana",
}


# =============================================================================
# 3.1 Descriptivas y frecuencias
# =============================================================================
def frecuencias(df: pd.DataFrame, col: str) -> pd.DataFrame:
    vc = df[col].value_counts()
    out = vc.rename_axis("Categoría").reset_index(name="Registros")
    out["%"] = (100 * out.Registros / out.Registros.sum()).round(2)
    out["% acumulado"] = out["%"].cumsum().round(2)
    return out


def resumen_frecuencias(df: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Tabla compacta con las categorías principales de las variables de delito y víctima."""
    filas = []
    for col in ["grupo_delito", "armas_medios", "genero", "curso_vida", "estado_civil", "movil_victima", "zona"]:
        f = frecuencias(df, col)
        principales = f.head(top)
        for _, r in principales.iterrows():
            filas.append({"Variable": VARIABLES_FRECUENCIA[col], "Categoría": r.Categoría,
                          "Registros": int(r.Registros), "%": r["%"]})
        if len(f) > top:
            resto = f.iloc[top:]
            filas.append({"Variable": VARIABLES_FRECUENCIA[col], "Categoría": f"Otras ({len(resto)} categorías)",
                          "Registros": int(resto.Registros.sum()), "%": round(resto["%"].sum(), 2)})
    return pd.DataFrame(filas)


def conteos(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Series de conteo: por día (calendario completo, con ceros), mes, barrio y comuna."""
    inicio, fin = df.fecha_hecho.min(), df.fecha_hecho.max()
    calendario = pd.date_range(f"{inicio.year}-01-01", f"{fin.year}-12-31")
    return {
        "Por día": df.fecha_hecho.value_counts().reindex(calendario, fill_value=0),
        "Por mes": df.groupby(["anio", "mes"]).size(),
        "Por barrio": df.loc[df.barrio != SIN_DATO, "barrio"].value_counts(),
        "Por comuna": df.loc[df.tipo_territorio == "COMUNA", "comuna"].value_counts(),
    }


def descriptivas_conteos(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for nombre, s in conteos(df).items():
        filas.append({
            "Conteo de delitos": nombre, "Unidades": len(s), "Media": s.mean(), "Desv. estándar": s.std(),
            "Mínimo": int(s.min()), "Q1": s.quantile(0.25), "Mediana": s.median(), "Q3": s.quantile(0.75),
            "Máximo": int(s.max()), "Asimetría": s.skew(), "Curtosis": s.kurt(),
            "Coef. de variación (%)": 100 * s.std() / s.mean(),
        })
    return pd.DataFrame(filas).round(2)


# =============================================================================
# 3.2 Tiempo
# =============================================================================
def serie_anual(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="anio", columns="grupo_delito", values="orden", aggfunc="size", fill_value=0)


def serie_mensual(df: pd.DataFrame) -> pd.DataFrame:
    s = df.groupby(df.fecha_hecho.dt.to_period("M")).size()
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"), fill_value=0)
    out = pd.DataFrame({"mes": s.index.to_timestamp(), "delitos": s.to_numpy()})
    out["media_movil_12"] = out.delitos.rolling(12, center=True).mean()
    return out


def por_dia_semana(df: pd.DataFrame) -> pd.DataFrame:
    n = df.dia_semana.value_counts().reindex(range(1, 8), fill_value=0)
    out = pd.DataFrame({"Día": DIAS, "Registros": n.to_numpy()})
    out["%"] = (100 * out.Registros / out.Registros.sum()).round(2)
    out["Índice (100 = promedio)"] = (100 * out.Registros / out.Registros.mean()).round(1)
    return out


def matriz_mes_anio(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="mes", columns="anio", values="orden", aggfunc="size", fill_value=0)


def matriz_dia_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio diario de delitos por día de la semana y mes (corrige que no todos los meses
    tienen el mismo número de lunes, martes…)."""
    conteo = df.groupby(["dia_semana", "mes"]).size()
    inicio, fin = df.fecha_hecho.min(), df.fecha_hecho.max()
    cal = pd.Series(pd.date_range(f"{inicio.year}-01-01", f"{fin.year}-12-31"))
    dias = cal.groupby([cal.dt.day_of_week + 1, cal.dt.month]).size()
    dias.index.names = ["dia_semana", "mes"]
    return (conteo / dias).unstack("mes").reindex(index=range(1, 8), columns=range(1, 13)).fillna(0)


def cambio_2020(df: pd.DataFrame) -> pd.DataFrame | None:
    """Variación de 2020 frente a 2019 y frente al promedio 2017–2019, por grupo de delito."""
    anios = set(df.anio.unique())
    if not {2017, 2018, 2019, 2020} <= anios:
        return None
    t = serie_anual(df)
    out = pd.DataFrame({
        "2019": t.loc[2019], "2020": t.loc[2020], "Promedio 2017–2019": t.loc[[2017, 2018, 2019]].mean(),
    })
    out.loc["TOTAL"] = [t.loc[2019].sum(), t.loc[2020].sum(), t.loc[[2017, 2018, 2019]].sum(axis=1).mean()]
    out["Variación vs 2019 (%)"] = 100 * (out["2020"] / out["2019"] - 1)
    out["Variación vs promedio 2017–2019 (%)"] = 100 * (out["2020"] / out["Promedio 2017–2019"] - 1)
    out = out[out["Promedio 2017–2019"] >= 20]  # grupos muy pequeños dan variaciones engañosas
    out = out.rename_axis("Grupo").reset_index()
    out["Grupo"] = out.Grupo.map(lambda g: ETIQUETA_GRUPO.get(g, "Total"))
    return out.round(1)


# =============================================================================
# 3.2 Espacio
# =============================================================================
def por_comuna(df: pd.DataFrame) -> pd.DataFrame:
    t = df.groupby(["comuna", "tipo_territorio"]).size().rename("Registros").reset_index()
    t["%"] = (100 * t.Registros / len(df)).round(2)
    return t.sort_values("Registros", ascending=False, ignore_index=True)


def top_barrios(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    b = df[df.barrio != SIN_DATO]
    moda_comuna = b.groupby("barrio").comuna.agg(lambda s: s.value_counts().index[0])
    t = b.barrio.value_counts().head(n).rename_axis("Barrio").reset_index(name="Registros")
    t["Comuna"] = t.Barrio.map(moda_comuna)
    t["%"] = (100 * t.Registros / len(df)).round(2)
    t["% acumulado"] = t["%"].cumsum().round(2)
    return t


def concentracion(df: pd.DataFrame, grupo: str | None = "HURTO") -> dict | None:
    """Curva de concentración: % acumulado de delitos frente a % acumulado de barrios (de mayor a menor)."""
    d = df if grupo is None else df[df.grupo_delito == grupo]
    vc = d.loc[d.barrio != SIN_DATO, "barrio"].value_counts()
    if vc.empty:
        return None
    acum = vc.cumsum() / vc.sum()
    n50 = int((acum < 0.5).sum() + 1)
    curva = pd.DataFrame({"pct_barrios": 100 * np.arange(1, len(vc) + 1) / len(vc), "pct_delitos": 100 * acum.to_numpy(),
                          "barrio": vc.index})
    # Índice de Gini a partir de la curva de Lorenz (barrios de menor a mayor)
    x = np.sort(vc.to_numpy())
    lorenz = np.cumsum(x) / x.sum()
    gini = 1 - 2 * np.trapezoid(np.r_[0, lorenz], dx=1 / len(x))
    return {"curva": curva, "barrios": len(vc), "barrios_50": n50, "pct_barrios_50": 100 * n50 / len(vc),
            "delitos": int(vc.sum()), "gini": float(gini), "top": vc.head(n50)}


# =============================================================================
# 3.3 Contingencia y correlación
# =============================================================================
def contingencia(df: pd.DataFrame, col: str, excluir_sin_dato: bool = True) -> dict:
    """Tabla de contingencia grupo de delito × variable de la víctima, con chi-cuadrado y V de Cramér.

    Los registros 'SIN DATO' se excluyen de la prueba: no son una categoría de la víctima sino la
    ausencia del dato. Se excluyen también los grupos con menos de 30 registros (esperados muy bajos).
    """
    from scipy.stats import chi2_contingency

    d = df
    if excluir_sin_dato:
        d = d[(d[col] != SIN_DATO) & (d.grupo_delito != SIN_DATO)]
    tabla = pd.crosstab(d.grupo_delito, d[col])
    tabla = tabla.loc[tabla.sum(axis=1) >= 30]
    tabla = tabla.loc[[g for g in GRUPOS if g in tabla.index]]
    if col == "curso_vida":
        tabla = tabla[[c for c in CURSO_VIDA if c in tabla.columns]]
    else:
        tabla = tabla[tabla.sum().sort_values(ascending=False).index]
    tabla = tabla.loc[:, tabla.sum() > 0]
    if min(tabla.shape) < 2:
        raise ValueError("La tabla de contingencia necesita al menos dos filas y dos columnas.")
    chi2, p, gl, esperados = chi2_contingency(tabla)
    n = int(tabla.to_numpy().sum())
    k = min(tabla.shape) - 1
    v = float(np.sqrt(chi2 / (n * k))) if k > 0 else np.nan
    return {
        "tabla": tabla, "fila_pct": 100 * tabla.div(tabla.sum(axis=1), axis=0), "chi2": float(chi2), "p": float(p),
        "gl": int(gl), "n": n, "v_cramer": v, "k": int(k), "pct_esperados_menor_5": float(100 * (esperados < 5).mean()),
        "excluidos": int(len(df) - n),
    }


def fuerza_v(v: float, k: int = 1) -> str:
    """Interpretación de Cohen (1988) para la V de Cramér.

    Los umbrales dependen de k = min(filas, columnas) − 1: efecto pequeño 0,1/√k, mediano 0,3/√k y
    grande 0,5/√k. Con k = 1 (p. ej., género con dos categorías) son 0,1; 0,3 y 0,5.
    """
    pequeno, mediano, grande = (u / np.sqrt(k) for u in (0.1, 0.3, 0.5))
    if v < pequeno:
        return "despreciable"
    if v < mediano:
        return "débil"
    if v < grande:
        return "moderada"
    return "fuerte"


def resumen_contingencias(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for col, nombre in [("genero", "Género"), ("curso_vida", "Curso de vida"), ("estado_civil", "Estado civil")]:
        c = contingencia(df, col)
        filas.append({"Variable de la víctima": nombre, "n analizado": c["n"], "Excluidos (SIN DATO)": c["excluidos"],
                      "Chi-cuadrado": round(c["chi2"], 1), "gl": c["gl"],
                      "p-valor": "< 0,001" if c["p"] < 0.001 else f"{c['p']:.3f}".replace(".", ","),
                      "V de Cramér": round(c["v_cramer"], 3), "k": c["k"],
                      "Asociación (Cohen)": fuerza_v(c["v_cramer"], c["k"]),
                      "% esperados < 5": round(c["pct_esperados_menor_5"], 1)})
    return pd.DataFrame(filas)


def conteos_barrio_anio(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz (barrio, año) × grupo de delito con el número de registros (0 si no hubo)."""
    d = df[(df.barrio != SIN_DATO) & (df.grupo_delito != SIN_DATO)]
    t = d.pivot_table(index=["barrio", "anio"], columns="grupo_delito", values="orden", aggfunc="size", fill_value=0)
    barrios, anios = d.barrio.unique(), sorted(d.anio.unique())
    t = t.reindex(pd.MultiIndex.from_product([barrios, anios], names=["barrio", "anio"]), fill_value=0)
    return t[[g for g in GRUPOS if g in t.columns]]


def spearman(df: pd.DataFrame, grupos: list[str] | None = None) -> dict:
    from scipy.stats import spearmanr

    t = conteos_barrio_anio(df)
    grupos = grupos or [g for g in GRUPOS[:6] if g in t.columns]
    t = t[grupos]
    rho, p = spearmanr(t.to_numpy())
    if np.ndim(rho) == 0:  # con dos variables scipy devuelve un escalar en vez de una matriz
        rho = np.array([[1.0, rho], [rho, 1.0]])
        p = np.array([[0.0, p], [p, 0.0]])
    rho = pd.DataFrame(rho, index=grupos, columns=grupos)
    p = pd.DataFrame(p, index=grupos, columns=grupos)
    return {"rho": rho, "p": p, "n": len(t), "datos": t}


# =============================================================================
# Figuras
# =============================================================================
def _go():
    import plotly.graph_objects as go

    return go


def fig_frecuencias_grupo(df: pd.DataFrame, clave: str = "frec_grupo"):
    go = _go()
    f = frecuencias(df, "grupo_delito").iloc[::-1]
    fig = go.Figure(go.Bar(
        y=f.Categoría.map(ETIQUETA_GRUPO), x=f.Registros, orientation="h",
        marker_color=[COLOR_GRUPO[g] for g in f.Categoría],
        text=[f"{fmt_int(n)} ({fmt_pct(p)})" for n, p in zip(f.Registros, f["%"])], textposition="outside",
        cliponaxis=False, textfont={"size": 11, "color": COLOR["tinta2"]},
        hovertemplate="%{y}: %{x:,} registros<extra></extra>"))
    fig.update_layout(barcornerradius=4, bargap=0.3)
    fig.update_xaxes(title="Registros", tickformat=",d", range=[0, f.Registros.max() * 1.25])
    fig.update_yaxes(title=None, type="category")
    return estilo_figura(fig, clave, alto=440)


def fig_histograma_diario(df: pd.DataFrame, clave: str = "hist_diario"):
    go = _go()
    s = conteos(df)["Por día"]
    fig = go.Figure(go.Histogram(x=s, xbins={"size": 2}, marker_color=COLOR["serie"][0],
                                 marker_line={"color": COLOR["superficie"], "width": 1},
                                 hovertemplate="%{x} delitos/día: %{y} días<extra></extra>"))
    for valor, nombre, desplaz in [(s.mean(), "Media", -12), (s.median(), "Mediana", 12)]:
        fig.add_vline(x=valor, line={"color": COLOR["tinta2"], "width": 1.5, "dash": "dash" if nombre == "Media" else "dot"})
        fig.add_annotation(x=valor, y=1, yref="paper", text=f"{nombre}: {valor:.1f}".replace(".", ","), showarrow=False,
                           xshift=desplaz * 4, yanchor="bottom", font={"size": 11, "color": COLOR["tinta2"]})
    fig.update_xaxes(title="Delitos registrados en un día")
    fig.update_yaxes(title="Número de días")
    return estilo_figura(fig, clave, alto=400)


def fig_histograma_barrio(df: pd.DataFrame, clave: str = "hist_barrio"):
    go = _go()
    s = conteos(df)["Por barrio"]
    fig = go.Figure(go.Histogram(x=np.log10(s), xbins={"size": 0.2}, marker_color=COLOR["serie"][0],
                                 marker_line={"color": COLOR["superficie"], "width": 1},
                                 hovertemplate="%{y} barrios<extra></extra>"))
    ticks = [1, 3, 10, 30, 100, 300, 1000, 3000, 10000]
    fig.update_xaxes(title="Delitos registrados en el barrio (2010–2021, escala logarítmica)",
                     tickvals=np.log10(ticks), ticktext=[fmt_int(t) for t in ticks])
    fig.update_yaxes(title="Número de barrios")
    return estilo_figura(fig, clave, alto=400)


def fig_serie_anual(df: pd.DataFrame, clave: str = "serie_anual"):
    go = _go()
    t = serie_anual(df)
    fig = go.Figure()
    principales = [g for g in GRUPOS[:5] if g in t.columns]
    for g in principales:
        fig.add_scatter(x=t.index, y=t[g], mode="lines+markers", name=ETIQUETA_GRUPO[g],
                        line={"color": COLOR_GRUPO[g], "width": 2}, marker={"size": 8},
                        hovertemplate="%{x}: %{y:,} registros<extra>" + ETIQUETA_GRUPO[g] + "</extra>")
    # Etiqueta directa solo en las dos series más altas al final; las demás terminan muy juntas y las
    # identifica la leyenda.
    for g in t[principales].iloc[-1].nlargest(2).index:
        fig.add_annotation(x=t.index[-1], y=t[g].iloc[-1], text=ETIQUETA_GRUPO[g], showarrow=False, xanchor="left",
                           xshift=8, font={"size": 11, "color": COLOR["tinta2"]})
    fig.update_xaxes(title=None, tickvals=list(t.index), range=[t.index.min() - 0.3, t.index.max() + 1.3])
    fig.update_yaxes(title="Registros por año", rangemode="tozero", tickformat=",d")
    return estilo_figura(fig, clave, alto=460)


def fig_serie_mensual(df: pd.DataFrame, clave: str = "serie_mensual"):
    go = _go()
    s = serie_mensual(df)
    fig = go.Figure()
    fig.add_scatter(x=s.mes, y=s.delitos, mode="lines", name="Registros del mes",
                    line={"color": COLOR["serie"][0], "width": 2},
                    hovertemplate="%{x|%m/%Y}: %{y:,} registros<extra></extra>")
    fig.add_scatter(x=s.mes, y=s.media_movil_12, mode="lines", name="Media móvil de 12 meses",
                    line={"color": COLOR["tinta2"], "width": 2, "dash": "dash"},
                    hovertemplate="%{x|%m/%Y}: %{y:,.0f}<extra>Media móvil</extra>")
    if (s.mes.dt.year == 2020).any():
        fig.add_vrect(x0="2020-03-20", x1="2020-08-31", fillcolor=COLOR["rejilla"], opacity=0.5, line_width=0)
        fig.add_annotation(x="2020-06-01", y=1, yref="paper", text="Cuarentena 2020", showarrow=False,
                           yanchor="bottom", font={"size": 11, "color": COLOR["tinta2"]})
    fig.update_xaxes(title=None, dtick="M12", tickformat="%Y")
    fig.update_yaxes(title="Registros por mes", rangemode="tozero", tickformat=",d")
    return estilo_figura(fig, clave, alto=440)


def fig_dia_semana(df: pd.DataFrame, clave: str = "dia_semana"):
    go = _go()
    d = por_dia_semana(df)
    fig = go.Figure(go.Bar(x=d.Día, y=d.Registros, marker_color=COLOR["serie"][0],
                           text=[fmt_pct(p) for p in d["%"]], textposition="inside", insidetextanchor="start",
                           textfont={"size": 12, "color": "white"},
                           hovertemplate="%{x}: %{y:,} registros<extra></extra>"))
    fig.add_hline(y=d.Registros.mean(), line={"color": COLOR["tinta2"], "dash": "dash", "width": 1.5})
    fig.add_annotation(x=1, xref="paper", y=d.Registros.mean(), text="Promedio", showarrow=False, xanchor="right",
                       yanchor="bottom", font={"size": 11, "color": COLOR["tinta2"]})
    fig.update_layout(barcornerradius=4, bargap=0.35)
    fig.update_xaxes(title=None)
    fig.update_yaxes(title="Registros", tickformat=",d", rangemode="tozero")
    return estilo_figura(fig, clave, alto=420)


def _heatmap(z: pd.DataFrame, x, y, clave: str, titulo_color: str, formato: str, alto: int, hover: str,
             desde_cero: bool = True):
    go = _go()
    escala = [[i / (len(SECUENCIAL) - 1), c] for i, c in enumerate(SECUENCIAL)]
    vmax = z.to_numpy().max()
    vmin = 0 if desde_cero else z.to_numpy().min()
    texto = [[formato.format(v).replace(",", "X").replace(".", ",").replace("X", ".") for v in fila] for fila in z.to_numpy()]
    fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=x, y=y, colorscale=escala, xgap=2, ygap=2,
                               text=texto, texttemplate="%{text}", textfont={"size": 10},
                               colorbar={"title": {"text": titulo_color, "side": "right"}, "thickness": 12},
                               hovertemplate=hover + "<extra></extra>", zmin=vmin, zmax=vmax))
    fig.update_yaxes(autorange="reversed", type="category")
    fig.update_xaxes(type="category", side="bottom")
    return estilo_figura(fig, clave, alto=alto)


def fig_heat_mes_anio(df: pd.DataFrame, clave: str = "heat_mes_anio"):
    m = matriz_mes_anio(df)
    return _heatmap(m, [str(a) for a in m.columns], [MESES[i - 1] for i in m.index], clave,
                    "Registros", "{:,.0f}", 480, "%{y} %{x}: %{z:,} registros")


def fig_heat_dia_mes(df: pd.DataFrame, clave: str = "heat_dia_mes"):
    m = matriz_dia_mes(df)
    # La escala empieza en el mínimo observado: los promedios varían entre unos 24 y 38 delitos diarios,
    # y una escala desde 0 ocultaría esas diferencias.
    return _heatmap(m, MESES, DIAS, clave, "Promedio diario", "{:.1f}", 400,
                    "%{y} de %{x}: %{z:.1f} delitos por día en promedio", desde_cero=False)


def fig_cambio_2020(df: pd.DataFrame, clave: str = "cambio_2020"):
    go = _go()
    c = cambio_2020(df)
    if c is None:
        return None
    c = c.iloc[::-1]
    col = "Variación vs promedio 2017–2019 (%)"
    colores = [COLOR["tinta2"] if g == "Total" else (COLOR["critico"] if v > 0 else COLOR["serie"][0])
               for g, v in zip(c.Grupo, c[col])]
    fig = go.Figure(go.Bar(y=c.Grupo, x=c[col], orientation="h", marker_color=colores,
                           text=[(f"+{v:.1f} %" if v > 0 else f"{v:.1f} %").replace(".", ",") for v in c[col]],
                           textposition="outside", cliponaxis=False, textfont={"size": 11, "color": COLOR["tinta2"]},
                           customdata=np.stack([c["Promedio 2017–2019"], c["2020"]], axis=-1),
                           hovertemplate="%{y}<br>Promedio 2017–2019: %{customdata[0]:,.0f}<br>2020: %{customdata[1]:,}"
                                         "<br>Variación: %{x:.1f} %<extra></extra>"))
    fig.add_vline(x=0, line={"color": COLOR["eje"], "width": 1})
    lim = max(abs(c[col].min()), abs(c[col].max())) * 1.3
    fig.update_layout(barcornerradius=4, bargap=0.35)
    fig.update_xaxes(title="Variación de 2020 frente al promedio 2017–2019 (%)", ticksuffix=" %", range=[-lim, lim])
    fig.update_yaxes(title=None, type="category")
    return estilo_figura(fig, clave, alto=420)


def fig_comunas(df: pd.DataFrame, clave: str = "comunas"):
    go = _go()
    c = por_comuna(df)
    c = c[c.comuna != SIN_DATO].iloc[::-1]
    colores = [COLOR["serie"][0] if t == "COMUNA" else COLOR["serie"][2] for t in c.tipo_territorio]
    fig = go.Figure(go.Bar(y=c.comuna, x=c.Registros, orientation="h", marker_color=colores,
                           text=[f"{fmt_int(n)} ({fmt_pct(p)})" for n, p in zip(c.Registros, c["%"])],
                           textposition="outside", cliponaxis=False, textfont={"size": 10, "color": COLOR["tinta2"]},
                           hovertemplate="%{y}: %{x:,} registros<extra></extra>", showlegend=False))
    for nombre, color in [("Comuna (urbana)", COLOR["serie"][0]), ("Corregimiento (rural)", COLOR["serie"][2])]:
        fig.add_bar(x=[None], y=[None], name=nombre, marker_color=color, showlegend=True)
    fig.update_layout(barcornerradius=3, bargap=0.25)
    fig.update_xaxes(title="Registros", tickformat=",d", range=[0, c.Registros.max() * 1.25])
    fig.update_yaxes(title=None, type="category")
    return estilo_figura(fig, clave, alto=620)


def fig_top_barrios(df: pd.DataFrame, clave: str = "top_barrios", n: int = 20):
    go = _go()
    t = top_barrios(df, n).iloc[::-1]
    fig = go.Figure(go.Bar(y=t.Barrio, x=t.Registros, orientation="h", marker_color=COLOR["serie"][0],
                           text=[f"{fmt_int(v)} · {c}" for v, c in zip(t.Registros, t.Comuna)], textposition="outside",
                           cliponaxis=False, textfont={"size": 10, "color": COLOR["tinta2"]},
                           hovertemplate="%{y}: %{x:,} registros<extra></extra>"))
    fig.update_layout(barcornerradius=3, bargap=0.25)
    fig.update_xaxes(title="Registros (etiqueta: registros · comuna)", tickformat=",d", range=[0, t.Registros.max() * 1.45])
    fig.update_yaxes(title=None, type="category")
    return estilo_figura(fig, clave, alto=600)


def fig_concentracion(df: pd.DataFrame, clave: str = "concentracion_hurto", grupo: str = "HURTO"):
    go = _go()
    c = concentracion(df, grupo)
    if c is None:
        return None
    cur = c["curva"]
    fig = go.Figure()
    fig.add_scatter(x=np.r_[0, cur.pct_barrios], y=np.r_[0, cur.pct_delitos], mode="lines",
                    name=f"{ETIQUETA_GRUPO[grupo]}: barrios ordenados de más a menos registros",
                    line={"color": COLOR["serie"][0], "width": 2.5},
                    customdata=np.r_[[""], cur.barrio], hovertemplate="%{x:.1f} % de los barrios → %{y:.1f} % de los registros"
                                                                       "<br>Último barrio: %{customdata}<extra></extra>")
    fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", name="Distribución uniforme (referencia)",
                    line={"color": COLOR["eje"], "dash": "dash", "width": 1.5}, hoverinfo="skip")
    x50 = c["pct_barrios_50"]
    fig.add_shape(type="line", x0=0, x1=x50, y0=50, y1=50, line={"color": COLOR["critico"], "dash": "dot", "width": 1.5})
    fig.add_shape(type="line", x0=x50, x1=x50, y0=0, y1=50, line={"color": COLOR["critico"], "dash": "dot", "width": 1.5})
    fig.add_annotation(x=x50, y=50, text=f"{c['barrios_50']} barrios ({fmt_pct(x50)}) concentran<br>el 50 % de los registros",
                       showarrow=True, ax=90, ay=40, font={"size": 11, "color": COLOR["tinta"]}, arrowcolor=COLOR["tenue"],
                       align="left")
    fig.update_xaxes(title="% acumulado de barrios", ticksuffix=" %", range=[0, 100])
    fig.update_yaxes(title="% acumulado de registros", ticksuffix=" %", range=[0, 101])
    return estilo_figura(fig, clave, alto=460)


def fig_contingencia(df: pd.DataFrame, col: str, clave: str):
    c = contingencia(df, col)
    pct = c["fila_pct"]
    y = [ETIQUETA_GRUPO[g] for g in pct.index]
    x = [str(v).title() if col != "curso_vida" else str(v)[4:].title() for v in pct.columns]
    fig = _heatmap(pct.round(1), x, y, clave, "% de la fila", "{:.1f}", 440,
                   "%{y} · %{x}: %{z:.1f} % de las víctimas del grupo")
    fig.add_annotation(
        text=(f"χ² = {fmt_int(round(c['chi2']))}; gl = {c['gl']}; p {'< 0,001' if c['p'] < 0.001 else '= ' + format(c['p'], '.3f')}"
              f"; V de Cramér = {c['v_cramer']:.3f}".replace(".", ",") + f"; n = {fmt_int(c['n'])}"),
        xref="paper", yref="paper", x=1, y=1.02, xanchor="right", yanchor="bottom", showarrow=False,
        font={"size": 11, "color": COLOR["tinta2"]})
    return fig


def fig_spearman(df: pd.DataFrame, clave: str = "spearman"):
    go = _go()
    s = spearman(df)
    rho = s["rho"]
    etiquetas = [ETIQUETA_GRUPO[g] for g in rho.index]
    azul_rojo = [[0, "#184f95"], [0.25, "#6da7ec"], [0.5, "#f0efec"], [0.75, "#ec835a"], [1, "#d03b3b"]]
    fig = go.Figure(go.Heatmap(z=rho.to_numpy(), x=etiquetas, y=etiquetas, zmin=-1, zmax=1, colorscale=azul_rojo,
                               xgap=2, ygap=2, text=[[f"{v:.2f}".replace(".", ",") for v in fila] for fila in rho.to_numpy()],
                               texttemplate="%{text}", textfont={"size": 12},
                               colorbar={"title": {"text": "ρ de Spearman", "side": "right"}, "thickness": 12},
                               hovertemplate="%{y} · %{x}: ρ = %{z:.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.add_annotation(text=f"Unidad: barrio-año (n = {fmt_int(s['n'])}); todos los coeficientes con p < 0,001"
                       if (s["p"].to_numpy() < 0.001).all() else f"Unidad: barrio-año (n = {fmt_int(s['n'])})",
                       xref="paper", yref="paper", x=1, y=1.02, xanchor="right", yanchor="bottom", showarrow=False,
                       font={"size": 11, "color": COLOR["tinta2"]})
    return estilo_figura(fig, clave, alto=480)


def fig_dispersion(df: pd.DataFrame, clave: str = "dispersion", x_grupo: str = "HURTO",
                   y_grupo: str = "VIOLENCIA INTRAFAMILIAR"):
    go = _go()
    s = spearman(df, [x_grupo, y_grupo])
    t = s["datos"].reset_index()
    rho = s["rho"].iloc[0, 1]
    # Se suma 1 para poder usar escala logarítmica con los barrio-año sin registros
    fig = go.Figure(go.Scattergl(
        x=t[x_grupo] + 1, y=t[y_grupo] + 1, mode="markers",
        marker={"size": 6, "color": COLOR["serie"][0], "opacity": 0.35, "line": {"width": 0}},
        customdata=np.stack([t.barrio, t.anio, t[x_grupo], t[y_grupo]], axis=-1),
        hovertemplate="%{customdata[0]} (%{customdata[1]})<br>" + ETIQUETA_GRUPO[x_grupo] + ": %{customdata[2]}<br>"
                      + ETIQUETA_GRUPO[y_grupo] + ": %{customdata[3]}<extra></extra>", name="Barrio-año"))
    fig.update_xaxes(type="log", title=f"{ETIQUETA_GRUPO[x_grupo]} por barrio y año (+1, escala log)")
    fig.update_yaxes(type="log", title=f"{ETIQUETA_GRUPO[y_grupo]} por barrio y año (+1, escala log)")
    fig.add_annotation(text=f"ρ de Spearman = {rho:.2f}".replace(".", ",") + f"; n = {fmt_int(s['n'])} barrio-año",
                       xref="paper", yref="paper", x=1, y=1.02, xanchor="right", yanchor="bottom", showarrow=False,
                       font={"size": 11, "color": COLOR["tinta2"]})
    return estilo_figura(fig, clave, alto=480)


# =============================================================================
# 4.1 Selección de gráficos y 4.2 mapas de concentración
# =============================================================================
SELECCION_GRAFICOS = pd.DataFrame([
    ("Grupo de delito, arma, género, curso de vida, estado civil, móvil, zona", "Categórica nominal u ordinal",
     "Frecuencia y proporción de cada categoría", "Barras horizontales ordenadas; tabla de frecuencias",
     "La longitud de una barra se compara con precisión; la orientación horizontal deja leer etiquetas largas. Se descartan los gráficos circulares: con más de 4 categorías los ángulos no se comparan bien.",
     "frecuencias frec_grupo"),
    ("Delitos por día y por barrio", "Numérica discreta (conteo)",
     "Forma de la distribución, simetría, sesgo", "Histograma (escala log en barrios)",
     "Muestra la forma completa de la distribución; la escala logarítmica hace legible un conteo con cola larga.",
     "hist_diario hist_barrio"),
    ("Delitos por día y por barrio", "Numérica discreta (conteo)",
     "Valores atípicos", "Diagrama de caja",
     "Resume mediana, cuartiles y valores fuera de los bigotes de Tukey; permite comparar años lado a lado.",
     "box_diario box_barrio"),
    ("Año, mes", "Temporal", "Tendencia y estacionalidad", "Serie de tiempo (líneas) con media móvil",
     "La línea conserva el orden temporal y hace visibles tendencias, quiebres y la caída de 2020.",
     "serie_anual serie_mensual"),
    ("Mes × año; día de la semana × mes", "Dos variables temporales",
     "Patrones cruzados (estacionalidad por año, día por mes)", "Mapa de calor",
     "Una matriz con color secuencial de un solo tono permite leer 144 u 84 celdas a la vez y encontrar bloques altos o bajos.",
     "heat_mes_anio heat_dia_mes"),
    ("Día de la semana", "Categórica ordinal", "Comparación entre días", "Barras verticales con línea de promedio",
     "El orden natural de los días se conserva en el eje X; la línea de promedio hace evidente el exceso del sábado.",
     "dia_semana"),
    ("Variación 2020 por grupo", "Numérica con signo", "Aumento o descenso frente a una referencia",
     "Barras divergentes desde 0", "El signo se lee por el lado de la barra y el color (rojo aumento, azul descenso).",
     "cambio_2020"),
    ("Comuna, barrio", "Categórica nominal (espacial)", "Ranking de zonas", "Barras horizontales ordenadas",
     "Ordenar de mayor a menor convierte la comparación en un ranking directo.", "comunas top_barrios"),
    ("Barrio (hurtos acumulados)", "Conteo acumulado", "Concentración espacial", "Curva de concentración (Lorenz)",
     "Responde directamente qué porcentaje de barrios acumula el 50 % de los hurtos y se compara con la diagonal de reparto uniforme.",
     "concentracion_hurto"),
    ("Latitud y longitud", "Coordenadas", "Concentración geográfica", "Mapa de densidad sobre mapa base",
     "Con más de 120.000 puntos, un mapa de puntos se satura; la densidad muestra dónde se acumulan los hechos.",
     "coord_despues mapa_densidad mapa_grupos"),
    ("Grupo de delito × género / curso de vida / estado civil", "Dos categóricas",
     "Asociación entre delito y víctima", "Tabla de contingencia como mapa de calor (% por fila) + chi-cuadrado y V de Cramér",
     "El porcentaje por fila compara perfiles de víctima entre delitos de tamaño muy distinto; la prueba cuantifica la asociación.",
     "cont_genero cont_curso cont_estado chi2"),
    ("Conteos por barrio y año de cada grupo", "Numéricas discretas", "Correlación",
     "Mapa de calor de correlación de Spearman y gráfico de dispersión (escala log)",
     "Spearman no exige linealidad ni normalidad (conteos asimétricos); la dispersión muestra la nube real detrás del coeficiente.",
     "spearman dispersion"),
], columns=["Variable(s)", "Tipo de variable", "Pregunta del análisis", "Gráfico elegido", "Por qué", "claves"])


def seleccion_graficos() -> pd.DataFrame:
    """Tabla 4.1 con el número de figura de cada ejemplo, tomado del catálogo (src.utils.FIGURAS)."""
    from src.utils import figura

    t = SELECCION_GRAFICOS.copy()
    t["Figuras"] = t.pop("claves").map(lambda c: ", ".join(str(figura(k)[0]) for k in c.split()))
    return t

CENTRO_MAPA = {"lat": 7.112, "lon": -73.118}
# Escala secuencial de un solo tono (azul), de transparente a oscuro
ESCALA_DENSIDAD = [[0, "rgba(205,226,251,0)"], [0.1, "rgba(158,197,244,0.55)"], [0.35, "#6da7ec"],
                   [0.6, "#2a78d6"], [0.85, "#184f95"], [1, "#0d366b"]]


def celdas(df: pd.DataFrame, tamano: float = 0.001) -> pd.DataFrame:
    """Agrupa las coordenadas válidas en celdas de ~110 m (0,001°) con su número de delitos.

    Con más de 120.000 puntos, la densidad calculada punto a punto satura el mapa; agregando por
    celda y fijando el máximo de la escala en el percentil 95 se distinguen los focos.
    """
    v = df.dropna(subset=["latitud"])
    g = v.assign(lat=(v.latitud / tamano).round() * tamano, lon=(v.longitud / tamano).round() * tamano)
    return g.groupby(["lat", "lon"]).size().rename("delitos").reset_index()


def _densitymap(c: pd.DataFrame, mostrar_escala: bool = True, radio: int = 9):
    go = _go()
    tope = float(c.delitos.quantile(0.95)) if len(c) else 1
    return go.Densitymap(lat=c.lat, lon=c.lon, z=c.delitos, radius=radio, zmin=0, zmax=tope,
                         colorscale=ESCALA_DENSIDAD, showscale=mostrar_escala,
                         colorbar={"title": {"text": "Delitos por celda<br>(~110 m)", "side": "right"},
                                   "thickness": 12},
                         hovertemplate="%{z} delitos en la celda<extra></extra>")


def fig_mapa_densidad(df: pd.DataFrame, clave: str = "mapa_densidad"):
    go = _go()
    c = celdas(df)
    fig = go.Figure(_densitymap(c))
    fig.update_layout(map={"style": "carto-positron", "center": CENTRO_MAPA, "zoom": 12})
    fig.add_annotation(text=f"{fmt_int(int(c.delitos.sum()))} delitos con coordenada válida en {fmt_int(len(c))} celdas; "
                            "escala hasta el percentil 95", xref="paper", yref="paper",
                       x=1, y=1.02, xanchor="right", yanchor="bottom", showarrow=False,
                       font={"size": 11, "color": COLOR["tinta2"]})
    return estilo_figura(fig, clave, alto=660)


def fig_mapas_grupos(df: pd.DataFrame, clave: str = "mapa_grupos",
                     grupos: tuple[str, ...] = ("HURTO", "VIOLENCIA INTRAFAMILIAR", "LESIONES PERSONALES",
                                                "LESIONES EN ACCIDENTE DE TRANSITO")):
    """Pequeños múltiplos: un mapa de densidad por grupo, cada uno con su propia escala relativa.

    Los delitos sexuales no se incluyen porque la fuente no publica su ubicación (todos sus registros
    traen el marcador 'xx.xxxx').
    """
    from plotly.subplots import make_subplots

    grupos = [g for g in grupos if df[df.grupo_delito == g].latitud.notna().any()]
    if not grupos:
        return None
    filas = (len(grupos) + 1) // 2
    titulos = [f"{ETIQUETA_GRUPO[g]} ({fmt_int(int(df[(df.grupo_delito == g)].latitud.notna().sum()))})" for g in grupos]
    fig = make_subplots(rows=filas, cols=2, specs=[[{"type": "map"}] * 2] * filas, subplot_titles=titulos,
                        horizontal_spacing=0.02, vertical_spacing=0.06)
    for i, g in enumerate(grupos):
        fig.add_trace(_densitymap(celdas(df[df.grupo_delito == g]), mostrar_escala=False, radio=8),
                      row=i // 2 + 1, col=i % 2 + 1)
    for i in range(len(grupos)):
        nombre = "map" if i == 0 else f"map{i + 1}"
        fig.layout[nombre].update(style="carto-positron", center=CENTRO_MAPA, zoom=11.2)
    fig.add_annotation(text="Escala relativa en cada mapa (hasta su percentil 95); entre paréntesis, registros con ubicación",
                       xref="paper", yref="paper", x=1, y=1.04, xanchor="right", yanchor="bottom", showarrow=False,
                       font={"size": 11, "color": COLOR["tinta2"]})
    return estilo_figura(fig, clave, alto=420 * filas + 60)


def _fig_cont_genero(df): return fig_contingencia(df, "genero", "cont_genero")
def _fig_cont_curso(df): return fig_contingencia(df, "curso_vida", "cont_curso")
def _fig_cont_estado(df): return fig_contingencia(df, "estado_civil", "cont_estado")


FIGURAS_PLOTLY = {
    "frec_grupo": fig_frecuencias_grupo, "hist_diario": fig_histograma_diario, "hist_barrio": fig_histograma_barrio,
    "serie_anual": fig_serie_anual, "serie_mensual": fig_serie_mensual, "dia_semana": fig_dia_semana,
    "heat_mes_anio": fig_heat_mes_anio, "heat_dia_mes": fig_heat_dia_mes, "cambio_2020": fig_cambio_2020,
    "comunas": fig_comunas, "top_barrios": fig_top_barrios, "concentracion_hurto": fig_concentracion,
    "cont_genero": _fig_cont_genero, "cont_curso": _fig_cont_curso, "cont_estado": _fig_cont_estado,
    "spearman": fig_spearman, "dispersion": fig_dispersion,
    "mapa_densidad": fig_mapa_densidad, "mapa_grupos": fig_mapas_grupos,
}


def main() -> None:
    from src.utils import DATA_PROCESSED

    df = pd.read_parquet(DATA_PROCESSED / "delitos_limpios.parquet")
    pd.set_option("display.width", 220)
    print(frecuencias(df, "grupo_delito").to_string(index=False), "\n")
    print(descriptivas_conteos(df).to_string(index=False), "\n")
    print(serie_anual(df).to_string(), "\n")
    print(por_dia_semana(df).to_string(index=False), "\n")
    print(cambio_2020(df).to_string(index=False), "\n")
    print(por_comuna(df).head(8).to_string(index=False), "\n")
    c = concentracion(df)
    print(f"Hurtos: {c['delitos']} en {c['barrios']} barrios; {c['barrios_50']} barrios ({c['pct_barrios_50']:.1f} %) "
          f"concentran el 50 %; Gini = {c['gini']:.3f}\n")
    print(resumen_contingencias(df).to_string(index=False), "\n")
    s = spearman(df)
    print(s["rho"].round(3).to_string(), "\nn =", s["n"])


if __name__ == "__main__":
    main()
