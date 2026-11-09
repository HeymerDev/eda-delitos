# Resultados

<!-- Párrafo introductorio: se revisa al cerrar la fase 4 para incluir las cifras finales de limpieza y análisis. -->
El proyecto analizó los 135.076 registros de delitos ocurridos en Bucaramanga entre 2010 y 2021, publicados
por la Alcaldía de Bucaramanga en el portal de datos abiertos de Colombia (conjunto `75fz-q98y`).

- **Almacenamiento:** el conjunto original se guardó sin modificaciones en una base de datos PostgreSQL alojada
  en Neon, en una tabla de solo lectura, y se conservó una copia en CSV cuya integridad se comprueba con
  huellas SHA-256.
- **Diagnóstico:** con Python (pandas) se diagnosticó la calidad de los datos: estructura, marcadores de dato
  faltante, duplicados, formato de las coordenadas, fechas e inconsistencias entre columnas.
- **Limpieza:** los problemas encontrados se corrigieron en un conjunto de datos nuevo, en el que cada
  eliminación queda registrada con su motivo.
- **Análisis y visualización:** sobre los datos limpios se hizo un análisis exploratorio de la distribución de
  los delitos en el espacio, en el tiempo y según el perfil de las víctimas, con una aplicación interactiva en
  Streamlit (gráficos de plotly). El tablero final se elaboró en Power BI, conectado a vistas de la base de datos.

## Objetivo 1: Diagnosticar la calidad del conjunto de datos de delitos de Bucaramanga.

### Actividad 1.1: Explorar la estructura del conjunto de datos: número de registros, variables y tipos de datos.

**Almacenamiento.** Para cumplir el requisito de almacenamiento se creó un proyecto en Neon con una base de
datos PostgreSQL (Figura 1). El original se exportó del formato xlsx a una copia CSV en UTF-8, y se verificó
celda por celda que ambas versiones tuvieran el mismo contenido. Esa copia se cargó en la tabla `delitos_raw`.

Como se observa en la Figura 2, todas las columnas de `delitos_raw` se definieron como texto, salvo `ORDEN`, que
es la clave primaria. Así la base conserva exactamente lo publicado, incluidos los errores, que son la
evidencia del diagnóstico.

La carga se hizo con el comando `COPY` de PostgreSQL en una sola transacción, que se revierte si el número de
filas no coincide. Para verificarla se ejecutaron dos comprobaciones:

- **Conteo:** la consulta de `sql/02_carga_verificacion.sql` devolvió 135.076 registros en `delitos_raw`,
  igual al total del archivo original (Figura 3).
- **Contenido:** al comparar la tabla con la copia CSV, ambas resultaron idénticas celda por celda.

**Estructura.** La exploración del archivo mostró:

- **Tamaño:** 135.076 registros y 19 variables, en una sola hoja.
- **Periodo:** hechos del 1 de enero de 2010 al 31 de diciembre de 2021.
- **Identificador:** `ORDEN` es único, va de 1 a 135.076 sin huecos y sigue el orden cronológico de los hechos
  (correlación de rangos con la fecha igual a 1).
- **Tipos de dato:** la Figura 4 muestra el tipo, la cardinalidad y ejemplos de cada variable. Se encontró que
  el archivo guarda todas las celdas como texto, incluso las numéricas. Al leerlo, solo `ORDEN`, `ANO` y `DIA`
  pueden interpretarse como enteros. Las coordenadas, que son numéricas por naturaleza, no pueden convertirse
  directamente por su formato.
- **Tipo de variables:** dieciséis de las diecinueve variables son categóricas. Su cardinalidad va desde 3
  valores (`GENERO`) hasta 484 (`BARRIOS_HECHO`).
- **Variables ordinales escritas como texto:** `MES`, `DIA_SEMANA` y `CURSO_DE_VIDA` llevan un prefijo
  numérico (por ejemplo, «01. ENERO»).

**Figura 1**

*Proyecto y base de datos creados en Neon*

[CAPTURA PENDIENTE: panel del proyecto en Neon]
![Figura 1](capturas/figura_01_neon_proyecto.png)

*Nota.* Elaboración propia en Neon (PostgreSQL). La captura no debe mostrar la cadena de conexión ni las credenciales.

**Figura 2**

*Definición de la tabla delitos_raw en PostgreSQL*

![Figura 2](capturas/figura_02_sql_create_raw.png)

*Nota.* Elaboración propia; fragmento del archivo `sql/01_schema.sql`.

