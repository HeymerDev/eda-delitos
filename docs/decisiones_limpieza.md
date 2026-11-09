# Decisiones de limpieza

Registro de cada decisión de limpieza (eliminación, recodificación, transformación, tratamiento de
atípicos) con el número de registros afectados y su justificación. Este archivo lo genera
`python -m src.cleaning` con las cifras de la ejecución; la misma tabla se muestra en la página
*Limpieza* de la aplicación.

**Principios**

- **El original no se modifica.** El xlsx, su copia CSV y `delitos_raw` conservan los 135.076 registros.
  Las decisiones se aplican solo al dataset nuevo `delitos_limpios`.
- **Toda eliminación queda registrada** en `delitos_eliminados` (orden, motivo, detalle y, en los
  duplicados, el ORDEN conservado), de modo que `delitos_limpios` + `delitos_eliminados` = 135.076.
- **Un solo motivo por registro.** Primero se aplica el filtro de alcance (E1) y después la
  eliminación de duplicados (E2) sobre los registros restantes.
- **No se imputa con la moda.** Los faltantes de las variables categóricas se recodifican como 'SIN DATO'.
- **Los atípicos y las inconsistencias se marcan con avisos (`flag_…`), no se eliminan.** Solo se anula
  un valor cuando es un error imposible de corregir.

## Tabla de decisiones

| ID | Actividad | Variable | Tipo | Decisión | Registros afectados | Justificación |
|---|---|---|---|---|---|---|
| D01 | 2.1 | Todas las categóricas | Transformación | Normalizar el texto: mayúsculas, sin tildes (se conserva la Ñ), sin espacios dobles ni espacios junto a paréntesis | 166.992 celdas | El original mezcla 'GARCÍA'/'GARCIA', 'TRÁNSITO'/'TRANSITO' y espacios dobles; sin normalizar, un mismo valor contaría como categorías distintas. |
| D02 | 2.1 | barrio, descripcion_conducta | Recodificación | Unificar variantes del mismo valor: barrio: QUINTADANIA → QUINTA DANIA (381); descripcion_conducta: ARTICULO 239. HURTO ABIGEATO → ARTICULO 239. HURTO A ABIGEATO (1); descripcion_conducta: LESION ACCIDENTAL EN TRANSITO → ARTICULO 120. LESIONES CULPOSAS (EN ACCIDENTE DE TRANSITO) (2) | 384 | Son la misma categoría escrita de dos formas (diagnóstico 1.2). Se elige la forma correcta del nombre. |
| D03 | 2.1 | MES, ANO, DIA | Transformación | Convertir el mes '01. ENERO' a número (1–12) y construir fecha_hecho (DATE) | 130.297 | Permite series de tiempo, filtros por rango y comprobar la coherencia de la fecha. |
| D04 | 2.1 | DIA_SEMANA | Corrección | Recalcular el día de la semana a partir de la fecha (ISO: 1 = lunes) | 575 corregidos | En agosto de 2020 el 84 % de los registros tenía un día de la semana que no corresponde a su fecha. La fecha es la referencia; el día se deriva de ella. |
| D05 | 2.1 | LATITUD, LONGITUD | Transformación | Reconstruir el valor decimal: solo dígitos, punto tras el 1.er dígito (latitud) o tras el 2.º (longitud) | 128.712 recuperadas | Los separadores de miles están en posiciones arbitrarias; en Bucaramanga la latitud es 7,xx y la longitud −73,xx, así que la posición del punto es conocida. |
| D06 | 2.1 | LATITUD, LONGITUD | Corrección | Intercambiar latitud y longitud cuando vienen cruzadas y corregir el signo de la longitud | 957 (aviso flag_coord_corregida) | Error de carga verificable: el valor de cada columna corresponde al rango de la otra; Bucaramanga está al occidente de Greenwich. |
| E1 | 2.1 | NOM_COMUNA | Eliminación | Eliminar los registros asignados a otro municipio (motivo FUERA_DEL_MUNICIPIO) | 166 | El estudio se limita a Bucaramanga; 115 de 166 traen ZONA = OTROS; no pueden asignarse a ninguna comuna. Aprobada. |
| E2 | 2.1 | 18 columnas (todas salvo ORDEN) | Eliminación | Eliminar duplicados exactos y conservar el ORDEN menor de cada grupo (motivo DUPLICADO_EXACTO) | 4.613 (4.321 grupos) | 12 veces más duplicados de los esperados por azar, concentrados en 2019–2021 junto con otros errores de carga e idénticos hasta en el perfil de la víctima. Aprobada. |
| D07 | 2.2 | 12 variables categóricas | Recodificación | Recodificar 'NO REPORTA', 'NO REPORTADO', 'SIN INFORMACION' y 'ERROR: #N/A' como la categoría 'SIN DATO' | 47.050 celdas | Son variables nominales u ordinales: imputar la moda inventaría categorías (p. ej., asignar 'MASCULINO' a 15.105 víctimas) y sesgaría los cruces. 'SIN DATO' conserva el registro y hace visible el faltante. |
| D08 | 2.2 | CURSO_DE_VIDA | Recodificación | Recodificar el error de Excel 'ERROR: #N/A' como 'SIN DATO' sin eliminar el registro | 924 | Es un error de fórmula en la fuente, no un dato inválido del hecho: el resto de las columnas del registro es válido. |
| D09 | 2.2 | latitud, longitud | Valor nulo + aviso | Dejar nulas las coordenadas inexistentes o irrecuperables y marcarlas (flag_coord_faltante, flag_coord_fuera_area) | 6.200 | Una ubicación no puede imputarse sin inventar el lugar del hecho. Los registros se conservan para los análisis no espaciales y se excluyen solo de los mapas. |
| A1 | 2.3 | latitud, longitud | Atípico (aviso) | Coordenada fuera del área de Bucaramanga (lat 7,0–7,25; lon −73,25 a −73,0): anular y marcar | 1 | Error imposible de corregir (punto en Bogotá); no se elimina el registro porque el resto es válido. |
| A2 | 2.3 | Conteo diario | Atípico (aviso) | Marcar los días cuyo conteo supera Q3 + 1.5·IQR y tiene z robusto > 3.5 (ambos dentro de su año): flag_dia_atipico | 11 días · 686 registros | En datos de conteo un atípico es un día con muchos más delitos de lo normal (fiestas de fin de año, 1 de enero, eventos). Es información real, no un error: se marca para poder analizarlo, no se elimina. |
| A3 | 2.3 | Conteo por barrio | Atípico (aviso) | Marcar los barrios cuyo conteo supera Q3 + 1.5·IQR y tiene z robusto > 3.5: flag_barrio_atipico | 54 barrios · 95.789 registros | La distribución por barrio es muy asimétrica: los atípicos son focos de concentración (CENTRO, SAN FRANCISCO…), no errores. En escala logarítmica ningún barrio es atípico. |
| A4 | 2.3 | barrio, comuna | Inconsistencia (aviso) | Marcar los registros cuya comuna no es la habitual de su barrio: flag_barrio_comuna | 1.198 | No se corrige con la moda porque no se puede saber si el error está en el barrio o en la comuna; el aviso permite excluirlos en análisis espaciales finos. |
| A5 | 2.3 | curso_vida, estado_civil | Inconsistencia (aviso) | Marcar primera infancia o infancia con estado civil de adulto: flag_curso_vida_estado_civil | 3 | Combinación imposible, pero no se sabe cuál de los dos valores es el erróneo; son 3 registros sin efecto en las frecuencias. |
| D10 | 2.3 | CONDUCTA | Transformación | Agrupar las 41 conductas en familias (grupo_delito): hurto, lesiones personales, lesiones en tránsito, violencia intrafamiliar, delitos sexuales, homicidio, homicidio en tránsito y otros | 130.297 | Facilita comparar tipos de delito con las características de la víctima (objetivo 3) sin perder la conducta original. |

