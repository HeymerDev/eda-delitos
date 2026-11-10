# Guía para el tablero de Power BI

El tablero se construye en Power BI Desktop y se conecta a la base de datos PostgreSQL en Neon por medio de
las vistas de `sql/03_vistas_powerbi.sql`. Esta guía cubre la conexión sin exponer credenciales, el modelo de
datos, las medidas DAX, los indicadores y los segmentadores recomendados, y las cifras de referencia para
comprobar que el tablero calcula bien.

## 1. Preparar las vistas en Neon

Las vistas se crean con uno de estos dos métodos:

- **Desde Python:** ejecute `python -m src.load vistas`.
- **Desde Neon:** pegue `sql/03_vistas_powerbi.sql` en el editor SQL y ejecútelo.

| Vista | Rol en el modelo | Filas esperadas |
|---|---|---|
| `vw_fact_delitos` | Hechos (un registro por delito) | 130.297 |
| `vw_dim_tiempo` | Calendario 2010–2021 | 4.383 |
| `vw_dim_territorio` | Comuna y barrio | 609 |
| `vw_dim_conducta` | Conducta, grupo y clasificación | 41 |
| `vw_dim_victima` | Género, curso de vida y estado civil | 92 |

**Recomendado: rol de solo lectura.** Power BI solo necesita leer, así que conviene conectarlo con un usuario
propio en lugar del usuario dueño de la base:

1. Al final de `03_vistas_powerbi.sql` está, comentado, el SQL para crear el rol `powerbi_lector` con permiso
   `SELECT` únicamente sobre las cinco vistas.
2. Ejecútelo una sola vez en el editor de Neon, con una contraseña generada en ese momento. También puede
   crear el rol desde *Roles* en la consola de Neon y luego ejecutar solo las líneas `GRANT`.

## Atajo: proyecto de Power BI ya armado

`python -m src.powerbi` genera un proyecto de Power BI (`.pbip`, la versión en texto de un `.pbix`) que ya
trae todo lo de las secciones 3 a 5: las cinco vistas conectadas a Neon, las relaciones, la tabla de fechas,
las ocho medidas DAX y una página *Tablero* con:

- **Indicadores:** seis tarjetas.
- **Segmentadores:** año, comuna, grupo de delito y género.
- **Visuales:** la serie mensual, las barras por grupo y por comuna, y la matriz de mes por año.

Pasos:

1. **Generar el proyecto:** ejecute `python -m src.powerbi`. Se crean dos carpetas:
   - `powerbi/`: el proyecto versionado en git, con un servidor de ejemplo.
   - `powerbi_local/`: la copia para abrir en este equipo, con el servidor y la base de su `.env`. Está en
     `.gitignore`.
2. **Abrir:** haga doble clic en `powerbi_local/Delitos_Bucaramanga.pbip`.
3. **Actualizar:** pulse *Actualizar*. Cuando Power BI pida credenciales, elija *Base de datos* y escriba su
   usuario y contraseña de Neon (idealmente `powerbi_lector`).
4. **Comprobar:** verifique las cifras de la sección 6.
5. **Guardar:** use *Archivo → Guardar como → .pbix* si necesita entregar un solo archivo.

Si abre el proyecto versionado (`powerbi/`), primero cambie los parámetros `Servidor` y `BaseDatos` en
*Inicio → Transformar datos → Editar parámetros*.

Los ajustes visuales que el proyecto no incluye se agregan a mano en Power BI:

- El formato condicional de la matriz (*Formato → Valores de celda → Color de fondo → Escala de colores*).
- El mapa de Azure Maps.
- Los colores por grupo de delito.

## 2. Conectar Power BI a Neon sin exponer credenciales

1. **Abrir el conector:** en Power BI Desktop, use *Obtener datos → Base de datos PostgreSQL*.
2. **Servidor:** escriba **solo el host** de Neon, por ejemplo `ep-xxxx-xxxx.us-east-2.aws.neon.tech`. Lo
   encuentra en *Dashboard → Connect* (*Connection details*).
3. **Base de datos:** el nombre de su base.
4. **Modo:** *Importar*. Son unos 130.000 registros, así que la importación es rápida y el tablero no depende de
   que el proyecto de Neon esté activo, ya que Neon suspende el cómputo cuando no hay uso.
