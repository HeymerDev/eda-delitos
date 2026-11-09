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

La limpieza se implementó en Python (`src/cleaning.py`) sobre una copia del original, que no se modificó, y
produjo un conjunto de datos nuevo, `delitos_limpios`. Cada decisión quedó registrada con su actividad, los
registros afectados y su justificación en una tabla de decisiones (Figura 11), que también se muestra en la
aplicación y en `docs/decisiones_limpieza.md`.

**Correcciones de formato:**

- **Texto:** se normalizaron las doce variables categóricas: mayúsculas, sin tildes (conservando la Ñ) y sin
  espacios repetidos. Esto modificó 166.992 celdas y evitó que un mismo valor, como «GARCÍA ROVIRA» y «GARCIA
  ROVIRA», se contara como dos categorías.
- **Variantes:** se unificaron tres variantes de escritura del mismo valor, que afectaban a 384 registros.
- **Fechas:** el mes se convirtió de texto a número y se construyó la fecha del hecho. El día de la semana se
  recalculó a partir de esa fecha, lo que corrigió 575 registros de agosto de 2020.
- **Coordenadas:** se reconstruyeron con la función de la Figura 12, que conserva solo los dígitos e inserta el
  punto decimal tras el primer dígito en la latitud y tras el segundo en la longitud.

La Figura 13 muestra por qué fue necesario corregir además el orden y el signo: con la sola reconstrucción
decimal, los 956 registros de 2020 con las columnas cruzadas aparecían en la longitud +71° y la latitud −7°,
lejos de Bucaramanga. Tras intercambiarlos y corregir el signo de una longitud, 124.097 registros del conjunto
limpio quedaron con una ubicación válida dentro del municipio (Figura 14).

**Eliminaciones.** Se aplicaron las dos eliminaciones aprobadas, cada una registrada en `delitos_eliminados`
con su motivo:

- **Otros municipios:** 166 registros asignados a otro municipio, fuera del alcance del estudio.
- **Duplicados exactos:** 4.613 duplicados exactos, organizados en 4.321 grupos. En cada grupo se conservó el
  registro de `ORDEN` menor.

Como se observa en la Figura 15, el conjunto limpio conserva 130.297 registros, el 96,5 % del original. No
hubo eliminaciones por errores irrecuperables: el único error imposible de corregir, una coordenada ubicada en
Bogotá, se trató anulando la coordenada y no el registro.

La eliminación de duplicados tuvo un efecto visible en la serie temporal. Diciembre de 2019 pasó de 1.911 a
1.220 registros, porque el 36,2 % de sus registros eran duplicados. Algo similar ocurrió en octubre y
noviembre de 2020, con el 33,5 % y el 36,8 %.

**Figura 11**

*Tabla de decisiones de limpieza*

