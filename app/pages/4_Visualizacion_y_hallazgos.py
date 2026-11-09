"""Visualización y hallazgos (objetivo 4)."""
import re

import streamlit as st

from comun import (
    aviso_filtros_activos,
    cargar_diagnostico,
    cargar_limpieza,
    cargar_limpios,
    configurar_pagina,
    filtros_sidebar,
    fuente,
    grafico_figura,
    tabla_figura,
    titulo,
)
from src import diagnostico, eda
from src.utils import DOCS, SQL_DIR, fmt_dec, fmt_int, fmt_pct, figura

configurar_pagina("Visualización y hallazgos")
datos, origen = cargar_limpios()
df, activos = filtros_sidebar(datos)
RUTA_CONTRASTE = DOCS / "contraste_antecedentes.md"

st.title("Visualización y hallazgos")
st.markdown(
    "**Objetivo 4.** Visualizar los patrones delictivos identificados mediante gráficos y mapas. Todos los "
    "gráficos de la aplicación son interactivos: muestran el valor al pasar el cursor y permiten acercar y "
    "descargar la imagen."
)

# =============================================================================
st.header("4.1 Selección de los tipos de gráfico", anchor="actividad-4-1")
st.markdown(
    """
Cada tipo de gráfico se eligió según el tipo de variable y la pregunta del análisis, con estos criterios
generales:

- **Comparar con la posición y la longitud antes que con el ángulo o el área.** Por eso se prefieren las
  barras a los gráficos circulares.
- **Un solo eje vertical por gráfico.**
- **Color por función:** un tono secuencial para magnitudes, dos tonos opuestos con un punto medio neutro para
  variaciones con signo, y un color fijo por grupo de delito en toda la aplicación.
- **Paleta validada para daltonismo.**
- **Título numerado y fuente en cada figura.**
"""
)
tabla_figura(eda.seleccion_graficos(), "seleccion_graficos")

# =============================================================================
st.header("4.2 Gráficos y mapas de concentración", anchor="actividad-4-2")
aviso_filtros_activos(activos)
n_fig = {k: figura(k)[0] for k in ["serie_mensual", "heat_mes_anio", "heat_dia_mes", "comunas", "box_diario"]}
st.markdown(
    f"""
Las series de tiempo, los gráficos de barras, los mapas de calor, los diagramas de caja, los histogramas y los
gráficos de dispersión de las páginas *Limpieza* y *Análisis exploratorio* forman el conjunto de
visualizaciones del proyecto. Algunos ejemplos son la serie mensual (Figura {n_fig["serie_mensual"]}), los
mapas de calor (Figuras {n_fig["heat_mes_anio"]} y {n_fig["heat_dia_mes"]}), las barras por comuna
(Figura {n_fig["comunas"]}) y los diagramas de caja (Figura {n_fig["box_diario"]}).

Esta sección añade los **mapas de concentración por zona**. Son mapas de densidad calculados solo con los
registros que tienen coordenada válida; la densidad se usa en lugar de los puntos porque con más de 120.000
hechos un mapa de puntos se satura. Los mapas responden a los filtros de la barra lateral.
"""
)
if df.latitud.notna().sum() < 20:
    st.caption("La selección no tiene suficientes registros con coordenadas para el mapa.")
else:
    grafico_figura(eda.fig_mapa_densidad(df), "mapa_densidad")
    fig_g = eda.fig_mapas_grupos(df)
    if fig_g is not None:
        grafico_figura(fig_g, "mapa_grupos")
sexuales = datos[datos.grupo_delito == "DELITOS SEXUALES"]
st.markdown(
    f"""
**Ubicaciones que la fuente no publica.** Ninguno de los {fmt_int(len(sexuales))} registros de delitos sexuales
del conjunto limpio tiene coordenadas: en el original, todos traen el marcador `xx.xxxx`. Estos registros son el
{fmt_pct(100 * len(sexuales) / datos.latitud.isna().sum())} de las ubicaciones faltantes, así que el faltante de
coordenadas no es aleatorio. Lo más probable es que la fuente omita la ubicación para proteger a las víctimas.
Por eso los delitos sexuales no aparecen en los mapas, y su distribución espacial solo puede analizarse por
barrio y comuna.
"""
)

