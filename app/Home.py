"""Inicio: contexto, objetivos, origen de los datos y cómo navegar."""
import streamlit as st

from comun import aviso_filtros_no_aplican, cargar_diagnostico, configurar_pagina
from src.utils import fmt_int

configurar_pagina("Inicio")
aviso_filtros_no_aplican()

st.title("Análisis exploratorio de los delitos ocurridos en Bucaramanga, Colombia (2010–2021)")
st.caption("Minería de Datos · Análisis exploratorio de datos (EDA) y visualización")

r = cargar_diagnostico()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Registros del conjunto original", fmt_int(r["filas"]))
c2.metric("Variables", r["columnas"])
c3.metric("Periodo", f"{r['fechas']['anio'][0]}–{r['fechas']['anio'][1]}")
c4.metric("Barrios distintos", fmt_int(r["estructura"].set_index("Variable").loc["BARRIOS_HECHO", "Valores distintos"]))

st.header("Contexto")
st.markdown(
    """
La Alcaldía de Bucaramanga publica en el portal de datos abiertos de Colombia el registro de los delitos
ocurridos en el municipio. Cada registro describe un hecho y a su víctima: la conducta (hurto, lesiones,
violencia intrafamiliar, delitos sexuales, homicidio…), el arma o medio empleado, el barrio y la comuna,
la fecha, y el curso de vida, estado civil y género de la víctima.

Este proyecto analiza esos registros para identificar **patrones delictivos en el espacio, en el tiempo
y en el perfil de las víctimas**. Es un trabajo exploratorio y descriptivo: no construye modelos predictivos.
"""
)

st.header("Objetivos")
st.markdown(
    f"""
**Objetivo general.** Analizar los {fmt_int(r["filas"])} registros de delitos ocurridos en Bucaramanga entre
2010 y 2021, publicados por la Alcaldía en datos abiertos, para identificar patrones delictivos en el espacio,
en el tiempo y en el perfil de las víctimas.

| Objetivo específico | Actividades | Página |
|---|---|---|
| 1. Diagnosticar la calidad del conjunto de datos de delitos de Bucaramanga. | 1.1 Estructura · 1.2 Nulos, duplicados, formato e inconsistencias · 1.3 Informe de diagnóstico | Diagnóstico |
| 2. Limpiar y preparar los datos mediante el tratamiento de valores nulos y atípicos. | 2.1 Formato, duplicados e inconsistentes · 2.2 Valores nulos · 2.3 Atípicos y validación | Limpieza |
| 3. Describir la distribución de los delitos en el espacio, en el tiempo y según el perfil de las víctimas. | 3.1 Estadísticas y frecuencias · 3.2 Zona y periodo · 3.3 Tablas de contingencia | Análisis exploratorio |
| 4. Visualizar los patrones delictivos identificados mediante gráficos y mapas. | 4.1 Selección de gráficos · 4.2 Gráficos y mapas · 4.3 Interpretación | Visualización y hallazgos |
"""
)

st.header("Origen de los datos")
st.markdown(
    """
| | |
|---|---|
| **Conjunto** | 40Delitos ocurridos en el Municipio de Bucaramanga |
| **Publicador** | Alcaldía de Bucaramanga, Santander |
| **Portal** | [datos.gov.co · 75fz-q98y](https://www.datos.gov.co/d/75fz-q98y) |
| **Publicación** | 16 de diciembre de 2023 |
| **Descarga** | 26 de octubre de 2026 (xlsx) |
| **Licencia** | Creative Commons Atribución-CompartirIgual 4.0 |

Los datos se almacenan en **PostgreSQL (Neon)** en tres tablas: `delitos_raw`, que es la copia fiel del
original y nunca se modifica; `delitos_limpios`, el dataset nuevo que produce la limpieza; y
`delitos_eliminados`, con cada registro excluido y su motivo.
"""
)

st.header("Cómo navegar")
st.markdown(
    """
Use el menú de la izquierda. Cada página corresponde a un objetivo específico y sus secciones siguen la
numeración de las actividades. Cada gráfico tiene un título numerado («Figura N») y su fuente, de modo que
puede citarse directamente en el artículo. En las páginas de análisis, la barra lateral tiene filtros de
rango de años, comuna, tipo de delito y género.
"""
)
