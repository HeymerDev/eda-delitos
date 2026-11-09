# Análisis exploratorio de los delitos ocurridos en Bucaramanga, Colombia (2010–2021)

Proyecto de la asignatura **Minería de Datos**. Es un análisis exploratorio de datos (EDA) y de
visualización de los 135.076 registros de delitos publicados por la Alcaldía de Bucaramanga.
No incluye modelos predictivos.

- **Almacenamiento:** PostgreSQL en [Neon](https://neon.tech).
- **Diagnóstico, limpieza y EDA:** Python + Streamlit.
- **Dashboard final:** Power BI (conectado a las vistas de `sql/03_vistas_powerbi.sql`).

## Fuente de los datos

| | |
|---|---|
| Conjunto | *40Delitos ocurridos en el Municipio de Bucaramanga* |
| Publicador | Alcaldía de Bucaramanga, Santander |
| Portal | datos.gov.co, identificador `75fz-q98y`: <https://www.datos.gov.co/d/75fz-q98y> |
| Licencia | Creative Commons Atribución-CompartirIgual 4.0 Internacional |
| Fecha de publicación en el portal | 16 de diciembre de 2023 |
| Fecha de descarga | 26 de octubre de 2026 |

El conjunto de datos lo indicó el profesor de la asignatura. Se descargó el 26 de octubre de 2026
en formato xlsx y se usa tal cual, sin modificar el archivo.

Referencia (APA 7):

> Alcaldía de Bucaramanga. (2023). *40Delitos ocurridos en el Municipio de Bucaramanga* [Conjunto de datos]. Datos Abiertos Colombia. https://www.datos.gov.co/d/75fz-q98y

### El dataset original no se modifica

- **Archivos originales en `data/raw/`:**
  - `…20261026.xlsx`: el archivo descargado.
  - `…20261026.csv`: su copia en CSV UTF-8, con el contenido idéntico celda a celda.
- **Integridad comprobable:** `data/raw/SHA256SUMS.txt` guarda la huella SHA-256 de los dos archivos.
  Se comprueba con:
  ```bash
  sha256sum -c data/raw/SHA256SUMS.txt
  ```
- **Tabla `delitos_raw` en Neon:** es la copia fiel de los 135.076 registros.
- **Dataset nuevo:** la limpieza genera `delitos_limpios`. Los registros que no pasan a la tabla
  limpia quedan en `delitos_eliminados`, cada uno con su motivo.

## Estructura

```
data/raw/          xlsx original + copia CSV original (UTF-8) + SHA256SUMS.txt
data/processed/    dataset limpio (parquet y csv); se regenera, no se versiona
sql/               01_schema.sql, 02_carga_verificacion.sql, 03_vistas_powerbi.sql
src/               load.py, diagnostico.py, cleaning.py, eda.py, capturas.py, utils.py
app/               Home.py y pages/ (aplicación Streamlit)
docs/              informe_diagnostico.md, decisiones_limpieza.md, resultados.md,
                   powerbi_guia.md, capturas/
```

## Requisitos

- Python 3.13 (en Windows se invoca con `py`).
- Git.
- Una cuenta gratuita en Neon.

Las dependencias de Python están en `requirements.txt`.

## Instalación

```bash
git clone <url-del-repositorio>
cd streamlit-eda
py -3.13 -m venv .venv
```

Activar el entorno virtual:

- Windows (PowerShell): `.\.venv\Scripts\Activate.ps1`
- Linux / macOS: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

```bash
playwright install chromium
```

El último comando solo hace falta para regenerar las capturas.

## Configurar la conexión a Neon (sin exponer credenciales)

1. **Crear el proyecto:** en <https://console.neon.tech>, cree un proyecto y una base de datos.
2. **Copiar la cadena de conexión:** en *Dashboard → Connect*, copie la *connection string*.
3. **Crear el archivo `.env`:** cópielo desde `.env.example` y pegue allí la cadena:
   ```
   DATABASE_URL=postgresql://usuario:contraseña@host.neon.tech/bd?sslmode=require
   ```
`.env` está en `.gitignore`, así que nunca se sube al repositorio. El código lee la cadena con
`python-dotenv` y no la imprime en ningún momento.

## Ejecución

Todos los comandos se ejecutan desde la raíz del proyecto, con el entorno virtual activo.

### Fase 0: copia del original y carga en Neon

Generar la copia CSV del xlsx y verificar que sea idéntica:

```bash
python -m src.load csv
```

Crear las tablas en Neon:

```bash
python -m src.load schema
```

Cargar la copia CSV en `delitos_raw`:

```bash
python -m src.load raw
```

Comprobar los conteos (también se puede ejecutar el archivo en el editor SQL de Neon):

```bash
python -m src.load verificar
```

### Fase 1: diagnóstico de calidad

Generar el informe y los resultados que usa la app (tarda unos 40 segundos):

```bash
python -m src.diagnostico
```

El informe queda en `docs/informe_diagnostico.md`.

### Fase 2: limpieza

Generar el conjunto limpio (unos 10 segundos):

```bash
python -m src.cleaning
```

El comando produce:

- `data/processed/delitos_limpios.{parquet,csv}` y `delitos_eliminados.{parquet,csv}`.
- `docs/decisiones_limpieza.md`, con la tabla de decisiones y las cifras de la ejecución.
- La tabla de validación en consola. Si alguna prueba falla, el proceso termina con error.

Cargar el resultado en Neon (vacía y vuelve a llenar `delitos_limpios` y `delitos_eliminados`):

```bash
python -m src.load limpios
```

Verificar la carga; ahora todas las consultas deben dar OK:

```bash
python -m src.load verificar
```

### Fase 3: análisis exploratorio

El análisis se ve en la página *Análisis exploratorio* de la app, con filtros por años, comuna, tipo de delito
y género. Para ver en consola un resumen de los resultados con el conjunto completo (frecuencias, conteos,
cambio en 2020, concentración de los hurtos, chi-cuadrado y Spearman):

```bash
python -m src.eda
```

### Aplicación

```bash
streamlit run app/Home.py
```

La app lee el original desde Neon (`delitos_raw`). Si no hay conexión, usa la copia CSV local. Para
forzar la lectura local, defina la variable de entorno `FUENTE_DATOS=local`:

- PowerShell: `$env:FUENTE_DATOS="local"`.
- bash: `export FUENTE_DATOS=local`.

### Capturas para el artículo

```bash
python -m src.capturas
```

El comando regenera todas las figuras en `docs/capturas/`:

- **Gráficos:** PNG exportados con kaleido.
- **Tablas y páginas de la app:** capturas tomadas con Playwright (headless), que arranca su propia instancia
  de la app.
- **Fragmentos de código:** imágenes generadas a partir de los archivos del proyecto.

La numeración de las figuras sale de `src/utils.py` (`FIGURAS`). Las capturas de Neon y Power BI se toman a
mano y se guardan con el nombre que indica el comando al final.

### Fase 4: visualización, hallazgos y Power BI

Crear las vistas en estrella para Power BI. Alternativamente, ejecute `sql/03_vistas_powerbi.sql` en el editor
SQL de Neon.

```bash
python -m src.load vistas
```

- **Power BI:** la conexión sin exponer credenciales, el modelo, las medidas DAX y las cifras de referencia
  están en [docs/powerbi_guia.md](docs/powerbi_guia.md). El archivo `.pbix` se elabora en Power BI Desktop.
- **Hallazgos:** la página *Visualización y hallazgos* de la app muestra cada hallazgo con su evidencia. El
  contraste con los antecedentes se escribe en esa misma página, o directamente en
  `docs/contraste_antecedentes.md`.