st.subheader("Tablero en Power BI")
st.markdown(
    """
El tablero final se construye en Power BI Desktop, conectado a Neon mediante cinco vistas que forman un modelo
en estrella: `vw_fact_delitos` con las dimensiones de tiempo, territorio, conducta y víctima. La conexión usa
un rol de solo lectura y no guarda credenciales en el archivo. La guía completa está en `docs/powerbi_guia.md`,
con la conexión, el modelo, las medidas DAX (total, variación % anual, % de hurto, % de «SIN DATO» y
participación de la comuna con más casos), los indicadores, los segmentadores y las cifras de referencia.
"""
)
sql = (SQL_DIR / "03_vistas_powerbi.sql").read_text(encoding="utf-8")
vista_hechos = re.search(r"CREATE OR REPLACE VIEW vw_fact_delitos AS.*?;", sql, re.S).group(0)
with st.container(key="figura_sql_vistas"):
    titulo("sql_vistas")
    st.code(vista_hechos, language="sql")
    fuente()

# =============================================================================
st.header("4.3 Interpretación de los patrones", anchor="actividad-4-3")
st.markdown(
    "Cada hallazgo se presenta con su cifra principal y su evidencia gráfica, calculadas con el **conjunto "
    "limpio completo** (los filtros de la barra lateral no se aplican en esta sección). Debajo de cada "
    "hallazgo hay un espacio para el **contraste con los antecedentes**, que se guarda en "
    "`docs/contraste_antecedentes.md`."
)


def leer_contraste() -> dict[str, str]:
    if not RUTA_CONTRASTE.exists():
        return {}
    texto = RUTA_CONTRASTE.read_text(encoding="utf-8")
    partes = re.split(r"^## (H\d+) · .*$", texto, flags=re.M)
    return {partes[i]: partes[i + 1].strip() for i in range(1, len(partes) - 1, 2)}


def guardar_contraste(hid: str, nuevo: str) -> None:
    texto = RUTA_CONTRASTE.read_text(encoding="utf-8")
    # [^\n]* (y no .*) para que el encabezado no abarque varias líneas con re.S
    patron = re.compile(rf"(^## {hid} · [^\n]*\n)(.*?)(?=^## H\d+ · |\Z)", re.M | re.S)
    texto = patron.sub(lambda m: m.group(1) + "\n" + nuevo.strip() + "\n\n", texto, count=1)
    RUTA_CONTRASTE.write_text(texto, encoding="utf-8")


completo = datos
conc = eda.concentracion(completo)
anual_g = eda.serie_anual(completo)
c2020 = eda.cambio_2020(completo).set_index("Grupo")
gen = eda.contingencia(completo, "genero")["fila_pct"]
cur = eda.contingencia(completo, "curso_vida")["fila_pct"]
dsem = eda.por_dia_semana(completo).set_index("Día")
mens = eda.serie_mensual(completo)
total_anual = completo.groupby("anio").size()
lim = cargar_limpieza()
dpm = lim["duplicados_por_mes"]
pct_hurto = 100 * (completo.grupo_delito == "HURTO").mean()
menores_sex = cur.loc["DELITOS SEXUALES", ["01. PRIMERA INFANCIA", "02. INFANCIA", "03. ADOLESCENCIA"]].sum()
abril = int(mens.loc[mens.mes == "2020-04-01", "delitos"].iloc[0])

