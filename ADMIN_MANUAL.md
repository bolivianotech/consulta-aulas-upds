# Manual del Panel de Administración (UPDS)

## Acceso
- URL de acceso público: `https://bolivianotech.github.io/consulta-aulas-upds/`
- El panel de administración es `adminupds.html` dentro del mismo sitio.

## Funciones principales
- Carga de Excel (reemplaza datos)
- Crear, editar y eliminar registros
- Exportar respaldo en JSON
- Advertencia de sesiones concurrentes

## Cargar archivo Excel
1. En la sección **Cargar Archivo Excel**, arrastra o selecciona el archivo `rptListadorGeneral_del_Sistema.xlsx`.
2. El sistema valida el formato según el reporte **LISTADO GENERAL POR GRUPOS**.
3. Al finalizar, verás las estadísticas de carga.

Nota: esta operación reemplaza todos los datos en la base.

## Crear un registro
1. Presiona **Nuevo**.
2. Completa los campos obligatorios.
3. Presiona **Guardar**.

## Editar un registro
1. En la tabla, presiona el botón de editar (✏️).
2. Modifica los campos necesarios.
3. Presiona **Guardar**.

## Eliminar un registro
1. En la tabla, presiona el botón de eliminar (🗑️).
2. Confirma la eliminación.

## Exportar respaldo
1. Presiona **Exportar Backup**.
2. Se descarga un archivo JSON con el estado actual.

## Advertencia de sesiones concurrentes
Si hay más de 2 sesiones activas, aparece una advertencia. 
Esto no bloquea cambios, pero se recomienda esperar para evitar conflictos.

## Auditoría (Auditlog)
Cada cambio registra:
- Acción (crear, actualizar, eliminar, upload Excel)
- Fecha y hora
- Navegador (user-agent)
- Valores anteriores y nuevos

