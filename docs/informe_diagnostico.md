# Informe de diagnóstico de calidad

**Conjunto:** 40Delitos ocurridos en el Municipio de Bucaramanga (datos.gov.co, `75fz-q98y`), Alcaldía de Bucaramanga (2023).  
**Archivo analizado:** `data/raw/40Delitos_ocurridos_en_el_Municipio_de_Bucaramanga_20261026.csv` (copia fiel del xlsx original).  
**Fecha del diagnóstico:** 2026-11-09. Generado con `python -m src.diagnostico`.

El diagnóstico solo lee los datos: no modifica el original. Las correcciones se aplican en la fase de limpieza sobre un dataset nuevo (`delitos_limpios`).

## Resumen de problemas encontrados

| Tipo | Problema | Variables | Registros | % del total | Tratamiento propuesto (fase) |
|---|---|---|---|---|---|
| Faltantes | Marcadores de dato faltante ('NO REPORTA', 'ERROR: #N/A', 'xx.xxxx', etc.) en lugar de nulos | 12 variables | 24.240 | 17,95 | Recodificar a la categoría 'SIN DATO' (2.2) |
| Faltantes | Valor de error de Excel 'ERROR: #N/A' en el curso de vida | CURSO_DE_VIDA | 940 | 0,70 | Recodificar a 'SIN DATO'; el resto del registro es válido (2.2) |
| Duplicados | Registros idénticos en todas las columnas salvo ORDEN (sobrantes) | 18 variables | 4.622 | 3,42 | Eliminar en el dataset limpio, conservar el ORDEN menor (2.1) |
| Formato | Coordenadas guardadas como texto con separadores de miles mal ubicados | LATITUD, LONGITUD | 124.191 | 91,94 | Reconstruir el valor decimal (2.1) |
| Formato | Latitud y longitud intercambiadas | LATITUD, LONGITUD | 956 | 0,71 | Intercambiar y reconstruir (2.1) |
| Formato | Longitud sin signo negativo | LONGITUD | 1 | 0,00 | Corregir el signo (2.1) |
| Rango | Coordenada fuera del área de Bucaramanga e irrecuperable | LATITUD, LONGITUD | 1 | 0,00 | Anular la coordenada y marcar con aviso (2.3) |
| Formato | Mes como texto con prefijo numérico ('01. ENERO') | MES | 135.076 | 100,00 | Convertir a número y construir fecha_hecho (2.1) |
| Inconsistencia | DIA_SEMANA no corresponde a la fecha | DIA_SEMANA | 577 | 0,43 | Recalcular desde la fecha (2.1) |
| Inconsistencia | Hecho asignado a otro municipio | NOM_COMUNA | 166 | 0,12 | Eliminar del dataset limpio: fuera del alcance (2.1) |
| Faltantes | Comuna 'SIN INFORMACION' | NOM_COMUNA | 45 | 0,03 | Recodificar a 'SIN DATO' (2.2) |
| Inconsistencia | Barrio registrado en una comuna distinta de la habitual | BARRIOS_HECHO, NOM_COMUNA | 1.359 | 1,01 | Marcar con aviso, sin corregir (2.3) |
| Inconsistencia | Una conducta con dos descripciones distintas | CONDUCTA, DESCRIPCION_CONDUCTA | 3 | 0,00 | Unificar la descripción (2.1) |
| Inconsistencia | Primera infancia o infancia con estado civil de adulto | CURSO_DE_VIDA, ESTADO_CIVIL_PERSONA | 3 | 0,00 | Marcar con aviso (2.3) |
| Formato | Variantes de escritura del mismo valor (espacios, tildes) | Varias | 11 | 0,01 | Normalizar el texto y unificar (2.1) |

## 1.1 Estructura del conjunto de datos

- **Registros:** 135.076. **Variables:** 19. **Hojas del libro:** Data.
- **Periodo:** del 2010-01-01 al 2021-12-31 (2010–2021).
- **Identificador:** `ORDEN` va de 1 a 135.076, es único y no tiene huecos. Sigue el orden cronológico de los hechos (correlación de rangos con la fecha: 1,0000).
- **Tipos:** el xlsx guarda **todas** las celdas como texto, incluidas las numéricas. Al leerlo, solo `ORDEN`, `ANO` y `DIA` se pueden interpretar como enteros. Las coordenadas, numéricas por naturaleza, no se pueden convertir directamente por su formato. `MES` y `DIA_SEMANA` son ordinales escritos como texto con un prefijo numérico ('01. ENERO').

