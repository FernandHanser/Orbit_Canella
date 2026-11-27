# Despliegue de ORBIT en el servidor de pruebas 128.1.200.70 (skill caddy-deploy).
# Lo leen scripts\instalar_pruebas.ps1 y scripts\actualizar.ps1, que son iguales en todos los
# proyectos. Aquí va solo lo propio de ORBIT. Ningún secreto: este archivo se versiona.
@{
    Nombre        = 'ORBIT'
    Repositorio   = 'git@github.com:FernandHanser/Orbit_Canella.git'
    Rama          = 'dev'
    Carpeta       = 'C:\ORBIT'

    # Preferidos: si están ocupados, instalar_pruebas.ps1 toma el siguiente libre y lo anota en
    # el sitio de Caddy (en el .70 el 8000 está ocupado: queda en 8001)
    PuertoInterno = 8000
    PuertoPublico = 8443

    PythonMinimo  = '3.11'   # el instalador busca el más nuevo que cumpla (en el .70 el del PATH es 3.10)
    Arranque      = 'serve.py'
    Salud         = '/salud'
    Requisitos    = @('requirements.txt', 'requirements-corte_caja.txt', 'requirements-expedientes_seguros.txt')
    Migraciones   = @('-m', 'flask', '--app', 'wsgi', 'db', 'upgrade')
    RequiereOdbc  = $true

    # .env: el del equipo de desarrollo (misma base de datos), con estos valores para el servidor
    EnvObligatorias = @('DATABASE_URL')
    EnvSecreto      = 'SECRET_KEY'
    EnvPuerto       = 'PORT'          # el script le pone el puerto interno elegido
    Env = @{
        AUTOMATE_ENV          = 'production'
        HOST                  = '127.0.0.1'   # Waitress solo para Caddy
        PROXY_CONFIABLE       = '127.0.0.1'   # IP real del usuario detrás de Caddy
        SESSION_COOKIE_SECURE = '1'
        LOG_DIR               = ''            # la ruta del equipo no existe aquí: logs\ del hub
    }
}
