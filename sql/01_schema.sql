-- =============================================================================
-- 01_schema.sql
-- Proyecto: Análisis exploratorio de los delitos ocurridos en Bucaramanga (2010–2021)
-- Motor: PostgreSQL (Neon)
--
-- Diseño en tres tablas:
--   delitos_raw         copia fiel del dataset original (135.076 filas). Nunca se modifica.
--   delitos_limpios     dataset NUEVO producido por src/cleaning.py, con tipos adecuados.
--   delitos_eliminados  trazabilidad: qué registros del original no pasaron a la tabla limpia y por qué.
--
-- Invariante que se verifica en 02_carga_verificacion.sql:
--   cada ORDEN de delitos_raw está exactamente en una de las tablas
--   delitos_limpios o delitos_eliminados  ->  limpios + eliminados = 135.076.
--
-- Re-ejecución: delitos_raw se crea con IF NOT EXISTS para que este script nunca la
-- borre. Las tablas derivadas (limpios y eliminados) se eliminan y se recrean porque
-- se regeneran por completo desde el original con src/cleaning.py.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. delitos_raw: el original tal como se publicó
-- -----------------------------------------------------------------------------
-- Decisión: todas las columnas en TEXT. Así se conserva exactamente lo publicado,
-- incluidos los errores (coordenadas como '7,170,557,382', marcadores como
-- 'ERROR: #N/A'). Si se tiparan aquí, PostgreSQL rechazaría o alteraría esos valores
-- y se perdería la evidencia del diagnóstico. ORDEN es la única excepción: es un
-- entero único (1..135076) y sirve como clave primaria natural.
-- Los nombres se pasan a snake_case ("CLASIFICACIONES DELITO" lleva un espacio).
CREATE TABLE IF NOT EXISTS delitos_raw (
    orden                   INTEGER PRIMARY KEY,
    armas_medios            TEXT NOT NULL,
    barrios_hecho           TEXT NOT NULL,
    latitud                 TEXT NOT NULL,
    longitud                TEXT NOT NULL,
    zona                    TEXT NOT NULL,
    nom_comuna              TEXT NOT NULL,
    ano                     TEXT NOT NULL,
    mes                     TEXT NOT NULL,
    dia                     TEXT NOT NULL,
    dia_semana              TEXT NOT NULL,
    descripcion_conducta    TEXT NOT NULL,
    conducta                TEXT NOT NULL,
    clasificaciones_delito  TEXT NOT NULL,
    curso_de_vida           TEXT NOT NULL,
    estado_civil_persona    TEXT NOT NULL,
    genero                  TEXT NOT NULL,
    movil_agresor           TEXT NOT NULL,
    movil_victima           TEXT NOT NULL
);
COMMENT ON TABLE delitos_raw IS
    'Copia fiel del dataset 75fz-q98y (datos.gov.co, Alcaldía de Bucaramanga). 135.076 filas. Solo lectura.';


-- -----------------------------------------------------------------------------
-- 2. Tablas derivadas: se recrean en cada ejecución
-- -----------------------------------------------------------------------------
-- CASCADE elimina también las vistas de 03_vistas_powerbi.sql que dependen de
-- delitos_limpios; después de recrear las tablas hay que volver a ejecutar ese script.
DROP TABLE IF EXISTS delitos_eliminados CASCADE;
DROP TABLE IF EXISTS delitos_limpios CASCADE;


