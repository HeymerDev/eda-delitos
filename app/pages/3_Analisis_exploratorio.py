"""Análisis exploratorio (objetivo 3)."""
import streamlit as st

from comun import (
    aviso_filtros_activos,
    cargar_limpios,
    configurar_pagina,
    filtros_sidebar,
    grafico_figura,
    tabla_estatica,
    tabla_figura,
)
from src import eda
from src.eda import ETIQUETA_GRUPO, GRUPOS, VARIABLES_FRECUENCIA
from src.utils import fmt_dec, fmt_int, fmt_pct

configurar_pagina("Análisis exploratorio")
datos, origen = cargar_limpios()
df, activos = filtros_sidebar(datos)

st.title("Análisis exploratorio")
st.markdown(
    "**Objetivo 3.** Describir la distribución de los delitos en el espacio, en el tiempo y según el perfil de "
    f"las víctimas. Se analiza el conjunto limpio (`delitos_limpios`, {origen})."
)
aviso_filtros_activos(activos)
if len(df) < 50:
    st.warning("La selección tiene muy pocos registros para el análisis. Amplíe los filtros.")
    st.stop()

m = st.columns(4)
m[0].metric("Registros analizados", fmt_int(len(df)))
m[1].metric("Periodo", f"{df.anio.min()}–{df.anio.max()}")
m[2].metric("Promedio diario", fmt_dec(eda.conteos(df)["Por día"].mean(), 1))
m[3].metric("Barrios con registros", fmt_int(df.loc[df.barrio != "SIN DATO", "barrio"].nunique()))


def figura_opcional(fig, clave):
    if fig is None:
        st.caption("Esta figura no está disponible con los filtros actuales.")
    else:
        grafico_figura(fig, clave)


# =============================================================================
st.header("3.1 Estadísticas descriptivas y frecuencias", anchor="actividad-3-1")
frec_g = eda.frecuencias(df, "grupo_delito")
st.markdown(
    """
Todas las variables del conjunto son **categóricas**, así que su descripción se hace con frecuencias y
porcentajes. Las únicas variables numéricas son los **conteos** que resultan de agregar los registros (delitos
por día, mes, barrio o comuna), y sobre ellos se calculan las medidas de tendencia central, dispersión y forma.
"""
)
if len(frec_g) > 1:
    st.markdown(
        f"El grupo de delito más frecuente es **{ETIQUETA_GRUPO[frec_g.Categoría.iloc[0]].lower()}** "
        f"({fmt_pct(frec_g['%'].iloc[0])} de los registros), seguido de "
        f"{ETIQUETA_GRUPO[frec_g.Categoría.iloc[1]].lower()} ({fmt_pct(frec_g['%'].iloc[1])})."
    )
tabla_figura(eda.resumen_frecuencias(df), "frecuencias")
with st.expander("Frecuencias completas de cualquier variable"):
    var = st.selectbox("Variable", list(VARIABLES_FRECUENCIA), format_func=VARIABLES_FRECUENCIA.get)
    st.dataframe(eda.frecuencias(df, var), hide_index=True, width="stretch")
grafico_figura(eda.fig_frecuencias_grupo(df), "frec_grupo")

desc = eda.descriptivas_conteos(df)
dia = desc.set_index("Conteo de delitos").loc["Por día"]
barrio = desc.set_index("Conteo de delitos").loc["Por barrio"]
st.markdown(
    f"""
- **Conteo diario:** su distribución es casi simétrica. La media es de {fmt_dec(dia.Media, 1)} delitos por día,
  la mediana de {fmt_int(dia.Mediana)} y la asimetría de {fmt_dec(dia.Asimetría)}.
- **Conteo por barrio:** está muy sesgado a la derecha. La mediana es de {fmt_int(barrio.Mediana)} delitos, la
  media de {fmt_int(round(barrio.Media))} y la asimetría de {fmt_dec(barrio.Asimetría, 1)}. Pocos barrios concentran
  muchos registros.
"""
)
tabla_figura(desc, "desc_conteos")
c1, c2 = st.columns(2)
with c1:
    grafico_figura(eda.fig_histograma_diario(df), "hist_diario")
with c2:
    grafico_figura(eda.fig_histograma_barrio(df), "hist_barrio")

# =============================================================================
st.header("3.2 Distribución por periodo de tiempo y por zona geográfica", anchor="actividad-3-2")
st.subheader("Tiempo")
anual = df.groupby("anio").size()
dsem = eda.por_dia_semana(df)
st.markdown(
    f"""
- **Año con más registros:** {anual.idxmax()} ({fmt_int(anual.max())}); con menos, {anual.idxmin()}
  ({fmt_int(anual.min())}).
- **Día de la semana:** el sábado concentra el {fmt_pct(dsem.set_index("Día").loc["Sábado", "%"])} de los
  registros, un {fmt_dec(dsem.set_index("Día").loc["Sábado", "Índice (100 = promedio)"] - 100, 1)} % por encima
  del promedio diario. El resto de los días es parejo.
- **Cambios bruscos:** las series anuales por grupo muestran quiebres, como el de las lesiones en tránsito
  entre 2016 y 2017 o el de los delitos sexuales en 2019. Deben leerse con cautela, porque pueden reflejar
  cambios en el registro de la fuente y no solo en la ocurrencia.
"""
)
grafico_figura(eda.fig_serie_anual(df), "serie_anual")
grafico_figura(eda.fig_serie_mensual(df), "serie_mensual")
grafico_figura(eda.fig_dia_semana(df), "dia_semana")
grafico_figura(eda.fig_heat_mes_anio(df), "heat_mes_anio")
grafico_figura(eda.fig_heat_dia_mes(df), "heat_dia_mes")