**Figura 3**

*Verificación de la carga de delitos_raw en el editor SQL de Neon*

[CAPTURA PENDIENTE: editor SQL de Neon con el resultado de la primera consulta de `sql/02_carga_verificacion.sql`]
![Figura 3](capturas/figura_03_neon_verificacion.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 4**

*Estructura del conjunto de datos original: variables, tipos y cardinalidad*

![Figura 4](capturas/figura_04_estructura.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

### Actividad 1.2: Identificar valores nulos, registros duplicados, errores de formato e inconsistencias.

**Valores faltantes.** El conjunto no tiene valores nulos ni celdas vacías. Los datos faltantes están escritos
como texto con marcadores distintos según la variable: «NO REPORTA», «NO REPORTADO», «SIN INFORMACION»,
«ERROR: #N/A» y «xx.xxxx» / «-yy.yyyy» en las coordenadas. En total, 24.240 registros (17,9 %) tienen al
menos un marcador.

Como se observa en la Figura 5, las variables de la víctima son las más afectadas:

- `ESTADO_CIVIL_PERSONA`: 17.134 registros (12,7 %).
- `GENERO`: 15.105 (11,2 %).
- `CURSO_DE_VIDA`: 10.941 (8,1 %). De ellos, 940 tienen el valor de error de Excel «ERROR: #N/A».

Les siguen las coordenadas, con 6.363 registros sin ubicación (4,7 %). Este patrón anticipa que el análisis
del perfil de las víctimas deberá tratar la categoría de dato faltante de forma explícita.

**Duplicados.** No hay registros duplicados completos, porque `ORDEN` es único. Sin embargo, al excluir `ORDEN`:

- **Grupos:** 8.952 registros forman 4.330 grupos de filas idénticas en las 18 columnas restantes.
- **Sobrantes:** si se conserva un registro por grupo, sobran 4.622 (3,4 %).
- **Comparación con el azar:** para saber si podían ser coincidencias, se permutó al azar el día dentro de cada
  mes en cinco repeticiones. Ese procedimiento conserva las frecuencias y rompe cualquier relación real entre
  registros. Con él se esperaban entre 360 y 399 duplicados, de modo que el valor observado es unas 12 veces
  mayor.
- **Distribución por año (Figura 6):** los duplicados se concentran en 2019, 2020 y 2021, con el 6,5 %, el
  8,8 % y el 6,7 % de los registros de cada año. Entre 2010 y 2018 oscilaban entre el 1,0 % y el 2,9 %.
- **Coincidencia con otros errores:** el aumento ocurre en los mismos años en que aparecen otros errores de
  carga, como las coordenadas intercambiadas y los días de la semana errados.
- **Ejemplos (Figura 7):** las filas de cada grupo coinciden incluso en el curso de vida, el estado civil y el
  género de la víctima.

Por estos indicios, los duplicados se interpretaron como errores de carga. Queda una limitación: como el
conjunto no incluye la hora ni un identificador de víctima, no puede descartarse que algunos grupos
correspondan a víctimas distintas de un mismo hecho con el mismo perfil.

**Coordenadas.** Las coordenadas presentan el error de formato más extendido (Figura 8):

- **Formatos:** la latitud aparece en 27 formatos de texto distintos y la longitud en 29.
- **Separadores mal ubicados:** 124.191 latitudes usan comas como separador de miles en posiciones arbitrarias.
  Por ejemplo, «7,170,557,382» corresponde a 7,170557382.
- **Intercambiadas:** 956 registros de 2020 tienen la latitud y la longitud en columnas cruzadas.
- **Sin signo:** una longitud carece de signo negativo.
- **Recuperables:** al reconstruir el valor decimal se recuperan 128.712 coordenadas dentro del área de
  Bucaramanga.
- **Irrecuperable:** un registro (ORDEN 116724) señala un punto en Bogotá y no puede corregirse.

**Rangos y fechas.** Los rangos son válidos: los años van de 2010 a 2021, los días de 1 a 31, y el número y el
nombre del mes son coherentes. No se hallaron fechas imposibles, como un 31 de febrero. Sin embargo, 577
registros de agosto de 2020 (el 83,9 % de ese mes) tienen un día de la semana que no corresponde a su fecha.

**Inconsistencias entre columnas.** La Figura 9 resume los errores de formato y las inconsistencias:

- **Otros municipios:** 166 registros asignan el hecho a otro municipio (Floridablanca 121, Girón 38,
  Medellín 3, Piedecuesta 3 y Barrancabermeja 1), a pesar de que el conjunto se refiere a Bucaramanga.
- **Barrio y comuna:** 134 barrios aparecen en más de una comuna, y 1.359 registros tienen una comuna distinta
  de la habitual de su barrio.
- **Curso de vida y estado civil:** tres registros combinan primera infancia o infancia con un estado civil de
  adulto.
- **Conducta y descripción:** dos conductas tienen una descripción alternativa en tres registros.
- **Escritura:** hay variantes del mismo valor («QUINTADANIA» y «QUINTA DANIA») y palabras escritas con y sin
  tilde.

Además, la relación entre conducta y clasificación es coherente, porque cada conducta tiene una sola
clasificación. Aun así, la fuente clasifica los 66.086 hurtos como «LESIONES NO FATALES», una particularidad
de su taxonomía que se documentó sin modificar.

**Figura 5**

*Marcadores de dato faltante por variable en el conjunto original*

![Figura 5](capturas/figura_05_faltantes.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 6**

*Registros duplicados (sin considerar ORDEN) por año: observados frente a esperados por azar*

![Figura 6](capturas/figura_06_duplicados_anio.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 7**

*Muestra de grupos de registros duplicados*

![Figura 7](capturas/figura_07_duplicados_muestra.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 8**

*Formatos de texto encontrados en las coordenadas*

![Figura 8](capturas/figura_08_coord_formatos.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 9**

*Resumen de errores de formato e inconsistencias entre columnas*

![Figura 9](capturas/figura_09_inconsistencias.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

### Actividad 1.3: Documentar los problemas de calidad encontrados en un informe de diagnóstico.

Los problemas identificados se documentaron en un informe de diagnóstico que la aplicación genera de forma
automática. El informe se guarda en `docs/informe_diagnostico.md` y puede descargarse desde la página
*Diagnóstico* (Figura 10).

El informe clasifica los problemas en cuatro tipos: faltantes, duplicados, formato e inconsistencia. Para cada
uno indica las variables afectadas, el número y el porcentaje de registros, y el tratamiento propuesto, que se
aplica en la fase de limpieza. Los problemas de mayor alcance son:

- El formato de las coordenadas (91,9 % de los registros).
- Los marcadores de dato faltante (17,9 %).
- Los duplicados (3,4 %).

Los demás afectan a menos del 1,1 % de los registros cada uno. El informe establece además que ninguna
corrección se aplica sobre el original: todas se hacen sobre un conjunto de datos nuevo.

**Figura 10**

*Informe de diagnóstico de calidad generado por la aplicación*

![Figura 10](capturas/figura_10_informe.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

## Objetivo 2: Limpiar y preparar los datos mediante el tratamiento de valores nulos y atípicos.

### Actividad 2.1: Corregir los errores de formato y eliminar los registros duplicados o inconsistentes.

*(Se completa en la fase 2.)*

### Actividad 2.2: Aplicar técnicas de tratamiento de valores nulos según el tipo de cada variable.

*(Se completa en la fase 2.)*

### Actividad 2.3: Detectar y tratar los valores atípicos, y validar el conjunto de datos resultante.

*(Se completa en la fase 2.)*

## Objetivo 3: Describir la distribución de los delitos en el espacio, en el tiempo y según el perfil de las víctimas mediante análisis exploratorio.

### Actividad 3.1: Calcular las estadísticas descriptivas y las frecuencias de cada variable.

*(Se completa en la fase 3.)*

### Actividad 3.2: Analizar la distribución de los delitos por zona geográfica y por periodo de tiempo.

*(Se completa en la fase 3.)*

### Actividad 3.3: Cruzar los tipos de delito con las características de las víctimas mediante tablas de contingencia.

*(Se completa en la fase 3.)*

## Objetivo 4: Visualizar los patrones delictivos identificados mediante gráficos y mapas.

### Actividad 4.1: Seleccionar los tipos de gráficos más adecuados para cada tipo de variable y análisis.

*(Se completa en la fase 4.)*

### Actividad 4.2: Elaborar los gráficos, como series de tiempo, barras y mapas de calor, y los mapas de concentración por zona.

*(Se completa en la fase 4.)*

### Actividad 4.3: Interpretar los patrones observados en las visualizaciones y contrastarlos con los antecedentes.

*(Se completa en la fase 4.)*