HALLAZGOS = [
    {
        "id": "H1", "titulo": "Concentración espacial del hurto",
        "cifra": ("Barrios que concentran el 50 % de los hurtos",
                  f"{conc['barrios_50']} de {conc['barrios']} ({fmt_pct(conc['pct_barrios_50'])})"),
        "figura": lambda: eda.fig_concentracion(completo),
        "clave": "concentracion_hurto",
        "texto": f"El hurto está muy concentrado: el índice de Gini entre barrios es de {fmt_dec(conc['gini'])}, y "
                 f"Centro, Cabecera del Llano, San Francisco, La Concordia y San Alonso encabezan la lista. Esta "
                 f"concentración sugiere que la prevención focalizada en pocos barrios abarcaría una parte "
                 f"importante del problema. La comparación con la población o la actividad comercial de cada "
                 f"barrio queda fuera de este conjunto de datos.",
    },
    {
        "id": "H2", "titulo": "Predominio y crecimiento del hurto",
        "cifra": ("Participación del hurto en los registros", fmt_pct(pct_hurto)),
        "figura": lambda: eda.fig_serie_anual(completo),
        "clave": "serie_anual",
        "texto": f"El hurto es casi la mitad de los registros y es el grupo que más creció: pasó de "
                 f"{fmt_int(anual_g.loc[2010, 'HURTO'])} registros en 2010 a {fmt_int(anual_g.loc[2018, 'HURTO'])} "
                 f"en 2018 ({fmt_pct(100 * (anual_g.loc[2018, 'HURTO'] / anual_g.loc[2010, 'HURTO'] - 1))} más). "
                 f"Tras la caída de 2020 se recuperó a {fmt_int(anual_g.loc[2021, 'HURTO'])} en 2021.",
    },
    {
        "id": "H3", "titulo": "Perfil de género según el tipo de delito",
        "cifra": ("Mujeres entre las víctimas de violencia intrafamiliar",
                  fmt_pct(gen.loc["VIOLENCIA INTRAFAMILIAR", "FEMENINO"])),
        "figura": lambda: eda.fig_contingencia(completo, "genero", "cont_genero"),
        "clave": "cont_genero",
        "texto": f"La asociación entre el delito y el género de la víctima es moderada (V de Cramér = "
                 f"{fmt_dec(eda.contingencia(completo, 'genero')['v_cramer'], 3)}). Las mujeres son la mayoría "
                 f"de las víctimas de violencia intrafamiliar ({fmt_pct(gen.loc['VIOLENCIA INTRAFAMILIAR', 'FEMENINO'])}) "
                 f"y de delitos sexuales ({fmt_pct(gen.loc['DELITOS SEXUALES', 'FEMENINO'])}). Los hombres "
                 f"predominan en el homicidio ({fmt_pct(gen.loc['HOMICIDIO', 'MASCULINO'])}) y, en menor medida, "
                 f"en el hurto ({fmt_pct(gen.loc['HURTO', 'MASCULINO'])}).",
    },
    {
        "id": "H4", "titulo": "Violencia sexual contra niños, niñas y adolescentes",
        "cifra": ("Víctimas de delitos sexuales menores de 18 años", fmt_pct(menores_sex)),
        "figura": lambda: eda.fig_contingencia(completo, "curso_vida", "cont_curso"),
        "clave": "cont_curso",
        "texto": f"Es el único grupo de delito cuyas víctimas son mayoritariamente menores de edad: primera "
                 f"infancia {fmt_pct(cur.loc['DELITOS SEXUALES', '01. PRIMERA INFANCIA'])}, infancia "
                 f"{fmt_pct(cur.loc['DELITOS SEXUALES', '02. INFANCIA'])} y adolescencia "
                 f"{fmt_pct(cur.loc['DELITOS SEXUALES', '03. ADOLESCENCIA'])}. En los demás grupos predominan los "
                 f"adultos y los jóvenes.",
    },
    {
        "id": "H5", "titulo": "Caída de 2020 y recuperación de 2021",
        "cifra": ("Variación de 2020 frente al promedio 2017–2019",
                  fmt_pct(c2020.loc["Total", "Variación vs promedio 2017–2019 (%)"]).replace("-", "−")),
        "figura": lambda: eda.fig_serie_mensual(completo),
        "clave": "serie_mensual",
        "texto": f"Abril de 2020 tiene el mínimo de toda la serie ({fmt_int(abril)} registros), en coincidencia "
                 f"con la cuarentena. En 2021 los registros aumentaron un "
                 f"{fmt_pct(100 * (total_anual[2021] / total_anual[2020] - 1))} frente a 2020. Sin embargo, la "
                 f"violencia intrafamiliar y los delitos sexuales ya venían bajando en 2019, y los homicidios "
                 f"aumentaron en 2020 ({fmt_int(anual_g.loc[2020, 'HOMICIDIO'])} frente a un promedio de "
                 f"{fmt_int(round(c2020.loc['Homicidio', 'Promedio 2017–2019']))}). Por eso el cambio no se "
                 f"explica solo por la pandemia.",
    },
    {
        "id": "H6", "titulo": "Mayor ocurrencia los sábados",
        "cifra": ("Registros en sábado", f"{fmt_pct(dsem.loc['Sábado', '%'])} "
                                         f"(+{fmt_dec(dsem.loc['Sábado', 'Índice (100 = promedio)'] - 100, 1)} % sobre el promedio)"),
        "figura": lambda: eda.fig_dia_semana(completo),
        "clave": "dia_semana",
        "texto": "El sábado es el único día claramente por encima del promedio; los demás días son parejos. El mapa "
                 "de calor de día de la semana y mes muestra el mismo patrón en casi todos los meses.",
    },
    {
        "id": "H7", "titulo": "La calidad del registro condiciona la lectura de las tendencias",
        "cifra": ("Duplicados eliminados en diciembre de 2019",
                  f"{fmt_int(dpm.iloc[0].duplicados)} de {fmt_int(dpm.iloc[0].original)} "
                  f"({fmt_pct(dpm.iloc[0]['% duplicado'])})"),
        "figura": lambda: diagnostico.fig_duplicados_anio(cargar_diagnostico()),
        "clave": "duplicados_anio",
        "texto": "Los errores de carga se concentran en 2019–2021: duplicados, coordenadas intercambiadas y días de "
                 "la semana errados. A esto se suman quiebres bruscos en algunas series (lesiones en tránsito en "
                 "2017, delitos sexuales en 2019) y cinco días sin ningún registro en marzo de 2019. Sin la limpieza, "
                 "los picos de fin de 2019 se habrían interpretado como aumentos reales. Las tendencias de los "
                 "últimos años deben leerse como tendencias del registro, no necesariamente de la ocurrencia.",
    },
]

