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
1. Crear una cuenta en https://cron-job.org
2. Crear un nuevo job con la URL:
   - `https://consulta-aulas-upds.onrender.com/api/health`
3. Programar cada 5 o 10 minutos.
4. Guardar.

Recomendación: usar intervalo de 5 minutos en horas de alta demanda.

## 6) Auditoría
La tabla `auditlog` guarda:
- Acción
- Fecha/hora
- User-Agent del navegador
- Valores anteriores y nuevos

## 7) QR de acceso
El QR de acceso se encuentra en `qr_consulta.html` y apunta a:
`https://bolivianotech.github.io/consulta-aulas-upds/`

