-- =============================================================================
-- 02_carga_verificacion.sql
-- Verificación de la carga en Neon. Puede ejecutarse en el editor SQL de Neon o con
--   python -m src.load verificar
-- Cada consulta devuelve una columna "estado" con OK o ERROR.
-- =============================================================================

-- 1. El original quedó completo en delitos_raw
SELECT COUNT(*) AS filas_raw,
       135076   AS esperado,
       CASE WHEN COUNT(*) = 135076 THEN 'OK' ELSE 'ERROR' END AS estado
FROM delitos_raw;

-- 2. limpios + eliminados = original
SELECT (SELECT COUNT(*) FROM delitos_limpios)    AS filas_limpios,
       (SELECT COUNT(*) FROM delitos_eliminados) AS filas_eliminados,
       (SELECT COUNT(*) FROM delitos_limpios) + (SELECT COUNT(*) FROM delitos_eliminados) AS suma,
       CASE WHEN (SELECT COUNT(*) FROM delitos_limpios) + (SELECT COUNT(*) FROM delitos_eliminados) = 135076
            THEN 'OK' ELSE 'ERROR' END AS estado;

-- 3. Ningún registro está a la vez en limpios y eliminados, y ninguno se perdió
SELECT (SELECT COUNT(*) FROM delitos_limpios l JOIN delitos_eliminados e USING (orden)) AS en_ambas,
       (SELECT COUNT(*) FROM delitos_raw r
         WHERE NOT EXISTS (SELECT 1 FROM delitos_limpios l WHERE l.orden = r.orden)
           AND NOT EXISTS (SELECT 1 FROM delitos_eliminados e WHERE e.orden = r.orden)) AS sin_destino,
       CASE WHEN (SELECT COUNT(*) FROM delitos_limpios l JOIN delitos_eliminados e USING (orden)) = 0
             AND (SELECT COUNT(*) FROM delitos_raw r
                   WHERE NOT EXISTS (SELECT 1 FROM delitos_limpios l WHERE l.orden = r.orden)
                     AND NOT EXISTS (SELECT 1 FROM delitos_eliminados e WHERE e.orden = r.orden)) = 0
            THEN 'OK' ELSE 'ERROR' END AS estado;

-- 4. Registros eliminados por motivo
SELECT motivo, COUNT(*) AS registros
FROM delitos_eliminados
GROUP BY motivo
ORDER BY registros DESC;

-- 5. Conteo por año: original vs. limpio vs. eliminado
-- Se une por ORDEN, así la comparación no depende de cómo se recodificó cada columna.
SELECT r.ano                                AS anio,
       COUNT(*)                             AS raw,
       COUNT(l.orden)                       AS limpios,
       COUNT(e.orden)                       AS eliminados,
       CASE WHEN COUNT(*) = COUNT(l.orden) + COUNT(e.orden) THEN 'OK' ELSE 'ERROR' END AS estado
FROM delitos_raw r
LEFT JOIN delitos_limpios    l ON l.orden = r.orden
LEFT JOIN delitos_eliminados e ON e.orden = r.orden
GROUP BY r.ano
ORDER BY r.ano;

-- 6. Conteo por conducta: original vs. limpio vs. eliminado
SELECT r.conducta                           AS conducta_original,
       COUNT(*)                             AS raw,
       COUNT(l.orden)                       AS limpios,
       COUNT(e.orden)                       AS eliminados,
       CASE WHEN COUNT(*) = COUNT(l.orden) + COUNT(e.orden) THEN 'OK' ELSE 'ERROR' END AS estado
FROM delitos_raw r
LEFT JOIN delitos_limpios    l ON l.orden = r.orden
LEFT JOIN delitos_eliminados e ON e.orden = r.orden
GROUP BY r.conducta
ORDER BY raw DESC;