-- -----------------------------------------------------------------------------
-- 3. delitos_limpios: dataset nuevo para el análisis
-- -----------------------------------------------------------------------------
CREATE TABLE delitos_limpios (
    -- Misma clave que el original: permite volver al registro fuente.
    orden                 INTEGER PRIMARY KEY REFERENCES delitos_raw (orden),

    -- Tiempo. SMALLINT basta para año, mes y día (2 bytes frente a 4 de INTEGER).
    -- fecha_hecho (DATE) se construye a partir de año, mes y día, y permite series de tiempo
    -- y filtros por rango. Los CHECK garantizan que las cuatro columnas sean coherentes entre sí.
    fecha_hecho           DATE     NOT NULL CHECK (fecha_hecho BETWEEN DATE '2010-01-01' AND DATE '2021-12-31'),
    anio                  SMALLINT NOT NULL CHECK (anio BETWEEN 2010 AND 2021),
    mes                   SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    dia                   SMALLINT NOT NULL CHECK (dia BETWEEN 1 AND 31),
    -- dia_semana sigue la norma ISO: 1 = lunes … 7 = domingo. Se recalcula desde la fecha
    -- porque el original tiene días de la semana errados (agosto de 2020).
    dia_semana            SMALLINT NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    dia_semana_nombre     VARCHAR(10) NOT NULL,
    CONSTRAINT ck_fecha_coherente CHECK (
        anio = EXTRACT(YEAR FROM fecha_hecho)
        AND mes = EXTRACT(MONTH FROM fecha_hecho)
        AND dia = EXTRACT(DAY FROM fecha_hecho)
        AND dia_semana = EXTRACT(ISODOW FROM fecha_hecho)
    ),

    -- Espacio. comuna conserva el prefijo numérico del original ('03. SAN FRANCISCO')
    -- para que ordene igual en gráficos y en Power BI. tipo_territorio separa las
    -- 17 comunas urbanas de los 3 corregimientos rurales. Los registros que el original
    -- asigna a otros municipios no entran en esta tabla: están en delitos_eliminados
    -- con motivo FUERA_DEL_MUNICIPIO, porque el estudio se limita a Bucaramanga.
    barrio                VARCHAR(100) NOT NULL,
    comuna                VARCHAR(40)  NOT NULL,
    tipo_territorio       VARCHAR(20)  NOT NULL
        CHECK (tipo_territorio IN ('COMUNA', 'CORREGIMIENTO', 'SIN DATO')),
    zona                  VARCHAR(10)  NOT NULL CHECK (zona IN ('URBANA', 'RURAL', 'OTROS', 'SIN DATO')),
    -- NUMERIC(10,7): 3 dígitos enteros y 7 decimales (precisión de ~1 cm), exacto y sin
    -- errores de redondeo binario. Es NULL cuando no hay coordenada recuperable.
    -- El CHECK limita las coordenadas al área de Bucaramanga.
    latitud               NUMERIC(10,7) CHECK (latitud  BETWEEN 7.0    AND 7.25),
    longitud              NUMERIC(10,7) CHECK (longitud BETWEEN -73.25 AND -73.0),
    CONSTRAINT ck_coord_par CHECK ((latitud IS NULL) = (longitud IS NULL)),

    -- Delito. grupo_delito agrupa las 41 conductas en familias para el análisis.
    descripcion_conducta  VARCHAR(150) NOT NULL,
    conducta              VARCHAR(150) NOT NULL,
    grupo_delito          VARCHAR(40)  NOT NULL,
    clasificacion_delito  VARCHAR(30)  NOT NULL CHECK (clasificacion_delito IN
        ('LESIONES NO FATALES', 'LESIONES FATALES', 'VIOLENCIA SEXUAL', 'SIN DATO')),
    armas_medios          VARCHAR(60)  NOT NULL,
    movil_agresor         VARCHAR(40)  NOT NULL,
    movil_victima         VARCHAR(40)  NOT NULL,

    -- Víctima. Los faltantes se recodifican como la categoría 'SIN DATO' (no se imputan).
    curso_vida            VARCHAR(30)  NOT NULL CHECK (curso_vida IN
        ('01. PRIMERA INFANCIA', '02. INFANCIA', '03. ADOLESCENCIA', '04. JOVENES',
         '05. ADULTEZ', '06. PERSONA MAYOR', 'SIN DATO')),
    estado_civil          VARCHAR(20)  NOT NULL CHECK (estado_civil IN
        ('SOLTERO', 'CASADO', 'UNION LIBRE', 'DIVORCIADO', 'SEPARADO', 'VIUDO', 'SIN DATO')),
    genero                VARCHAR(10)  NOT NULL CHECK (genero IN ('MASCULINO', 'FEMENINO', 'SIN DATO')),

    -- Avisos (flags). Los atípicos y las inconsistencias se marcan, no se borran.
    -- BOOLEAN NOT NULL DEFAULT FALSE: cada aviso es verdadero o falso, nunca desconocido.
    flag_coord_faltante          BOOLEAN NOT NULL DEFAULT FALSE,  -- sin coordenada en el original
    flag_coord_corregida         BOOLEAN NOT NULL DEFAULT FALSE,  -- lat/lon intercambiadas o signo corregido
    flag_coord_fuera_area        BOOLEAN NOT NULL DEFAULT FALSE,  -- coordenada fuera de Bucaramanga, anulada
    flag_dia_semana_corregido    BOOLEAN NOT NULL DEFAULT FALSE,  -- DIA_SEMANA original no coincidía con la fecha
    flag_barrio_comuna           BOOLEAN NOT NULL DEFAULT FALSE,  -- barrio asignado a una comuna poco habitual
    flag_curso_vida_estado_civil BOOLEAN NOT NULL DEFAULT FALSE,  -- ej. primera infancia y casado
    flag_dia_atipico             BOOLEAN NOT NULL DEFAULT FALSE,  -- el día del hecho tiene un conteo extremo
    flag_barrio_atipico          BOOLEAN NOT NULL DEFAULT FALSE   -- el barrio tiene un conteo extremo
);
COMMENT ON TABLE delitos_limpios IS
    'Dataset limpio generado por src/cleaning.py a partir de delitos_raw. Ver docs/decisiones_limpieza.md.';