| Variable | Tipo de celda en el xlsx | Tipo inferido al leer | Tipo según su significado | Valores distintos | Valor más frecuente | Ejemplos |
|---|---|---|---|---|---|---|
| ORDEN | texto | entero | Identificador | 135.076 | 1 (1) | 46778 · 117284 · 55724 |
| ARMAS_MEDIOS | texto | texto | Categórica nominal | 43 | SIN EMPLEO DE ARMAS (38.265) | MOTO · CONTUNDENTES · PAPA EXPLOSIVA |
| BARRIOS_HECHO | texto | texto | Categórica nominal (alta cardinalidad) | 484 | CENTRO (11.199) | LA FLORESTA · ALTOS DEL KENNEDY · TRANSICION I |
| LATITUD | texto | texto | Numérica continua (guardada como texto) | 64.429 | xx.xxxx (6.363) | 710,283,391 · 7,126,499,506 · 71,219,864,736 |
| LONGITUD | texto | texto | Numérica continua (guardada como texto) | 60.106 | -yy.yyyy (6.363) | -7,311,459,295 · -73,110,023,662 · -73.122313119 |
| ZONA | texto | texto | Categórica nominal | 4 | URBANA (131.547) | NO REPORTA · OTROS · URBANA |
| NOM_COMUNA | texto | texto | Categórica nominal | 26 | 03. SAN FRANCISCO (15.875) | 08. SUR OCCIDENTE · 06. LA CONCORDIA · 16. LAGOS DEL CACIQUE |
| ANO | texto | entero | Numérica discreta (temporal) | 12 | 2016 (13.610) | 2015 · 2012 · 2013 |
| MES | texto | texto | Categórica ordinal (texto '01. ENERO') | 12 | 10. OCTUBRE (11.990) | 10. OCTUBRE · 11. NOVIEMBRE · 02. FEBRERO |
| DIA | texto | entero | Numérica discreta (temporal) | 31 | 1 (5.097) | 23 · 5 · 9 |
| DIA_SEMANA | texto | texto | Categórica ordinal | 7 | 06. SÁBADO (21.747) | 03. MIÉRCOLES · 06. SÁBADO · 07. DOMINGO |
| DESCRIPCION_CONDUCTA | texto | texto | Categórica nominal | 43 | ARTÍCULO 239. HURTO A PERSONAS (48.452) | ARTÍCULO 239. HURTO A RESIDENCIAS · ARTÍCULO 103. HOMICIDIO · ARTÍCULO 239. HURTO A ABIGEATO |
| CONDUCTA | texto | texto | Categórica nominal | 41 | HURTO A PERSONAS (48.452) | HURTO A RESIDENCIAS · HOMICIDIO · ACTOS SEXUALES CON MENOR DE 14 AÑOS (CIRCUNSTANCIAS DE AGRAVACIÓN) |
| CLASIFICACIONES DELITO | texto | texto | Categórica nominal | 4 | LESIONES NO FATALES (128.993) | NO REPORTA · VIOLENCIA SEXUAL · LESIONES NO FATALES |
| CURSO_DE_VIDA | texto | texto | Categórica ordinal | 8 | 05. ADULTEZ (62.516) | ERROR: #N/A · 03. ADOLESCENCIA · 04. JOVENES |
| ESTADO_CIVIL_PERSONA | texto | texto | Categórica nominal | 7 | SOLTERO (61.727) | VIUDO · CASADO · SOLTERO |
| GENERO | texto | texto | Categórica nominal | 3 | MASCULINO (63.560) | MASCULINO · NO REPORTA · FEMENINO |
| MOVIL_AGRESOR | texto | texto | Categórica nominal | 14 | A PIE (93.438) | CONDUCTOR TAXI · PASAJERO TAXI · PASAJERO BUS |
| MOVIL_VICTIMA | texto | texto | Categórica nominal | 14 | A PIE (104.797) | CONDUCTOR MOTOCICLETA · BICICLETA · CONDUCTOR TAXI |

## 1.2 Problemas de calidad