5. **Credenciales:** en la ventana *Base de datos*, escriba el usuario (`powerbi_lector`) y su contraseña, y deje
   marcado *Cifrar conexiones*, porque Neon exige SSL.
6. **Tablas:** en el navegador, seleccione las cinco vistas `vw_…` y pulse *Cargar*.

**Por qué no se exponen las credenciales:**

- **No van en el archivo:** Power BI guarda las credenciales en el almacén de credenciales de Windows del
  usuario, no dentro del `.pbix`. Quien abra el archivo en otro equipo tendrá que escribir las suyas.
- **No van en el repositorio ni en las capturas:** nunca escriba la cadena de conexión completa
  (`postgresql://usuario:contraseña@…`) en el campo *Servidor*, en parámetros de Power Query ni en el
  repositorio. Las capturas del tablero no deben mostrar la ventana de credenciales.
- **El rol limita el daño:** como `powerbi_lector` solo puede leer las vistas, una filtración de su contraseña no
  permite modificar ni borrar datos.

**Si la conexión falla:**

- **Error de *endpoint* o de SNI:** algunos clientes antiguos no envían el nombre del servidor. Neon admite
  pasar el identificador del endpoint (la primera parte del host, `ep-xxxx-xxxx`) dentro del campo de
  contraseña. El formato exacto está en la documentación de Neon, en la sección sobre clientes sin soporte de
  SNI (*connection errors*); compruébelo allí antes de usarlo.
- **Falta el proveedor de PostgreSQL:** en versiones antiguas de Power BI Desktop puede pedir instalar
  **Npgsql**. Las versiones actuales ya lo incluyen.

## 3. Modelo de datos (estrella)

En *Vista de modelo*:

1. **Tabla de fechas:** marque `vw_dim_tiempo` como tabla de fechas (*Marcar como tabla de fechas → fecha*).
2. **Relaciones:** cree estas cuatro, todas de muchos a uno, con dirección de filtro única desde la dimensión
   hacia los hechos:

| Desde (hechos) | Hacia (dimensión) |
|---|---|
| `vw_fact_delitos[fecha_hecho]` | `vw_dim_tiempo[fecha]` |
| `vw_fact_delitos[territorio_key]` | `vw_dim_territorio[territorio_key]` |
| `vw_fact_delitos[conducta_key]` | `vw_dim_conducta[conducta_key]` |
| `vw_fact_delitos[victima_key]` | `vw_dim_victima[victima_key]` |

3. **Columnas de clave:** ocúltelas en la vista de informe (`*_key`, `orden`) para que no aparezcan en los
   visuales.
4. **Orden de las etiquetas:**
   - `vw_dim_tiempo[mes_nombre]` por `mes`.
   - `vw_dim_tiempo[dia_semana_nombre]` por `dia_semana`.
5. **Categoría de datos:** asigne *Latitud* y *Longitud* a `vw_fact_delitos[latitud]` y `[longitud]`.

## 4. Medidas DAX

Cree una tabla de medidas vacía (*Especificar datos*, llamada `Medidas`) y agregue:

```DAX
Total delitos =
COUNTROWS ( vw_fact_delitos )
```

```DAX
Total año anterior =
CALCULATE ( [Total delitos], SAMEPERIODLASTYEAR ( vw_dim_tiempo[fecha] ) )
```

```DAX
Variación % anual =
DIVIDE ( [Total delitos] - [Total año anterior], [Total año anterior] )
```

```DAX
% hurto =
DIVIDE (
    CALCULATE ( [Total delitos], vw_dim_conducta[grupo_delito] = "HURTO" ),
    CALCULATE ( [Total delitos], REMOVEFILTERS ( vw_dim_conducta ) )
)
```

```DAX
% SIN DATO (género) =
DIVIDE (
    CALCULATE ( [Total delitos], vw_dim_victima[genero] = "SIN DATO" ),
    CALCULATE ( [Total delitos], REMOVEFILTERS ( vw_dim_victima[genero] ) )
)
```

```DAX
Comuna con más casos =
VAR t = ADDCOLUMNS ( VALUES ( vw_dim_territorio[comuna] ), "@n", [Total delitos] )
RETURN MAXX ( TOPN ( 1, t, [@n], DESC ), vw_dim_territorio[comuna] )
```