![Figura 11](capturas/figura_11_decisiones.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 12**

*Función de reconstrucción de las coordenadas*

![Figura 12](capturas/figura_12_codigo_coordenadas.png)

*Nota.* Elaboración propia; fragmento del archivo `src/utils.py`.

**Figura 13**

*Coordenadas con solo la reconstrucción decimal, antes de corregir intercambios y signos*

![Figura 13](capturas/figura_13_coord_antes.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 14**

*Ubicación de los delitos con coordenadas válidas después de la corrección*

![Figura 14](capturas/figura_14_coord_despues.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023). Mapa base: © OpenStreetMap contributors © CARTO.

**Figura 15**

*Registros del conjunto original y del conjunto limpio, y registros eliminados por motivo*

![Figura 15](capturas/figura_15_antes_despues.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

### Actividad 2.2: Aplicar técnicas de tratamiento de valores nulos según el tipo de cada variable.

La técnica de tratamiento se eligió según el tipo de cada variable (Figura 16).

**Variables categóricas.** En las doce variables categóricas, los marcadores «NO REPORTA», «NO REPORTADO»,
«SIN INFORMACION» y «ERROR: #N/A» se recodificaron como la categoría «SIN DATO», en 47.050 celdas. Se descartó
imputar con la moda: estas variables son nominales u ordinales, y asignar la categoría más frecuente, como
«MASCULINO» o «SOLTERO», a miles de víctimas habría inventado un perfil y sesgado las tablas de contingencia
del objetivo 3.

Los 924 registros con el error de Excel «ERROR: #N/A» en el curso de vida se recodificaron sin eliminarse,
porque el resto de sus columnas es válido. En el conjunto limpio, «SIN DATO» representa:

- El 12,5 % del estado civil.
- El 11,1 % del género.
- El 8,3 % del curso de vida.

**Coordenadas.** Las 6.200 coordenadas inexistentes o irrecuperables se dejaron como valores nulos,
identificados con los avisos `flag_coord_faltante` y `flag_coord_fuera_area`. Una ubicación no puede imputarse
sin inventar el lugar del hecho, así que estos registros se conservan para todos los análisis excepto los mapas.

**Figura 16**

*Tratamiento de los valores faltantes según el tipo de variable*

![Figura 16](capturas/figura_16_faltantes_tratamiento.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

### Actividad 2.3: Detectar y tratar los valores atípicos, y validar el conjunto de datos resultante.

**Qué es un atípico en este conjunto.** Como las variables del conjunto son categóricas, los atípicos se
buscaron en los conteos que resultan de agregarlas: delitos por día y delitos por barrio. En datos de conteo,
un atípico no es un error de digitación sino un periodo o un lugar con muchos más delitos de lo habitual, por
lo que se marcó con avisos y no se eliminó.

**Método.** Se combinaron dos criterios, y un valor se consideró atípico solo si ambos coincidían:

- **Límite de Tukey:** el valor supera Q3 + 1,5·IQR.
- **z robusto** de Iglewicz y Hoaglin: z mayor que 3,5, calculado con la mediana y la desviación absoluta
  mediana. Este criterio no se distorsiona por los mismos extremos que se busca detectar.

**Conteo diario.** Los umbrales se calcularon dentro de cada año, porque el nivel general cambia entre años
(Figura 17).

- **Días atípicos:** de 4.383 días, el límite de Tukey señaló 42 y el z robusto 11. Los 11 que cumplen ambos
  criterios agrupan 686 registros, marcados con `flag_dia_atipico`.
- **Fechas:** cuatro de esos días son un 1 de enero, y uno es la Navidad de 2012.
- **Efecto de los duplicados:** antes de eliminarlos, los picos más altos de la serie estaban en diciembre de
  2019. Con ellos, esos días habrían parecido atípicos.
- **Día 1 del mes:** tiene 4.920 registros, frente a una media de 4.279 en los días 2 a 28. Este exceso podría
  deberse a fechas registradas por defecto.
- **Días sin registros:** del 27 al 31 de marzo de 2019 no hay ningún registro. Probablemente es un hueco en la
  carga de datos.

Ambas situaciones del día 1 y de marzo de 2019 se documentaron como limitaciones.

**Conteo por barrio.** La distribución es muy asimétrica (Figura 18): la mediana es de 46 delitos por barrio,
mientras que CENTRO registra 10.740.

- **Escala lineal:** 54 de los 438 barrios superan ambos criterios y concentran el 73,5 % de los registros.
  Se marcaron con `flag_barrio_atipico`.
- **Escala logarítmica:** ningún barrio es atípico (z robusto máximo de 2,27), lo que indica una cola larga y
  no valores imposibles.
- **Lectura:** los barrios marcados se interpretan como focos de concentración del delito, que se analizan en el
  objetivo 3.

**Inconsistencias marcadas.** También se marcaron, sin corregirlas:

- **Barrio y comuna:** 1.198 registros cuya comuna no es la habitual de su barrio (`flag_barrio_comuna`).
- **Curso de vida y estado civil:** 3 registros de primera infancia o infancia con estado civil de adulto.

En ambos casos no es posible saber cuál de los dos valores es el erróneo.

**Validación.** El conjunto limpio superó las 18 pruebas de la Figura 19:

- Limpios más eliminados suman 135.076.
- Cada registro está en una sola tabla.
- No quedan duplicados según el criterio aprobado ni marcadores de faltante.
- Las fechas son coherentes con el año, el mes, el día y el día de la semana.
- Las coordenadas están dentro del área de Bucaramanga.
- Las categorías y los tipos de dato son los permitidos.

Estas pruebas coinciden con las restricciones `CHECK` del esquema de `delitos_limpios` en PostgreSQL. La carga
en Neon se verificó con el script `sql/02_carga_verificacion.sql` (Figura 20).
<!-- [PENDIENTE: escribir aquí el resultado de la verificación en Neon cuando se cargue delitos_limpios] -->

**Figura 17**

*Diagramas de caja del número de delitos por día, por año*

![Figura 17](capturas/figura_17_box_diario.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 18**

*Diagramas de caja del número de delitos por barrio en escala lineal y logarítmica*

![Figura 18](capturas/figura_18_box_barrio.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 19**

*Validación del conjunto de datos limpio*

![Figura 19](capturas/figura_19_validacion.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

**Figura 20**

*Verificación de la carga de delitos_limpios y delitos_eliminados en el editor SQL de Neon*

[CAPTURA PENDIENTE: editor SQL de Neon con el resultado de las consultas 2 y 4 de `sql/02_carga_verificacion.sql`]
![Figura 20](capturas/figura_20_neon_limpios.png)

*Nota.* Elaboración propia con datos de Alcaldía de Bucaramanga (2023).

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