### Valores nulos y marcadores de faltante

No hay valores nulos (0) ni celdas vacías (0). Los faltantes están escritos como texto, con marcadores distintos según la variable. 24.240 registros (17,9 %) tienen al menos uno.

| Variable | Marcador | Registros | % del total |
|---|---|---|---|
| ARMAS_MEDIOS | NO REPORTADO | 2.113 | 1,56 |
| BARRIOS_HECHO | SIN INFORMACION | 38 | 0,03 |
| LATITUD | xx.xxxx | 6.363 | 4,71 |
| LONGITUD | -yy.yyyy | 6.363 | 4,71 |
| ZONA | NO REPORTA | 2.189 | 1,62 |
| NOM_COMUNA | SIN INFORMACION | 45 | 0,03 |
| DESCRIPCION_CONDUCTA | NO REPORTA | 12 | 0,01 |
| CONDUCTA | NO REPORTA | 12 | 0,01 |
| CLASIFICACIONES DELITO | NO REPORTA | 12 | 0,01 |
| CURSO_DE_VIDA | NO REPORTA | 10.001 | 7,40 |
| CURSO_DE_VIDA | ERROR: #N/A | 940 | 0,70 |
| ESTADO_CIVIL_PERSONA | NO REPORTA | 17.134 | 12,68 |
| GENERO | NO REPORTA | 15.105 | 11,18 |
| MOVIL_AGRESOR | NO REPORTA | 434 | 0,32 |
| MOVIL_VICTIMA | NO REPORTA | 881 | 0,65 |

### Registros duplicados

- **Duplicados completos:** 0, porque `ORDEN` es único en todas las filas.
- **Duplicados sin `ORDEN`:** 8.952 registros forman 4.330 grupos de filas idénticas en las otras 18 columnas. Si se conserva un registro por grupo, sobran **4.622** (3,4 %).
- **Tamaño de los grupos:** 4.099 grupos de 2, 189 grupos de 3, 31 grupos de 4, 7 grupos de 5, 2 grupos de 6, 1 grupo de 7, 1 grupo de 9.
- **No son coincidencias:** al permutar al azar el día dentro de cada mes (5 repeticiones), se esperan 360–399 duplicados. El valor observado es unas 12 veces mayor.
- **Coinciden con otros errores de carga:** la tasa pasa del 1–3 % anual en 2010–2018 al 6,5–8,8 % en 2019–2021, los mismos años con coordenadas intercambiadas y días de la semana errados.
- **Son idénticos incluso en la víctima:** curso de vida, estado civil, género y móvil coinciden. En cambio, 25.885 registros comparten el hecho (fecha, lugar, conducta, arma y móvil del agresor) con víctimas distintas, que es lo esperable cuando un hecho tiene varias víctimas.
- **Limitación:** sin hora ni identificador de víctima no puede descartarse que algunos grupos sean víctimas distintas con el mismo perfil, sobre todo en lesiones de tránsito.

| Año | Registros | Duplicados sobrantes | % del año | Esperados por azar |
|---|---|---|---|---|
| 2010 | 8.693 | 203 | 2,34 | 39,20 |
| 2011 | 10.367 | 299 | 2,88 | 51,80 |
| 2012 | 10.912 | 277 | 2,54 | 40,60 |
| 2013 | 10.759 | 248 | 2,31 | 36,40 |
| 2014 | 10.214 | 189 | 1,85 | 9,00 |
| 2015 | 10.829 | 236 | 2,18 | 51,60 |
| 2016 | 13.610 | 246 | 1,81 | 13,40 |
| 2017 | 12.308 | 124 | 1,01 | 3,20 |
| 2018 | 13.492 | 356 | 2,64 | 11,80 |
| 2019 | 12.566 | 812 | 6,46 | 31,60 |
| 2020 | 9.605 | 848 | 8,83 | 29,40 |
| 2021 | 11.721 | 784 | 6,69 | 59,00 |

Conductas con más duplicados sobrantes:

