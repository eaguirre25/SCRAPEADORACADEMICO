# Selecciones semanales de lecturas

Cada selección semanal es **un archivo nuevo** en esta carpeta, con la fecha
como nombre: `AAAA-MM-DD.md` (por ejemplo, `2026-10-11.md`). No hace falta
leer ni modificar ningún otro archivo: el workflow **Generar Dashboard** junta
todas las selecciones en `docs/weekly_reports.json` y las muestra en la
biblioteca («Revisiones e informes» → «Selecciones semanales de lecturas»).

## Formato

El mismo texto del correo, en Markdown:

```markdown
## Selección semanal — 11 de octubre de 2026

Párrafo introductorio (opcional).

1. **Apellido, I., & Apellido, I. (2026). Título del trabajo. _Revista, 12_(3), 45–67. https://doi.org/10.xxxx/yyyy**
DOI: 10.xxxx/yyyy
Por qué importa: explicación.

2. **…**

### Prioridad de lectura
Texto (opcional).
```

- Cada recomendación es un ítem numerado con la referencia APA completa **en negrita**.
- Debajo pueden ir «DOI: …» y la explicación (con o sin «Por qué importa:»).
- Se ignoran las notas «Estado de biblioteca» o «Sincronización».

## Instrucción para la tarea programada de ChatGPT

> Además de enviar el correo, creá en el repositorio `eaguirre25/SCRAPEADORACADEMICO`
> (rama `main`) el archivo `data/weekly_reports/AAAA-MM-DD.md` con la fecha de hoy
> y el mismo texto del correo en Markdown. Es un archivo nuevo: no leas ni modifiques
> `docs/weekly_reports.json` ni ningún otro archivo.