```DAX
Participación comuna con más casos =
VAR t = ADDCOLUMNS ( VALUES ( vw_dim_territorio[comuna] ), "@n", [Total delitos] )
RETURN DIVIDE ( MAXX ( t, [@n] ), [Total delitos] )
```

```DAX
Promedio diario =
DIVIDE ( [Total delitos], COUNTROWS ( vw_dim_tiempo ) )
```

Las medidas de porcentaje se formatean como *Porcentaje* con 1 decimal.

**Notas sobre las medidas:**

- **`% hurto`** usa `REMOVEFILTERS` en el denominador. Así, si el usuario filtra por un grupo de delito, el
  porcentaje sigue calculándose sobre el total y no sobre la selección.
- **`% SIN DATO (género)`** se puede replicar para el curso de vida y el estado civil cambiando la columna.
- **`Variación % anual`** necesita que `vw_dim_tiempo` esté marcada como tabla de fechas. Se lee mejor en un
  visual con el año en el eje o en una tarjeta con un segmentador de año.

## 5. Tablero recomendado

**Indicadores (tarjetas), en la fila superior:**

- Total delitos.
- Variación % anual.
- % hurto.
- % SIN DATO (género).
- Comuna con más casos y su participación.

**Segmentadores**, en una sola franja a la izquierda o arriba:

- `vw_dim_tiempo[anio]` (estilo *Entre*, como rango de años).
- `vw_dim_territorio[comuna]`.
- `vw_dim_conducta[grupo_delito]`.
- `vw_dim_victima[genero]`.

Son los mismos filtros de la aplicación de Streamlit.

**Visuales:**

| Visual | Campos | Pregunta que responde |
|---|---|---|
| Gráfico de líneas | Eje: `anio_mes`; valor: Total delitos | ¿Cómo evolucionan los delitos? |
| Barras horizontales | `grupo_delito`; Total delitos | ¿Qué delitos predominan? |
| Barras horizontales | `comuna`; Total delitos (ordenadas) | ¿Dónde se concentran? |
| Matriz con formato condicional (escala de color) | Filas: `mes_nombre`; columnas: `anio`; valor: Total delitos | Mapa de calor mes × año |
| Matriz con «Mostrar valor como % del total de la fila» | Filas: `grupo_delito`; columnas: `genero` | Perfil de las víctimas por delito |
| Mapa (Azure Maps, capa de mapa térmico) | Latitud y Longitud de los hechos | Concentración geográfica |

**Notas:**

- **Colores:** use los mismos que en la aplicación, con un color fijo por grupo de delito: hurto azul `#2a78d6`,
  lesiones personales naranja `#eb6834`, lesiones en tránsito verde `#1baf7a`, violencia intrafamiliar amarillo
  `#eda100` y delitos sexuales rosa `#e87ba4`.
- **Mapa:** el visual de Azure Maps puede requerir habilitarse en *Opciones → Seguridad*.

## 6. Cifras de referencia para validar el tablero

Sin ningún filtro, el tablero debe mostrar estos valores, calculados con el mismo conjunto en Python:

| Medida | Valor esperado |
|---|---|
| Total delitos | 130.297 |
| Promedio diario | 29,73 |
| % hurto | 48,96 % |
| % SIN DATO (género) | 11,05 % |
| Comuna con más casos | 03. SAN FRANCISCO |
| Participación comuna con más casos | 11,77 % (15.338 delitos) |
| Variación % anual 2020 | −25,5 % (frente a 2019) |
| Variación % anual 2021 | +25,3 % (frente a 2020) |

## 7. Evidencias para el artículo

En `docs/resultados.md` quedaron reservadas dos figuras para capturas de Power BI. Antes de guardarlas,
compruebe que no muestren el servidor, el usuario ni la contraseña.

- **Modelo en estrella:** captura de la *Vista de modelo* con las cinco vistas y sus relaciones. Guárdela como
  `docs/capturas/figura_45_pbi_modelo.png`.
- **Tablero:** captura del tablero completo con los indicadores, los segmentadores y los visuales. Guárdela como
  `docs/capturas/figura_46_pbi_tablero.png`.