st.markdown("**Cambio en 2020.** Se compara 2020 con 2019 y con el promedio de 2017–2019, que es más estable que "
            "un solo año. Se omiten los grupos con menos de 20 registros anuales en promedio.")
figura_opcional(eda.fig_cambio_2020(df), "cambio_2020")
c20 = eda.cambio_2020(df)
if c20 is not None:
    with st.expander("Tabla del cambio en 2020"):
        tabla_estatica(c20)

st.subheader("Espacio")
com = eda.por_comuna(df)
conc = eda.concentracion(df, "HURTO")
st.markdown(
    f"""
- **Comuna con más registros:** {com.comuna.iloc[0]} ({fmt_pct(com["%"].iloc[0])}). Las cinco primeras suman el
  {fmt_pct(com["%"].head(5).sum())} de los registros.
- **Corregimientos:** los tres corregimientos rurales suman
  {fmt_pct(com[com.tipo_territorio == "CORREGIMIENTO"]["%"].sum())}.
"""
    + (
        f"""- **Concentración de los hurtos:** **{conc["barrios_50"]} de {conc["barrios"]} barrios
  ({fmt_pct(conc["pct_barrios_50"])}) concentran el 50 % de los hurtos**, con un índice de Gini de
  {fmt_dec(conc["gini"])} entre barrios."""
        if conc else ""
    )
)
grafico_figura(eda.fig_comunas(df), "comunas")
grafico_figura(eda.fig_top_barrios(df), "top_barrios")
figura_opcional(eda.fig_concentracion(df), "concentracion_hurto")
if conc:
    with st.expander(f"Los {conc['barrios_50']} barrios que concentran la mitad de los hurtos"):
        st.dataframe(conc["top"].rename_axis("Barrio").reset_index(name="Hurtos"), hide_index=True)

# =============================================================================
st.header("3.3 Tipos de delito y características de las víctimas", anchor="actividad-3-3")
st.markdown(
    """
**Método.** Se construyó una tabla de contingencia entre el grupo de delito y cada característica de la víctima:
género, curso de vida y estado civil.

- **Prueba de independencia:** chi-cuadrado de Pearson.
- **Fuerza de la asociación:** V de Cramér, interpretada con los umbrales de Cohen (1988) ajustados al número
  de categorías, k = min(filas, columnas) − 1. Una asociación es pequeña desde 0,1/√k, mediana desde 0,3/√k y
  grande desde 0,5/√k.
- **Exclusiones:** los registros «SIN DATO» se excluyen de cada prueba, porque representan la ausencia del dato
  y no una categoría de la víctima. También se excluyen los grupos con menos de 30 registros.

Las figuras muestran el porcentaje por fila: cómo se distribuyen las víctimas de cada grupo de delito.
"""
)
try:
    for col, clave in [("genero", "cont_genero"), ("curso_vida", "cont_curso"), ("estado_civil", "cont_estado")]:
        grafico_figura(eda.fig_contingencia(df, col, clave), clave)
        with st.expander("Tabla de contingencia con frecuencias absolutas"):
            t = eda.contingencia(df, col)["tabla"]
            t.index = [ETIQUETA_GRUPO[g] for g in t.index]
            st.dataframe(t, width="stretch")
    st.markdown("Resumen de las tres pruebas de independencia:")
    tabla_figura(eda.resumen_contingencias(df), "chi2")
except ValueError:
    st.caption("Con los filtros actuales no hay suficientes categorías para las pruebas de chi-cuadrado.")

st.subheader("Correlación entre conteos agregados")
st.markdown(
    """
Las variables del conjunto son categóricas, así que no admiten una correlación directa. Para cumplir el
análisis de correlaciones se **agregaron los registros por barrio y año** y se calculó la correlación de
Spearman entre los conteos de cada grupo de delito.

Se usa Spearman porque los conteos son asimétricos y la relación no tiene por qué ser lineal. **Precaución:**
los barrios más grandes o más concurridos tienden a registrar más delitos de todo tipo, y el conjunto no
incluye la población de cada barrio. Por eso una correlación positiva indica que los delitos coinciden en los
mismos lugares, no que uno cause el otro.
"""
)
opciones = [g for g in GRUPOS[:6] if g in set(df.grupo_delito)]
if len(opciones) < 2:
    st.caption("La correlación necesita al menos dos grupos de delito en la selección.")
else:
    grafico_figura(eda.fig_spearman(df), "spearman")
    g1, g2 = st.columns(2)
    x_g = g1.selectbox("Eje X", opciones, index=0, format_func=ETIQUETA_GRUPO.get)
    y_g = g2.selectbox("Eje Y", opciones, index=min(3, len(opciones) - 1), format_func=ETIQUETA_GRUPO.get)
    if x_g != y_g:
        grafico_figura(eda.fig_dispersion(df, "dispersion", x_g, y_g), "dispersion")
    else:
        st.caption("Elija dos grupos distintos.")