## Resultado

| Concepto | Registros | % del original |
|---|---|---|
| Registros del conjunto original | 135.076 | 100,00 |
| Eliminados: hecho asignado a otro municipio | 166 | 0,12 |
| Eliminados: duplicado exacto | 4.613 | 3,42 |
| Eliminados: error irrecuperable | 0 | 0,00 |
| Registros del conjunto limpio | 130.297 | 96,46 |

## Notas sobre las decisiones aprobadas

**E1 · Registros de otros municipios (166).** El objeto de estudio son los
delitos ocurridos en Bucaramanga, y el conjunto se titula así. Estas filas declaran otro municipio en
`NOM_COMUNA` (Floridablanca 121, Girón 38, Medellín 3, Piedecuesta 3, Barrancabermeja 1). 115 de ellas
traen `ZONA = OTROS`, la única zona que no es urbana ni rural. Las coordenadas no permiten corregirlas,
porque el área de referencia también cubre a Floridablanca y Girón. Los 45 registros con
'SIN INFORMACION' en la comuna no se eliminan: falta el dato, pero no indican otro municipio.

**E2 · Duplicados exactos (4.613 en 4.321 grupos).**
El criterio compara las 18 columnas del original salvo `ORDEN`, después de normalizar el texto,
reconstruir las coordenadas y recalcular el día de la semana, y antes de recodificar los faltantes
(dos registros que solo difieren en 'NO REPORTA' frente a 'ERROR: #N/A' no se consideran iguales).
Evidencia (ver `docs/informe_diagnostico.md`):

- **No son coincidencias:** al permutar al azar el día dentro de cada mes se esperan 360–399
  duplicados; se observan unas 12 veces más.
