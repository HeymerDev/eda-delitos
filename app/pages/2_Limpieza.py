"""Limpieza y preparación de los datos (objetivo 2)."""
import inspect

import streamlit as st

from comun import (
    aviso_filtros_no_aplican,
    cargar_eliminados,
    cargar_limpieza,
    cargar_limpios,
    configurar_pagina,
    grafico_figura,
    tabla_estatica,
    tabla_figura,
    titulo,
    fuente,
)
from src import utils
from src.cleaning import (
    K_IQR,
    Z_ROBUSTO,
    fig_box_barrio,
    fig_box_diario,
    fig_coord_antes,
    fig_coord_despues,
)
from src.utils import TOTAL_REGISTROS, fmt_int, fmt_pct

configurar_pagina("Limpieza")
aviso_filtros_no_aplican()

r = cargar_limpieza()
limpios, origen = cargar_limpios()
elim = cargar_eliminados()
k, a, val = r["conteos"], r["atipicos"], r["validacion"]

st.title("Limpieza y preparación de los datos")
st.markdown(
    "**Objetivo 2.** Limpiar y preparar los datos mediante el tratamiento de valores nulos y atípicos. "
    "La limpieza produce un **conjunto de datos nuevo** (`delitos_limpios`); el original no se modifica. "
    f"Cada registro excluido queda en `delitos_eliminados` con su motivo. Datos mostrados: {origen}."
)

m = st.columns(4)
m[0].metric("Registros originales", fmt_int(TOTAL_REGISTROS))
m[1].metric("Registros limpios", fmt_int(len(limpios)), f"−{fmt_int(len(elim))}", delta_color="off")
m[2].metric("Eliminados", fmt_int(len(elim)), fmt_pct(100 * len(elim) / TOTAL_REGISTROS), delta_color="off")
m[3].metric("Pruebas de validación superadas", f"{(val.Resultado == 'OK').sum()} de {len(val)}")

# =============================================================================
st.header("Comparación antes y después", anchor="antes-despues")
st.markdown(
    f"Del conjunto original se eliminaron **{fmt_int(len(elim))} registros** "
    f"({fmt_pct(100 * len(elim) / TOTAL_REGISTROS)}): {fmt_int(k['fuera_municipio'])} asignados a otro municipio y "
    f"{fmt_int(k['duplicados'])} duplicados exactos. No hubo eliminaciones por errores irrecuperables: el único error "
    "imposible de corregir (una coordenada en Bogotá) se trató anulando la coordenada, no el registro."
)
tabla_figura(r["antes_despues"], "antes_despues")
with st.expander("Ver los registros eliminados y su motivo"):
    st.dataframe(elim, hide_index=True, width="stretch")
    st.download_button("Descargar delitos_eliminados (CSV)", elim.to_csv(index=False).encode("utf-8"),
                       file_name="delitos_eliminados.csv", mime="text/csv")

st.header("Tabla de decisiones", anchor="decisiones")
st.markdown("Cada decisión de limpieza con su actividad, los registros afectados y su justificación. "
            "La misma tabla está en `docs/decisiones_limpieza.md`.")
tabla_figura(r["decisiones"], "decisiones")

