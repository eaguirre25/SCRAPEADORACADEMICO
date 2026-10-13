# Auditoría de modelos y recomendaciones — 13/10/2026

**Necesita revisión. Cobertura parcial.** Se corrigieron errores comprobados sin reentrenar modelos. Inventario acotado: BERTopic principal, tres STM por idioma, comparación entre modelos y recomendaciones semanales. Los denominadores siguientes son componentes de ese inventario; no equivalen a una verificación completa de todos los controles del sitio.

## Calidad y utilidad
| Category | Observed defects | Assessment |
|---|---|---|
| Utilidad y completitud | 3 / 3 | Las tres preguntas (validez BERTopic, validez STM, recepción semanal) conservan pendientes: revisión humana, convergencia y entregas ausentes. |
| Claridad analítica | 1 / 3 | Se aclararon alcance de metadatos y estados exploratorios; evaluación BERTopic conserva exportación incompleta. |
| Consistencia visual e interacción | desconocido | No se inventaría un total de controles: revisión visual posterior al despliegue limitada a la sección modificada. |

## Corrección y robustez
| Category | Observed defects | Assessment |
|---|---|---|
| Autoridad y confianza de fuentes | 4 / 4 | Los cuatro modelos actuales carecen de validación humana; el corpus exacto necesario para reproducir la evaluación no está versionado. |
| Exactitud de valores | 4 / 5 | Estabilidad BERTopic corregida y comparación corregida. Persisten evaluación incompleta BERTopic y réplicas STM no convergentes (tres idiomas). |
| Acuerdo dentro de gráficos | 0 / 5 | Sin contradicción numérica observada en cuatro vistas de modelos y comparación; no certifica cada gráfico. |
| Detalles completos de fuentes | N/A | El sitio no presenta las superficies de detalle de fuentes del producto Data. Se inspeccionaron código y CSV del repositorio. |
| Consistencia entre componentes | 2 / 3 | Grupos: resultados/evaluación, comparación, tarea/entregas. Evaluación incompleta y entregas ausentes continúan pendientes. |
| Controles de calidad de datos | 4 / 4 | Los cuatro modelos requieren revisar elegibilidad e idiomas antes de nuevo ajuste. La deduplicación del catálogo no reemplaza esa revisión. |
| Apoyo de conclusiones | 2 / 2 | BERTopic y STM permiten exploración; no se certifican resultados definitivos. |

## Hallazgos y medidas

1. **BERTopic:** ajuste del 10/10: 7596 publicaciones; 33 temas; 3284 sin tema (43,23%). Corregido promedio que incluía semilla42 contra sí misma: ARI 0,807178 → 0,758972; NMI 0,872364 → 0,840456; Jaccard 0,750031 → 0,687538. Cuatro comparaciones independientes, cinco ajustes. S2 sigue preferido.
2. **Evaluación incompleta:** código recorría14 temas pese a existir33. Corregido recorrido y notas. CSV enriquecidos de heterogeneidad e idioma todavía contienen14: regeneración pendiente con corpus compatible. No sustituirlos por métricas de otra versión. Revisión humana disponible corresponde al modelo histórico de julio.
3. **STM:** ES2746 documentos/K20, EN3805/K20, PT998/K5. Estabilidad aproximada0,288/0,344/0,324. Réplicas no convergentes en los tres; falta registrar convergencia del ajuste final. No se afirma que el ajuste final también falló. Muestras muestran textos turcos en ES y españoles en EN; detector restringido a cuatro idiomas sin rechazo de desconocidos. Revisar corpus e idiomas y reentrenar con evaluación convergente.
4. **Comparación:** corregidos45 alineamientos que trataban BERTopic−1 como tema. Se conservan7549 documentos compartidos;3258 sin tema auditados por separado. Ahora1390 alineamientos temáticos, ninguno con−1. Tabla identifica modelo e idioma STM. Red documental usa palabras clave y simulación de fuerzas; distancia en pantalla no demuestra semejanza semántica de embeddings.
5. **Recomendaciones:** seis entregas/60 ítems, última20/09. No constan27/09,04/10,11/10. Tarea activa domingos20h Buenos Aires, registra última ejecución11/10: no demuestra envío ni persistencia. Prompt corregido para crear data/weekly_reports/AAAA-MM-DD.json y verificar lectura, preservando archivos previos; docs/weekly_reports.json se genera. No se alteró horario. En correos consultados no se encontraron entregas posteriores; no se inventan ni se recuperan contenidos inexistentes. Las recomendaciones se muestran en biblioteca, pero no existe incorporación automática a master_records ni descarga a Drive.

## Validación
Pruebas del repositorio y control de integridad del dashboard. Sin reentrenamiento ni cambios en documentos originales.

## Referencias metodológicas
Grootendorst, M. (2022). *BERTopic: Neural topic modeling with a class-based TF-IDF procedure*. https://doi.org/10.48550/arXiv.2203.05794

Roberts, M. E., Stewart, B. M., & Tingley, D. (2019). stm: An R package for structural topic models. *Journal of Statistical Software, 91*(2), 1–40. https://doi.org/10.18637/jss.v091.i02

## Continuación de la revisión

Se verificaron los32 documentos del STM español T17 con el detector corregido:19 turcos,12 ingleses y1 español. Es una revisión de ese grupo; no una tasa estimada para todo el corpus. Ejemplos DOI10.29228/asrjournal.71516,10.29228/asrjournal.66776 y10.7827/turkishstudies.52134.

Correcciones para el nuevo ajuste:
- Detector abierto a todos los idiomas disponibles, con rechazo de decisiones ambiguas; se usa primero el resumen cuando tiene suficiente texto. Idiomas no admitidos permanecen en la biblioteca y pasan al registro de exclusiones del corpus analítico.
- STM prioriza candidatos con estabilidad disponible y al menos80% de réplicas convergentes. La estabilidad se calcula sobre réplicas convergentes; si ninguna solución cumple, queda exploratoria. El máximo de iteraciones de réplicas pasa de150 a500; esto no garantiza convergencia.
- Se registra convergencia del ajuste final y la trayectoria de su objetivo.
- Evaluación pasa a ser requisito para publicar resultados: no se ignoran sus errores. Se conserva una copia comprimida del corpus de metadatos usado por el ajuste.
- Las pruebas R se ejecutan antes del entrenamiento. Pruebas locales de idiomas/corpus/comparación pasan; la sintaxis R se validó con un parser. La ejecución de pruebas R y del nuevo entrenamiento queda pendiente en GitHub Actions; R no está disponible localmente.

La validación documental e interpretación de los temas actuales sigue pendiente. Una corrección del código no equivale a validar científicamente los modelos.