-- Índices: aceleran los filtros y agrupaciones más frecuentes en la app y en Power BI
-- (por año, comuna, conducta y rango de fechas). La PK ya indexa orden.
CREATE INDEX ix_limpios_anio        ON delitos_limpios (anio);
CREATE INDEX ix_limpios_comuna      ON delitos_limpios (comuna);
CREATE INDEX ix_limpios_conducta    ON delitos_limpios (conducta);
CREATE INDEX ix_limpios_fecha_hecho ON delitos_limpios (fecha_hecho);


-- -----------------------------------------------------------------------------
-- 4. delitos_eliminados: trazabilidad de lo que se quitó
-- -----------------------------------------------------------------------------
-- Cada registro del original que no pasa a delitos_limpios queda aquí con su motivo.
-- Motivos (ver docs/decisiones_limpieza.md):
--   FUERA_DEL_MUNICIPIO  NOM_COMUNA asigna el hecho a otro municipio (fuera del alcance del estudio).
--   DUPLICADO_EXACTO     idéntico a otro registro en todas las columnas salvo ORDEN.
--   ERROR_IRRECUPERABLE  error imposible de corregir que invalida el registro.
-- Un registro tiene un solo motivo: primero se aplica el filtro de alcance y luego la
-- eliminación de duplicados, sobre los registros que quedan.
-- orden_conservado indica, en los duplicados, qué registro del grupo se mantuvo.
CREATE TABLE delitos_eliminados (
    orden             INTEGER PRIMARY KEY REFERENCES delitos_raw (orden),
    motivo            VARCHAR(30) NOT NULL
        CHECK (motivo IN ('FUERA_DEL_MUNICIPIO', 'DUPLICADO_EXACTO', 'ERROR_IRRECUPERABLE')),
    detalle           TEXT,
    orden_conservado  INTEGER REFERENCES delitos_raw (orden),
    fecha_proceso     TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE delitos_eliminados IS
    'Registros del original excluidos de delitos_limpios, con el motivo de cada exclusión.';
