-- =============================================================================
-- 03_vistas_powerbi.sql
-- Vistas para el tablero de Power BI: un modelo en estrella sobre delitos_limpios.
--
--   vw_fact_delitos      hechos: un registro por delito, con las claves de cada dimensión
--   vw_dim_tiempo        calendario completo 2010–2021 (tabla de fechas de Power BI)
--   vw_dim_territorio    barrio y comuna
--   vw_dim_conducta      conducta, grupo de delito y clasificación
--   vw_dim_victima       combinación de género, curso de vida y estado civil
--
-- Decisiones de diseño:
--   * Vistas y no tablas: no duplican datos; si se recarga delitos_limpios, el tablero se actualiza.
--   * Claves de texto (por ejemplo, 'comuna | barrio'): estables entre recargas y legibles al depurar
--     las relaciones en Power BI; no requieren secuencias ni tablas adicionales.
--   * La dimensión de tiempo se genera con generate_series para incluir los días sin registros:
--     la inteligencia de tiempo de DAX necesita un calendario continuo.
--   * Solo lectura: Power BI no necesita escribir. Al final hay un rol opcional de solo lectura.
--
-- Ejecución: en el editor SQL de Neon, o con psql. Debe ejecutarse después de 01_schema.sql
-- (01_schema.sql elimina estas vistas al recrear delitos_limpios, por el CASCADE).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Dimensión de tiempo
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_dim_tiempo AS
SELECT
    d::date                                                   AS fecha,
    EXTRACT(YEAR FROM d)::int                                 AS anio,
    EXTRACT(QUARTER FROM d)::int                              AS trimestre,
    EXTRACT(MONTH FROM d)::int                                AS mes,
    (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',
           'Septiembre','Octubre','Noviembre','Diciembre'])[EXTRACT(MONTH FROM d)::int] AS mes_nombre,
    to_char(d, 'YYYY-MM')                                     AS anio_mes,
    EXTRACT(DAY FROM d)::int                                  AS dia,
    EXTRACT(ISODOW FROM d)::int                               AS dia_semana,
    (ARRAY['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'])[EXTRACT(ISODOW FROM d)::int]
                                                              AS dia_semana_nombre,
    EXTRACT(ISODOW FROM d) IN (6, 7)                          AS fin_de_semana
FROM generate_series(DATE '2010-01-01', DATE '2021-12-31', INTERVAL '1 day') AS d;

-- -----------------------------------------------------------------------------
-- Dimensión de territorio
-- -----------------------------------------------------------------------------
-- Un mismo barrio puede aparecer en más de una comuna (inconsistencia marcada con
-- flag_barrio_comuna), por eso la clave combina comuna y barrio.
CREATE OR REPLACE VIEW vw_dim_territorio AS
SELECT DISTINCT
    comuna || ' | ' || barrio                                 AS territorio_key,
    comuna,
    barrio,
    tipo_territorio,
    CASE WHEN comuna ~ '^[0-9]{2}\. ' THEN substring(comuna FROM 1 FOR 2)::int END AS comuna_numero
FROM delitos_limpios;

-- -----------------------------------------------------------------------------
-- Dimensión de conducta
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_dim_conducta AS
SELECT DISTINCT
    conducta                                                  AS conducta_key,
    conducta,
    descripcion_conducta,
    grupo_delito,
    clasificacion_delito
FROM delitos_limpios;

-- -----------------------------------------------------------------------------
-- Dimensión de víctima
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_dim_victima AS
SELECT DISTINCT
    genero || ' | ' || curso_vida || ' | ' || estado_civil   AS victima_key,
    genero,
    curso_vida,
    estado_civil
FROM delitos_limpios;

-- -----------------------------------------------------------------------------
-- Hechos
-- -----------------------------------------------------------------------------
-- Las columnas de bajo número de categorías que no forman una dimensión propia (zona, arma, móviles)
-- quedan en la tabla de hechos. Se incluyen las coordenadas para el visual de mapa y los avisos
-- de la limpieza para poder filtrar atípicos e inconsistencias.
CREATE OR REPLACE VIEW vw_fact_delitos AS
SELECT
    orden,
    fecha_hecho,
    comuna || ' | ' || barrio                                 AS territorio_key,
    conducta                                                  AS conducta_key,
    genero || ' | ' || curso_vida || ' | ' || estado_civil   AS victima_key,
    zona,
    armas_medios,
    movil_agresor,
    movil_victima,
    latitud,
    longitud,
    flag_coord_faltante,
    flag_dia_atipico,
    flag_barrio_atipico,
    flag_barrio_comuna
FROM delitos_limpios;

COMMENT ON VIEW vw_fact_delitos  IS 'Hechos para Power BI: un registro por delito del conjunto limpio.';
COMMENT ON VIEW vw_dim_tiempo    IS 'Calendario continuo 2010–2021 (marcar como tabla de fechas en Power BI).';

-- -----------------------------------------------------------------------------
-- Verificación: cada vista de dimensión tiene una sola fila por clave y los hechos cuadran
-- -----------------------------------------------------------------------------
SELECT 'vw_fact_delitos' AS vista, COUNT(*) AS filas, COUNT(DISTINCT orden) AS claves_distintas FROM vw_fact_delitos
UNION ALL SELECT 'vw_dim_tiempo', COUNT(*), COUNT(DISTINCT fecha) FROM vw_dim_tiempo
UNION ALL SELECT 'vw_dim_territorio', COUNT(*), COUNT(DISTINCT territorio_key) FROM vw_dim_territorio
UNION ALL SELECT 'vw_dim_conducta', COUNT(*), COUNT(DISTINCT conducta_key) FROM vw_dim_conducta
UNION ALL SELECT 'vw_dim_victima', COUNT(*), COUNT(DISTINCT victima_key) FROM vw_dim_victima;

-- -----------------------------------------------------------------------------
-- (Opcional) Rol de solo lectura para Power BI
-- -----------------------------------------------------------------------------
-- Ejecutar una sola vez, reemplazando la contraseña por una generada en el momento. La contraseña
-- se escribe solo aquí, en el editor de Neon, y nunca se guarda en el repositorio.
--
-- CREATE ROLE powerbi_lector WITH LOGIN PASSWORD '<contraseña-segura>';
-- GRANT CONNECT ON DATABASE <nombre_bd> TO powerbi_lector;
-- GRANT USAGE ON SCHEMA public TO powerbi_lector;
-- GRANT SELECT ON vw_fact_delitos, vw_dim_tiempo, vw_dim_territorio, vw_dim_conducta, vw_dim_victima
--     TO powerbi_lector;