| Conducta | Registros | Duplicados sobrantes | % de la conducta |
|---|---|---|---|
| HURTO A PERSONAS | 48.452 | 1.982 | 4,09 |
| LESIONES CULPOSAS ( EN ACCIDENTE DE TRANSITO ) | 21.130 | 1.214 | 5,75 |
| LESIONES PERSONALES | 24.450 | 891 | 3,64 |
| VIOLENCIA INTRAFAMILIAR | 16.519 | 182 | 1,10 |
| HURTO A ENTIDADES COMERCIALES | 8.937 | 128 | 1,43 |
| ACTOS SEXUALES CON MENOR DE 14 AÑOS | 1.529 | 62 | 4,05 |
| HURTO A RESIDENCIAS | 4.752 | 51 | 1,07 |
| HURTO A MOTOCICLETAS | 3.708 | 30 | 0,81 |
| HOMICIDIO | 1.365 | 17 | 1,25 |
| ACCESO CARNAL ABUSIVO CON MENOR DE 14 AÑOS | 805 | 13 | 1,61 |

### Formato de las coordenadas

- **Formatos:** `LATITUD` tiene 27 formatos de texto distintos y `LONGITUD` 29. 124.191 latitudes usan comas como separador de miles en posiciones arbitrarias y 3.604 usan punto decimal.
- **Sin coordenadas:** 6.363 registros traen los marcadores `xx.xxxx` / `-yy.yyyy`.
- **Intercambiadas:** 956 registros tienen la longitud en `LATITUD` y la latitud en `LONGITUD` (años: 2020: 956).
- **Sin signo:** 1 registro tiene la longitud sin signo negativo.
- **Recuperables:** con la regla de reconstrucción se recuperan 128.712 coordenadas dentro del área de Bucaramanga (lat 7,0–7,25 y lon −73,25 a −73,0).
- **Irrecuperables:** 1 registro queda fuera del área y no puede corregirse.

Formatos más frecuentes (9 = cualquier dígito):

| Formato (9 = dígito) | LATITUD | LONGITUD |
|---|---|---|
| 9,999,999,999 | 100.539 | 0 |
| -99,999,999,999 | 0 | 60.299 |
| -9,999,999,999 | 0 | 25.278 |
| -99,999,999 | 0 | 22.626 |
| 99,999,999,999 | 11.043 | 0 |
| -999,999,999,999 | 0 | 10.983 |
| 999,999,999 | 9.119 | 0 |
| -yy.yyyy | 0 | 6.363 |
| xx.xxxx | 6.363 | 0 |
| 9.9999999999 | 2.374 | 828 |
| -99.9999999999 | 830 | 2.301 |
| 9,999,999 | 2.476 | 0 |

Registro con coordenada fuera del área:

| ORDEN | LATITUD | LONGITUD | NOM_COMUNA | BARRIOS_HECHO |
|---|---|---|---|---|
| 116724 | 4,590,126,666 | -7,419,390,437 | 01. NORTE | NUEVO COLON |

### Rangos y fechas

- **Rangos:** `ANO` va de 2010 a 2021, `DIA` de 1 a 31, y `MES` tiene 12 valores con el número y el nombre coherentes (sí).
- **Fechas imposibles** (por ejemplo, 31 de febrero): 0.
- **`DIA_SEMANA` incoherente con la fecha:** 577 registros, todos en el mes indicado abajo.

| Año | Mes | Registros con DIA_SEMANA errado | Registros del mes | % del mes |
|---|---|---|---|---|
| 2020 | 08. AGOSTO | 577 | 688 | 83,90 |

### Inconsistencias entre columnas

- **Conducta y clasificación:** 0 conductas tienen más de una clasificación, así que la relación es coherente. Sin embargo, la fuente clasifica los hurtos como 'LESIONES NO FATALES' (66.086 registros). Se documenta como una particularidad de la taxonomía de la fuente y no se modifica.
- **Conducta sin dato:** 12 registros tienen conducta y clasificación 'NO REPORTA'.
- **Conducta y descripción:** dos conductas aparecen con dos descripciones distintas:

| CONDUCTA | DESCRIPCION_CONDUCTA | Registros |
|---|---|---|
| HURTO A ABIGEATO | ARTÍCULO 239. HURTO A ABIGEATO | 10 |
| HURTO A ABIGEATO | ARTÍCULO 239. HURTO ABIGEATO | 1 |
| LESIONES CULPOSAS ( EN ACCIDENTE DE TRANSITO ) | ARTÍCULO 120. LESIONES CULPOSAS ( EN ACCIDENTE DE TRANSITO ) | 21.128 |
| LESIONES CULPOSAS ( EN ACCIDENTE DE TRANSITO ) | LESION ACCIDENTAL EN TRANSITO | 2 |

