# Guía Técnica de Despliegue (Desde Cero)

## 1) Supabase
1. Crear un proyecto en Supabase.
2. Ir a **SQL Editor** y ejecutar el script `supabase_schema.sql`.
3. En **Project Settings → API**, copiar:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`

## 2) Backend (Render)
1. Crear un nuevo servicio Web en Render.
2. Conectar el repo: `https://github.com/bolivianotech/consulta-aulas-upds`.
3. Configurar:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py` (o `gunicorn app:app` si lo habilitas)
4. Variables de entorno:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
5. Desplegar.

## 3) Frontend (GitHub Pages)
1. En el repo, habilitar GitHub Pages:
   - Source: `main` / `/` (root).
2. Verifica que la URL pública funcione:
   - `https://bolivianotech.github.io/consulta-aulas-upds/`
3. El panel admin es:
   - `https://bolivianotech.github.io/consulta-aulas-upds/adminupds.html`

## 4) Primer cargado de datos
1. Abrir el panel admin.
2. Subir `rptListadorGeneral_del_Sistema.xlsx`.
3. Verificar estadísticas.

## 5) Cold Start en Render (cron-job.org)
Para evitar que el servicio entre en sleep:
1. Crear una cuenta en cron-job.org.
2. Crear un nuevo job (cronjob).
3. Configurar el job para hacer un **HTTP GET** a:
   - `https://consulta-aulas-upds.onrender.com/api/health`
4. Programar el job cada 10-12 minutos.
5. Guardar el job y ejecutar un test run.

Notas:
- cron-job.org permite ejecutar jobs hasta una vez por minuto y configurar requests HTTP personalizados.
- Render recomienda tener un endpoint de health check que responda con 2xx/3xx para verificar disponibilidad.

## 6) Auditoría
La tabla `auditlog` guarda:
- Acción
- Fecha/hora
- User-Agent del navegador
- Valores anteriores y nuevos

## 7) QR de acceso
El QR de acceso se encuentra en `qr_consulta.html` y apunta a:
`https://bolivianotech.github.io/consulta-aulas-upds/`