# =============================================================================
st.header("2.1 Corrección de formato y eliminación de duplicados e inconsistentes", anchor="actividad-2-1")
f = r["formato"]
st.markdown(
    f"""
- **Texto:** se normalizaron las 12 variables categóricas: mayúsculas, sin tildes (se conserva la Ñ), sin
  espacios dobles ni espacios junto a paréntesis. Cambiaron {fmt_int(f["texto_modificado"])} celdas.
- **Variantes:** se unificaron las variantes del mismo valor: «QUINTADANIA» pasa a «QUINTA DANIA» y las dos
  descripciones alternativas de abigeato y de lesiones en tránsito pasan a la forma con artículo.
- **Fechas:** el mes pasó de texto («01. ENERO») a número y se construyó `fecha_hecho`. El día de la semana se
  recalculó a partir de la fecha, lo que corrigió {fmt_int(int(limpios.flag_dia_semana_corregido.sum()))} registros
  de agosto de 2020.
- **Coordenadas:** se reconstruyeron con la función de la Figura {utils.figura("codigo_coordenadas")[0]}.
  {fmt_int(f["coordenadas"].get("intercambiada", 0))} pares venían intercambiados y
  {f["coordenadas"].get("signo", 0)} sin signo; se corrigieron y se marcaron con `flag_coord_corregida`.
- **Eliminaciones aprobadas:** {fmt_int(k["fuera_municipio"])} registros de otros municipios (E1) y
  {fmt_int(k["duplicados"])} duplicados exactos en {fmt_int(k["grupos_duplicados"])} grupos (E2). En cada grupo de
  duplicados se conservó el `ORDEN` menor.
"""
)
with st.container(key="figura_codigo_coordenadas"):
    titulo("codigo_coordenadas")
    st.code(inspect.getsource(utils.reconstruir_coordenada), language="python")
    fuente()

st.markdown(
    "La Figura siguiente muestra el efecto de corregir los intercambios: con solo la reconstrucción decimal, "
    "los 956 registros cruzados de 2020 quedan a miles de kilómetros (longitud +71°, latitud −7°)."
)
grafico_figura(fig_coord_antes(r), "coord_antes")
grafico_figura(fig_coord_despues(limpios), "coord_despues")

# =============================================================================
st.header("2.2 Tratamiento de los valores nulos", anchor="actividad-2-2")
st.markdown(
    """
La técnica se eligió según el tipo de variable:

- **Variables categóricas:** se recodificaron los marcadores de faltante («NO REPORTA», «NO REPORTADO»,
  «SIN INFORMACION», «ERROR: #N/A») como la categoría **«SIN DATO»**. No se imputó la moda: asignar «MASCULINO»
  o «SOLTERO» a miles de víctimas inventaría un perfil y sesgaría las tablas de contingencia del objetivo 3.
  Con «SIN DATO» se conserva el registro, cuyas demás columnas son válidas, y la magnitud del faltante queda
  visible en cada análisis.
- **Coordenadas:** las inexistentes o irrecuperables quedan como **valor nulo** con su aviso
  (`flag_coord_faltante`, `flag_coord_fuera_area`). Una ubicación no puede imputarse sin inventar el lugar del
  hecho. Estos registros se usan en todos los análisis excepto en los mapas.
"""
)
tabla_figura(r["faltantes"], "faltantes_tratamiento")