- **Otros municipios:** 166 registros tienen en `NOM_COMUNA` un municipio distinto de Bucaramanga. Además, 45 registros dicen 'SIN INFORMACION'.

| Municipio | Registros | Con ZONA = OTROS |
|---|---|---|
| FLORIDABLANCA | 121 | 81 |
| GIRON | 38 | 30 |
| MEDELLIN | 3 | 2 |
| PIEDECUESTA | 3 | 1 |
| BARRANCABERMEJA | 1 | 1 |

- **Barrios en varias comunas:** 134 barrios aparecen en más de una comuna. 1.359 registros tienen una comuna distinta de la más frecuente para su barrio; en su mayoría son registros aislados. Ejemplos:

| Barrio | Comunas | Registros |
|---|---|---|
| 5 DE ENERO | 05. GARCÍA ROVIRA · 01. NORTE · FLORIDABLANCA | 13 · 1 · 1 |
| ALARCON | 03. SAN FRANCISCO · 01. NORTE · 07. LA CIUDADELA · 12. CABECERA DEL LLANO | 2.070 · 1 · 1 · 1 |
| ALFONSO LOPEZ | 05. GARCÍA ROVIRA · 12. CABECERA DEL LLANO | 1.943 · 1 |
| ALTO VIENTO I | 16. LAGOS DEL CACIQUE · FLORIDABLANCA | 1 · 1 |
| ALTOS DEL KENNEDY | 01. NORTE · 13. ORIENTAL | 65 · 1 |
| ANTIGUO CAMPESTRE | 12. CABECERA DEL LLANO · 08. SUR OCCIDENTE | 263 · 1 |
| ANTONIA SANTOS | 13. ORIENTAL · 01. NORTE · 07. LA CIUDADELA | 967 · 1 · 1 |
| ANTONIA SANTOS SUR | 09. LA PEDREGOSA · 13. ORIENTAL | 2.333 · 1 |

- **Zona y comuna:** 39 registros de corregimientos (zona rural del municipio) están marcados como URBANA, y 165 registros de comunas urbanas como RURAL. Es plausible en los bordes del municipio, así que se documenta sin corregir.
- **Curso de vida y estado civil:** 3 registros de primera infancia o infancia tienen un estado civil de adulto, lo que es imposible:

| ORDEN | CURSO_DE_VIDA | ESTADO_CIVIL_PERSONA | CONDUCTA |
|---|---|---|---|
| 118840 | 01. PRIMERA INFANCIA | UNION LIBRE | HURTO A PERSONAS |
| 120289 | 02. INFANCIA | VIUDO | LESIONES PERSONALES |
| 122142 | 01. PRIMERA INFANCIA | CASADO | LESIONES CULPOSAS ( EN ACCIDENTE DE TRANSITO ) |

- **Medios de transporte poco plausibles:** Bucaramanga no tiene metro, puerto ni aeropuerto urbano. 'PASAJERO METRO' corresponde probablemente al sistema Metrolínea. Se documenta y se conserva:

| Variable | Valor | Registros |
|---|---|---|
| MOVIL_AGRESOR | PASAJERO METRO | 101 |
| MOVIL_AGRESOR | TRIPULANTE AERONAVE | 1 |
| MOVIL_AGRESOR | PASAJERO BARCO | 1 |
| MOVIL_VICTIMA | PASAJERO METRO | 117 |
| MOVIL_VICTIMA | PASAJERO AERONAVE | 2 |
| MOVIL_VICTIMA | PASAJERO BARCO | 1 |

### Formato del texto

- **Variantes de un mismo valor** (coinciden al quitar tildes, espacios y signos):

| Variable | Variantes | Registros |
|---|---|---|
| BARRIOS_HECHO | QUINTADANIA \| QUINTA DANIA | 381 \| 11 |

- **Valores con espacios dobles:** `BARRIOS_HECHO` (35 registros).
- **Palabras escritas con y sin tilde:** ARTICULO / ARTÍCULO; GARCIA / GARCÍA; TRANSITO / TRÁNSITO. Se normalizan a mayúsculas sin tildes en la limpieza.
