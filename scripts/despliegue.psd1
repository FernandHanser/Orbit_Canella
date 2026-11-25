# Despliegue de ORBIT en el servidor de pruebas 128.1.200.70 (skill caddy-deploy).
# Lo leen scripts\instalar_pruebas.ps1 y scripts\actualizar.ps1, que son iguales en todos los
# proyectos. Aquí va solo lo propio de ORBIT. Ningún secreto: este archivo se versiona.
@{
    Nombre        = 'ORBIT'
    Repositorio   = 'git@github.com:FernandHanser/Orbit_Canella.git'
    Rama          = 'dev'
    Carpeta       = 'C:\ORBIT'

    PuertoInterno = 8001   # el 8000 ya lo usa otro programa en el .70
    PuertoPublico = 8443

    Arranque      = 'serve.py'
    Salud         = '/salud'
    Requisitos    = @('requirements.txt', 'requirements-corte_caja.txt', 'requirements-expedientes_seguros.txt')
    Migraciones   = @('-m', 'flask', '--app', 'wsgi', 'db', 'upgrade')
    RequiereOdbc  = $true

    # .env: el del equipo de desarrollo (misma base de datos), con estos valores para el servidor
    EnvObligatorias = @('DATABASE_URL')
    EnvSecreto      = 'SECRET_KEY'
    Env = @{
        AUTOMATE_ENV          = 'production'
        HOST                  = '127.0.0.1'   # Waitress solo para Caddy
        PORT                  = '8001'        # igual a PuertoInterno
        PROXY_CONFIABLE       = '127.0.0.1'   # IP real del usuario detrás de Caddy
        SESSION_COOKIE_SECURE = '1'
        LOG_DIR               = ''            # la ruta del equipo no existe aquí: logs\ del hub
        CORTE_CAJA_MODO       = 'simulacion'
    }
}