# =============================================================================
st.header("2.3 Detección y tratamiento de atípicos, y validación", anchor="actividad-2-3")
diario, barrios = a["diario"], a["barrios"]
dpm = r["duplicados_por_mes"]
d1 = a["dia_1"]
st.markdown(
    f"""
**Qué es un atípico en datos de conteo.** Las variables del conjunto son categóricas: las únicas magnitudes son
los conteos que resultan de agregar los registros, como los delitos por día o por barrio. En un conteo, un
atípico no es un dato mal digitado sino un **periodo o un lugar con muchos más delitos de lo habitual**. Puede
deberse a un fenómeno real (fiestas, eventos, focos de criminalidad) o a la forma de registro (cargas
masivas, fechas por defecto). Por eso los atípicos **se marcan con avisos y no se eliminan**: borrarlos
subestimaría justamente los momentos y lugares de mayor riesgo.

**Método.** Se usaron dos criterios y se marca un valor solo si ambos coinciden:

- **Límite de Tukey:** el valor supera Q3 + {K_IQR}·IQR.
- **z robusto** (Iglewicz y Hoaglin): z = (x − mediana) / (1,4826·MAD) mayor que {Z_ROBUSTO}. A diferencia
  de la media y la desviación estándar, la mediana y la MAD no se distorsionan por los mismos extremos que se
  quiere detectar.
"""
)
st.subheader("Conteo diario")
st.markdown(
    f"""
Los umbrales se calcularon dentro de cada año, porque el nivel general cambia entre años (por ejemplo, la
caída de 2020).

- **Días atípicos:** {int(diario.atipico.sum())} días de {fmt_int(len(diario))} superan ambos criterios
  (marcados en rojo). Agrupan {fmt_int(int(limpios.flag_dia_atipico.sum()))} registros con `flag_dia_atipico`.
- **Fechas:** {a["dias_atipicos_1_enero"]} de ellos son un 1 de enero; los demás son sobre todo fines de semana
  y festivos.
- **Efecto de los duplicados:** antes de eliminarlos, los días de diciembre de 2019 eran los más atípicos de la
  serie. Ese mes pasó de {fmt_int(dpm.iloc[0].original)} a {fmt_int(dpm.iloc[0].limpio)} registros
  ({fmt_pct(dpm.iloc[0]["% duplicado"])} eran duplicados).
- **Días sin registros:** {len(a["dias_cero"])} días seguidos no tienen ningún delito
  ({a["dias_cero"][0].strftime("%d/%m/%Y")} a {a["dias_cero"][-1].strftime("%d/%m/%Y")}). Con una media de unos
  30 delitos diarios, lo más probable es un hueco en la carga de datos; se documenta como limitación.
- **Día 1 del mes:** tiene {fmt_int(d1["registros"])} registros, frente a una media de
  {fmt_int(round(d1["media_dias_2_28"]))} en los días 2 a 28. El exceso podría deberse a fechas registradas por
  defecto. No es identificable registro a registro, así que se documenta como limitación.
"""
)
grafico_figura(fig_box_diario(r), "box_diario")
with st.expander("Días atípicos"):
    tabla_estatica(diario[diario.atipico].sort_values("delitos", ascending=False)
                   .assign(fecha=lambda d: d.fecha.dt.strftime("%d/%m/%Y"))
                   [["fecha", "delitos", "limite_iqr", "z_robusto"]])

st.subheader("Conteo por barrio")
st.markdown(
    f"""
- **Asimetría:** la distribución es muy asimétrica. La mediana es de {fmt_int(barrios.delitos.median())} delitos
  por barrio y CENTRO tiene {fmt_int(barrios.delitos.max())}.
- **Escala lineal:** {int(barrios.atipico.sum())} barrios superan ambos criterios y concentran
  {fmt_int(int(limpios.flag_barrio_atipico.sum()))} registros
  ({fmt_pct(100 * limpios.flag_barrio_atipico.mean())}). Se marcan con `flag_barrio_atipico`.
- **Escala logarítmica:** ningún barrio es atípico (z robusto máximo = {barrios.z_robusto_log.max():.2f}).
  Es decir, no hay valores imposibles sino una cola larga.
- **Lectura:** los barrios marcados se interpretan como focos de concentración, un hallazgo que se analiza en el
  objetivo 3, y no como errores.
"""
)
grafico_figura(fig_box_barrio(r), "box_barrio")
with st.expander("Barrios marcados"):
    tabla_estatica(barrios[barrios.atipico][["barrio", "delitos", "z_robusto", "z_robusto_log"]])

st.subheader("Inconsistencias marcadas")
st.markdown(
    f"""
- **`flag_barrio_comuna`:** {fmt_int(int(limpios.flag_barrio_comuna.sum()))} registros cuya comuna no es la habitual
  de su barrio. No se corrigen con la moda porque no se sabe cuál de las dos columnas tiene el error.
- **`flag_curso_vida_estado_civil`:** {int(limpios.flag_curso_vida_estado_civil.sum())} registros de primera
  infancia o infancia con estado civil de adulto.
- **`flag_coord_fuera_area`:** {int(limpios.flag_coord_fuera_area.sum())} coordenada fuera del área de Bucaramanga,
  anulada.
"""
)

st.subheader("Validación del conjunto limpio")
st.markdown(
    "El conjunto resultante se validó con estas pruebas: conteos que cuadran con el original, ausencia de "
    "duplicados según el criterio aprobado, ausencia de marcadores de faltante, tipos de dato, coherencia de "
    "la fecha, rangos de las coordenadas y categorías permitidas. Son las mismas restricciones que impone el "
    "esquema de `delitos_limpios` en PostgreSQL."
)
tabla_figura(val, "validacion")
