# Academic Scraper for School Management Research

Este repositorio contiene un script en Python que recolecta trabajos académicos
relacionados con **dirección escolar** y **gestión escolar** a partir de repositorios
públicos accesibles a través de la API de OpenAlex.  La finalidad es mantener
actualizado un catálogo de publicaciones desde 2020 hasta la fecha y enviar un
informe diario por correo electrónico con las nuevas incorporaciones.

## ¿Qué hace el script?

1. **Búsqueda en OpenAlex** – Utiliza la API pública de OpenAlex para
   realizar búsquedas de texto sobre varios términos relacionados con
   dirección/gestión escolar.  La consulta se filtra para recuperar obras
   publicadas desde el 1 de enero de 2020.  Los resultados incluyen el título,
   año de publicación, DOI y un enlace al recurso.

2. **Base de datos local** – Guarda la lista de DOI ya registrados en
   `data/scraped_records.json` para que en futuras ejecuciones sólo se
   consideren artículos nuevos.  Este archivo se actualiza automáticamente
   después de cada ejecución.

3. **Informe diario por correo electrónico** – Si se encuentran nuevos
   artículos, el script genera un resumen en formato de texto y envía un
   correo electrónico al destinatario indicado con los detalles de las
   publicaciones recientes.  El envío se realiza a través del servidor SMTP
   de Gmail utilizando credenciales almacenadas como variables de entorno.

4. **Ejecución programada en GitHub Actions** – El flujo de trabajo
   `/.github/workflows/daily-scraper.yml` ejecuta el script a diario a una
   hora predefinida.  Se recomienda configurar los secretos del repositorio
   para **GMAIL_USER**, **GMAIL_APP_PASSWORD** y **RECIPIENT_EMAIL**.

## Cómo empezar

1. **Clonar y preparar el entorno**

   ```bash
   git clone https://github.com/tu-usuario/academic-scraper.git
   cd academic-scraper
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configurar variables de entorno**

   El script utiliza tres variables de entorno para enviar el correo:

   - `GMAIL_USER`: dirección de Gmail desde la cual se enviarán los correos.
   - `GMAIL_APP_PASSWORD`: contraseña de aplicación generada en Gmail (no uses
     tu contraseña de acceso directa; genera una contraseña de aplicación en
     https://myaccount.google.com/apppasswords si tienes activada la verificación
     en dos pasos).
   - `RECIPIENT_EMAIL`: dirección de correo electrónico que recibirá los
     informes diarios.

   Puedes exportar estas variables en tu sesión o definirlas en los secretos
   del repositorio cuando utilices GitHub Actions.

   ```bash
   export GMAIL_USER="tu_usuario@gmail.com"
   export GMAIL_APP_PASSWORD="contraseña_de_aplicación"
   export RECIPIENT_EMAIL="destinatario@ejemplo.com"
   ```

3. **Ejecutar el scraper manualmente**

   ```bash
   python main.py
   ```

   La primera ejecución descargará todos los artículos desde 2020, guardará los
   datos en `data/scraped_records.json` y enviará un correo con el informe.  Las
   ejecuciones posteriores buscarán nuevos artículos y enviarán un informe
   únicamente si se encuentran novedades.

## Configuración de GitHub Actions

Este repositorio incluye un flujo de trabajo ubicado en
`.github/workflows/daily-scraper.yml` que programa la ejecución diaria del
script.  Para activarlo es necesario:

1. **Crear un repositorio en GitHub** – Sube estos archivos a tu cuenta de
   GitHub.
2. **Definir los secretos** – En la configuración del repositorio en GitHub,
   selecciona **Settings → Secrets and variables → Actions** y agrega los
   siguientes secretos:
   - `GMAIL_USER`
   - `GMAIL_APP_PASSWORD`
   - `RECIPIENT_EMAIL`
3. **Activar las acciones** – Una vez que los secretos estén definidos, GitHub
   Actions ejecutará el flujo de trabajo en el horario especificado en el
   archivo YAML (puedes modificar la cron para adaptarla a tu zona horaria).

## Créditos y licencias

Los datos recopilados provienen de la API de OpenAlex, que distribuye su
contenido bajo licencia CC0 (dominio público)【280946531337324†L250-L346】.  Este proyecto está liberado bajo
licencia MIT y puede adaptarse libremente para fines académicos o de
investigación.
