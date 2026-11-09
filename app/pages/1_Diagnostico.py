"""Diagnóstico de calidad del conjunto original (objetivo 1)."""
import numpy as np
import streamlit as st

from comun import (
    aviso_filtros_no_aplican,
    cargar_diagnostico,
    configurar_pagina,
    fuente,
    grafico_figura,
    tabla_estatica,
    tabla_figura,
    titulo,
)
from src.diagnostico import (
    RUTA_INFORME,
    fig_coord_formatos,
    fig_duplicados_anio,
    fig_faltantes,
    informe_markdown,
)
from src.utils import TOTAL_REGISTROS, fmt_int, fmt_pct

configurar_pagina("Diagnóstico")
aviso_filtros_no_aplican()

r = cargar_diagnostico()
f, d, c, fe, inc = r["faltantes"], r["duplicados"], r["coordenadas"], r["fechas"], r["inconsistencias"]

st.title("Diagnóstico de calidad del conjunto de datos")
st.markdown(
    "**Objetivo 1.** Diagnosticar la calidad del conjunto de datos de delitos de Bucaramanga. "
    "El diagnóstico se hace sobre el **original sin modificar**: solo se describe lo que hay; las "
    "correcciones se hacen en la página *Limpieza*, sobre un dataset nuevo."
)

m = st.columns(5)
m[0].metric("Registros", fmt_int(r["filas"]))
m[1].metric("Variables", r["columnas"])
m[2].metric("Registros con algún faltante", fmt_pct(100 * f["filas_con_alguno"] / TOTAL_REGISTROS))
m[3].metric("Duplicados sobrantes (sin ORDEN)", fmt_int(d["sobrantes"]))
m[4].metric("Registros sin coordenadas", fmt_int(c["faltantes"]))

# =============================================================================
st.header("1.1 Estructura del conjunto de datos", anchor="actividad-1-1")
st.markdown(
    f"""
El conjunto tiene **{fmt_int(r["filas"])} registros** y **{r["columnas"]} variables** en una sola hoja
(`{r["hojas"][0]}`), con hechos del {fe["fecha_min"]} al {fe["fecha_max"]}. `ORDEN` es un identificador único
del 1 al {fmt_int(fe["orden_rango"][1])}, sin huecos y en orden cronológico.

El xlsx guarda **todas las celdas como texto**. Al leerlo, solo `ORDEN`, `ANO` y `DIA` pueden interpretarse
como enteros. Las coordenadas, que son numéricas, no pueden convertirse directamente por su formato.
Dieciséis de las diecinueve variables son categóricas.
"""
)
tabla_figura(r["estructura"], "estructura", height=36 * (len(r["estructura"]) + 1) + 4)

# =============================================================================
st.header("1.2 Valores nulos, duplicados, errores de formato e inconsistencias", anchor="actividad-1-2")

# ---- Faltantes
st.subheader("Valores nulos y marcadores de faltante")
st.markdown(
    f"No hay valores nulos ({f['nulos']}) ni celdas vacías ({f['vacias']}): los faltantes están escritos como "
    f"texto, con un marcador distinto según la variable. **{fmt_int(f['filas_con_alguno'])} registros** "
    f"({fmt_pct(100 * f['filas_con_alguno'] / TOTAL_REGISTROS)}) tienen al menos un marcador. Las variables "
    f"de la víctima son las más afectadas."
)
grafico_figura(fig_faltantes(r), "faltantes")
st.caption("Marcadores encontrados: «NO REPORTA», «NO REPORTADO» (ARMAS_MEDIOS), «SIN INFORMACION», "
           "«ERROR: #N/A» (CURSO_DE_VIDA) y «xx.xxxx» / «-yy.yyyy» (coordenadas).")
with st.expander("Detalle por variable y marcador"):
    st.dataframe(f["detalle"], hide_index=True, width="stretch")

