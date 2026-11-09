# Decisiones de limpieza

Registro de cada decisión de limpieza: eliminación, recodificación, imputación,
transformación o tratamiento de atípicos. Para cada una se indica a cuántos registros
afecta y por qué se tomó. La misma tabla se muestra en la página *Limpieza* de la aplicación.

**Principios generales**

- **El original no se modifica.** Las decisiones se aplican solo al dataset nuevo
  (`delitos_limpios`). El xlsx original, su copia CSV y la tabla `delitos_raw` conservan
  los 135.076 registros. La integridad de los archivos se comprueba con `data/raw/SHA256SUMS.txt`.
- **Toda eliminación queda registrada** en `delitos_eliminados` con su `orden`, su
  `motivo` y un `detalle`. Así se cumple siempre: `delitos_limpios` + `delitos_eliminados` = 135.076.
- **Cada registro tiene un solo motivo de eliminación.** Las reglas se aplican en el orden de esta tabla.

> Las cifras se obtuvieron sobre el original. Las cifras definitivas las produce
> `src/cleaning.py` en la Fase 2 y se actualizan aquí al ejecutarlo.

## Eliminaciones (actividad 2.1)

| ID | Decisión | Registros | Justificación | Estado |
|---|---|---|---|---|
| E1 | **Eliminar los registros asignados a otro municipio.** Se eliminan las filas cuyo `NOM_COMUNA` es FLORIDABLANCA (121), GIRON (38), MEDELLIN (3), PIEDECUESTA (3) o BARRANCABERMEJA (1). Motivo: `FUERA_DEL_MUNICIPIO`. | 166 (0,12 %) | Ver la justificación de E1 debajo de la tabla. | Aprobada |
| E2 | **Eliminar los duplicados exactos.** Son duplicados los registros idénticos en las 18 columnas, excepto `ORDEN`. Se comparan después de normalizar el texto, reconstruir las coordenadas y recalcular el día de la semana. En cada grupo se conserva el `ORDEN` menor. Motivo: `DUPLICADO_EXACTO`, con `orden_conservado`. | ≈ 4.613 (3,4 %) | Ver la justificación de E2 debajo de la tabla. | Aprobada |

**Justificación de E1.** El objeto de estudio son los delitos ocurridos en el municipio de
Bucaramanga, y el propio conjunto se titula así. Estas filas declaran que el hecho ocurrió
en otro municipio, de modo que quedan fuera del alcance del análisis.

- **La fuente las identifica como externas:** 115 de las 166 traen `ZONA = OTROS`, la única
  categoría que no es urbana ni rural.
- **No se pueden asignar a ninguna comuna de Bucaramanga:** si se conservaran, aparecerían
  como comunas falsas en los conteos espaciales.
- **Las coordenadas no permiten corregirlas.** El área de referencia usada (lat 7,0–7,25 y
  lon −73,25 a −73,0) también cubre a Floridablanca y Girón, así que no confirma ni descarta
  la etiqueta.
- **Su peso es mínimo (0,12 %)** y se concentran en 2019–2021 (133 de las 166).

Los 45 registros con `NOM_COMUNA = SIN INFORMACION` **no** se eliminan: no indican otro
municipio, solo falta el dato. Se recodifican como `SIN DATO`.

**Justificación de E2.** Se identificaron 4.622 registros sobrantes en el original, y quedan
4.613 tras aplicar E1, porque 9 de ellos ya eran de otro municipio. Hay tres indicios de que
son errores de carga y no coincidencias:

- **No se explican por azar:** al mezclar aleatoriamente el día dentro de cada mes, el número
  de duplicados esperado fue de 360 a 399. El observado es unas 12 veces mayor.
- **La tasa sube en los años con otros errores de carga:** pasa del 1–3 % anual (2010–2018) al
  6,5–8,8 % (2019–2021). Esos son los años de las coordenadas intercambiadas (2020) y de los
  días de la semana errados (agosto de 2020).
- **Las filas son idénticas incluso en el perfil completo de la víctima.**

**Limitación de E2.** El dataset no tiene hora ni identificador de víctima. Por eso no puede
descartarse que una parte de los grupos sean víctimas distintas de un mismo hecho, sobre todo
en las lesiones de tránsito, donde el 11 % de las filas está duplicado. La evidencia de este
análisis está en el informe de diagnóstico y en la página *Diagnóstico* de la aplicación.

## Pendientes de la Fase 2

Se documentan al implementarlas en `src/cleaning.py`:

- Normalización de texto, conversión del mes a número y construcción de `fecha_hecho`.
- Reconstrucción de coordenadas: corrección de lat/lon intercambiadas y de signo, y anulación
  de las irrecuperables.
- Recálculo de `dia_semana`.
- Recodificación de los faltantes a `SIN DATO` (actividad 2.2).
- Unificación de variantes de escritura.
- Avisos de atípicos e inconsistencias (actividad 2.3).