contraste = leer_contraste()
for i, h in enumerate(HALLAZGOS):
    with st.container(border=True, key="figura_hallazgos" if i == 0 else f"hallazgo_{h['id']}"):
        if i == 0:
            titulo("hallazgos")
        st.subheader(f"{h['id']} · {h['titulo']}")
        st.metric(h["cifra"][0], h["cifra"][1])
        st.markdown(h["texto"])
        st.plotly_chart(h["figura"](), width="stretch", config={"displaylogo": False},
                        key=f"fig_{h['id']}")
        st.caption(f"Evidencia: Figura {figura(h['clave'])[0]}.")
        actual = contraste.get(h["id"], "")
        pendiente = actual.startswith("[ESCRIBA")
        st.markdown("**Contraste con los antecedentes**")
        if pendiente or not actual:
            st.caption("Pendiente: escriba el contraste con los antecedentes.")
        else:
            st.markdown(actual)
        if i == 0:
            fuente()
    with st.expander(f"Editar el contraste de {h['id']}"):
        nuevo = st.text_area("Texto", "" if pendiente else actual, height=150, key=f"txt_{h['id']}",
                             label_visibility="collapsed")
        if st.button("Guardar", key=f"guardar_{h['id']}"):
            guardar_contraste(h["id"], nuevo or "[ESCRIBA AQUÍ EL CONTRASTE CON LOS ANTECEDENTES]")
            st.success("Guardado en docs/contraste_antecedentes.md")
            st.rerun()