# ---- Duplicados
st.subheader("Registros duplicados")
esperado = np.mean(d["esperado_azar"])
st.markdown(
    f"""
- **Duplicados completos: {d["completos"]}.** `ORDEN` es distinto en todas las filas.
- **Duplicados sin `ORDEN`:** {fmt_int(d["filas_en_grupos"])} registros forman {fmt_int(d["n_grupos"])} grupos
  de filas idénticas en las otras 18 columnas. Si se conserva uno por grupo, **sobran {fmt_int(d["sobrantes"])}
  ({fmt_pct(100 * d["sobrantes"] / TOTAL_REGISTROS)})**.
- **No son coincidencias.** Al permutar al azar el día dentro de cada mes, lo que conserva las frecuencias y
  rompe cualquier relación real entre registros, se esperan {min(d["esperado_azar"])}–{max(d["esperado_azar"])}
  duplicados. Se observan **{d["sobrantes"] / esperado:.0f} veces más** (Figura 6).
- **Se concentran en 2019–2021,** donde pasan del 1–3 % al 6,5–8,8 % del año. Son los mismos años con
  coordenadas intercambiadas y días de la semana errados, lo que apunta a errores de carga.
- **Coinciden incluso en el perfil de la víctima.** En cambio, {fmt_int(d["comparten_hecho"])} registros
  comparten el hecho con víctimas distintas, lo esperable en hechos con varias víctimas.
- **Limitación:** sin hora ni identificador de víctima no se puede descartar que algunos grupos sean
  víctimas distintas con el mismo perfil, sobre todo en lesiones de tránsito.

**Decisión aprobada:** eliminar los sobrantes solo en el dataset limpio, conservando el `ORDEN` menor de cada
grupo y registrando cada eliminación en `delitos_eliminados`. El original no se modifica.
"""
)
grafico_figura(fig_duplicados_anio(r), "duplicados_anio")

st.markdown("Cuatro grupos de duplicados elegidos al azar. Las filas de un mismo grupo coinciden en las 18 "
            "columnas y solo difieren en `ORDEN`. Por espacio se muestran 12 de ellas; la tabla completa está "
            "debajo.")
cols_muestra = ["Grupo", "ORDEN", "ANO", "MES", "DIA", "BARRIOS_HECHO", "LATITUD", "CONDUCTA", "ARMAS_MEDIOS",
                "CURSO_DE_VIDA", "ESTADO_CIVIL_PERSONA", "GENERO"]
tabla_figura(d["muestra"][cols_muestra], "duplicados_muestra")
with st.expander("Ver los grupos con todas las columnas"):
    st.dataframe(d["muestra"], hide_index=True, width="stretch")
cA, cB = st.columns(2)
with cA:
    st.markdown("**Tamaño de los grupos**")
    st.dataframe(d["tamanos"].rename_axis("Filas por grupo").reset_index(name="Grupos"), hide_index=True)
with cB:
    st.markdown("**Conductas con más duplicados sobrantes**")
    st.dataframe(d["por_conducta"].head(10), hide_index=True)

# ---- Coordenadas
st.subheader("Formato de las coordenadas")
st.markdown(
    f"""
`LATITUD` y `LONGITUD` son números guardados como texto, con **{c["n_formatos_lat"]} y {c["n_formatos_lon"]}
formatos distintos**. La mayoría usa comas como separador de miles en posiciones arbitrarias: por ejemplo,
`7,170,557,382` significa 7,170557382. Otros registros usan punto decimal.

- **Sin coordenadas:** {fmt_int(c["faltantes"])} registros con los marcadores `xx.xxxx` / `-yy.yyyy`.
- **Intercambiadas:** {fmt_int(c["intercambiadas"])} registros, todos de 2020, con la longitud en `LATITUD`.
- **Sin signo:** {len(c["sin_signo"])} longitud sin el signo negativo.
- **Recuperables:** con la regla de reconstrucción (solo dígitos, con el punto decimal tras el primer dígito
  en la latitud y tras dos en la longitud) se recuperan **{fmt_int(c["recuperables"])} coordenadas** dentro
  del área de Bucaramanga.
- **Irrecuperables:** {len(c["fuera_area"])} registro cae fuera del área (en Bogotá).
"""
)
grafico_figura(fig_coord_formatos(r), "coord_formatos")
with st.expander("Ejemplos de reconstrucción por tipo de caso"):
    st.dataframe(c["muestra"].rename(columns={"lat": "latitud reconstruida", "lon": "longitud reconstruida"}),
                 hide_index=True, width="stretch")