- **Coinciden con otros errores de carga:** la tasa pasa del 1–3 % anual (2010–2018) al 6,5–8,8 %
  (2019–2021), los años con coordenadas intercambiadas y días de la semana errados.
- **Son idénticos hasta en el perfil de la víctima.**

*Limitación:* sin hora ni identificador de víctima no puede descartarse que algunos grupos sean
víctimas distintas de un mismo hecho con el mismo perfil, sobre todo en lesiones de tránsito.

## Qué significa un atípico en datos de conteo de delitos

Las variables del conjunto son categóricas; las únicas magnitudes son los **conteos** que resultan de
agregar los registros (delitos por día, por barrio). En un conteo, un valor atípico no es un dato
mal digitado sino un **periodo o un lugar con muchos más delitos de lo habitual**. Puede deberse a
un fenómeno real (fiestas, eventos, focos de criminalidad) o a la forma de registro (cargas masivas,
fechas por defecto). Por eso los atípicos se **marcan** para analizarlos y no se eliminan: borrarlos
subestimaría justamente los momentos y lugares de mayor riesgo.

- **Métodos:** límite superior de Tukey (Q3 + 1.5·IQR) y z robusto (Iglewicz y Hoaglin, 1993),
  z = (x − mediana) / (1,4826 · MAD), con umbral 3.5. Se marca un valor como atípico solo
  si ambos métodos coinciden. El z robusto usa la mediana y la MAD, que no se distorsionan por los
  mismos valores extremos que se quiere detectar, a diferencia de la media y la desviación estándar.
- **Días:** los umbrales se calculan dentro de cada año, porque el nivel general cambia entre años
  (por ejemplo, la caída de 2020). Tras la limpieza hay 11 días atípicos.
  4 de ellos son un 1 de enero. Días atípicos de mayor conteo:

| fecha | delitos | limite_iqr | z_robusto |
|---|---|---|---|
| 2018-01-01 | 77 | 60,00 | 4,72 |
| 2016-01-01 | 73 | 58,12 | 4,48 |
| 2020-01-01 | 73 | 51,00 | 4,82 |
| 2012-01-01 | 68 | 48,00 | 5,40 |
| 2020-01-07 | 62 | 51,00 | 3,76 |
| 2011-10-01 | 60 | 47,00 | 4,45 |
| 2013-02-23 | 56 | 46,50 | 3,78 |
| 2012-12-25 | 56 | 48,00 | 3,78 |

- **Efecto de los duplicados en los picos:** antes de eliminar los duplicados, varios días de
  diciembre de 2019 aparecían como los más atípicos de la serie. Los meses con más duplicados
  eliminados fueron:

| Año | Mes | Original | Duplicados | Limpio | % duplicado |
|---|---|---|---|---|---|
| 2.019 | 12 | 1.911 | 691 | 1.220 | 36,20 |
| 2.020 | 11 | 1.058 | 389 | 669 | 36,80 |
| 2.020 | 10 | 1.077 | 361 | 716 | 33,50 |
| 2.018 | 10 | 1.290 | 205 | 1.085 | 15,90 |
| 2.021 | 4 | 1.171 | 135 | 1.036 | 11,50 |

- **Días sin registros:** 5 días no tienen ningún delito (2019-03-27, 2019-03-28, 2019-03-29, 2019-03-30, 2019-03-31). En una ciudad con una media de unos 30 delitos
  diarios, lo más probable es que sea un hueco en la carga de datos y no una ausencia real de delitos.
  Se documenta como limitación de las series diarias.

- **Barrios:** la distribución es muy asimétrica (mediana de 46 delitos por barrio frente a 10.740 en CENTRO).
  Los barrios marcados son focos de concentración. En escala logarítmica ningún barrio supera
  |z| = 3.5, lo que confirma que no hay valores imposibles sino una cola larga. Barrios marcados con más delitos:

| barrio | delitos | z_robusto | z_robusto_log |
|---|---|---|---|
| CENTRO | 10.740 | 163,93 | 2,27 |
| SAN FRANCISCO | 5.721 | 86,99 | 2,01 |
| CABECERA DEL LLANO | 5.556 | 84,46 | 1,99 |
| LA CONCORDIA | 4.904 | 74,47 | 1,94 |
| PROVENZA | 3.338 | 50,46 | 1,78 |
| SAN ALONSO | 3.310 | 50,03 | 1,78 |
| CAMPO HERMOSO | 2.695 | 40,61 | 1,69 |
| GARCIA ROVIRA | 2.570 | 38,69 | 1,67 |

- **Día 1 del mes:** tiene 4.920 registros frente a una media de
  4.279 en los días 2 a 28. El exceso puede deberse a fechas
  registradas por defecto cuando se desconocía el día exacto. No hay forma de identificarlas
  registro a registro, así que se documenta como limitación y no se modifica.