# ---- Fechas
st.subheader("Rangos y fechas")
st.markdown(
    f"""
- **Rangos válidos:** `ANO` va de {fe["anio"][0]} a {fe["anio"][1]} y `DIA` de {fe["dia"][0]} a {fe["dia"][1]}.
  `MES` tiene {len(fe["meses"])} valores con número y nombre coherentes.
- **Fechas imposibles** (como un 31 de febrero): **{fe["fechas_imposibles"]}**.
- **Días de la semana errados:** **{fmt_int(fe["dia_semana_errado"])} registros** tienen un `DIA_SEMANA` que no
  corresponde a su fecha. Todos son de agosto de 2020, donde afectan al
  {fmt_pct(fe["dia_semana_por_mes"]["% del mes"].iloc[0])} del mes.
"""
)
st.dataframe(fe["dia_semana_muestra"], hide_index=True)

# ---- Inconsistencias
st.subheader("Inconsistencias entre columnas")
fuera = inc["fuera_municipio"]
st.markdown(
    f"""
- **Otros municipios:** {fmt_int(fuera.Registros.sum())} registros asignan el hecho a otro municipio
  ({", ".join(f"{m.title()} {n}" for m, n in zip(fuera.Municipio, fuera.Registros))}).
- **Barrio y comuna:** {inc["barrios_multicomuna"]} barrios aparecen en más de una comuna, y
  {fmt_int(inc["filas_comuna_no_modal"])} registros tienen una comuna distinta de la habitual de su barrio.
- **Curso de vida y estado civil:** {len(inc["curso_estado_imposible"])} niños de primera infancia o infancia
  figuran como casados, en unión libre o viudos.
- **Conducta y descripción:** dos conductas tienen una descripción alternativa en
  {inc["conducta_descripcion_minoritaria"]} registros. Además, la fuente clasifica los hurtos como
  'LESIONES NO FATALES' ({fmt_int(inc["hurtos_lesiones_no_fatales"])} registros), una particularidad de su
  taxonomía que se documenta sin modificar.
- **Variantes de escritura:** valores escritos de dos formas (`QUINTADANIA` y `QUINTA DANIA`), espacios dobles
  y palabras con y sin tilde ({"; ".join(inc["tildes_mixtas"])}).
"""
)
resumen_inc = r["resumen"][r["resumen"].Tipo.isin(["Formato", "Inconsistencia", "Rango"])]
tabla_figura(resumen_inc, "inconsistencias")
with st.expander("Detalle de cada inconsistencia"):
    st.markdown("**Registros asignados a otros municipios**")
    st.dataframe(fuera, hide_index=True)
    st.markdown("**Barrios registrados en varias comunas** (comunas ordenadas de más a menos registros)")
    st.dataframe(inc["ejemplos_barrio_comuna"], hide_index=True, width="stretch")
    st.markdown("**Curso de vida frente a estado civil**")
    st.dataframe(inc["curso_estado"], width="stretch")
    st.markdown("**Conducta con dos descripciones**")
    st.dataframe(inc["conducta_descripcion"], hide_index=True, width="stretch")
    st.markdown("**Medios de transporte poco plausibles en Bucaramanga** (probablemente Metrolínea en el caso del metro)")
    st.dataframe(inc["moviles_raros"], hide_index=True)
    st.markdown("**Variantes de escritura**")
    st.dataframe(inc["variantes"], hide_index=True, width="stretch")

# =============================================================================
st.header("1.3 Informe de diagnóstico", anchor="actividad-1-3")
st.markdown(
    "Los problemas encontrados se documentan en un informe de diagnóstico. El informe incluye el tratamiento "
    "propuesto para cada problema, que se aplica en la fase de limpieza. Se regenera con "
    "`python -m src.diagnostico` y se guarda en `docs/informe_diagnostico.md`."
)
informe = RUTA_INFORME.read_text(encoding="utf-8") if RUTA_INFORME.exists() else informe_markdown(r)
with st.container(key="figura_informe"):
    titulo("informe")
    tabla_estatica(r["resumen"])
    st.download_button("Descargar el informe de diagnóstico (Markdown)", informe,
                       file_name="informe_diagnostico.md", mime="text/markdown", type="primary")
    fuente()
with st.expander("Ver el informe completo"):
    st.markdown(informe)
