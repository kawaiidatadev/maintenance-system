# setuph.ps1
param(
    [string]$InstallDir,
    [switch]$Uninstall
)

if ($Uninstall) {
    Write-Host Desinstalando Sistema de Mantenimiento... -ForegroundColor Yellow
    Set-Location $InstallDir
    docker-compose down -v 2$null
    Write-Host ✅ Desinstalación completada. -ForegroundColor Green
    exit 0
}

Write-Host
Write-Host ========================================== -ForegroundColor Cyan
Write-Host   SISTEMA DE GESTIÓN DE MANTENIMIENTO -ForegroundColor Cyan
Write-Host   Configuración automática -ForegroundColor Cyan
Write-Host ========================================== -ForegroundColor Cyan
Write-Host

# Agregar regla al firewall para permitir acceso en red
netsh advfirewall firewall add rule name=Sistema Mantenimiento dir=in action=allow protocol=TCP localport=5001 2$null

# Cambiar al directorio de instalación
Set-Location $InstallDir

# Crear archivo .env si no existe
$envFile = Join-Path $InstallDir .env
if (-not (Test-Path $envFile)) {
    $secretKey = -join ((48..122)  Get-Random -Count 32  % {[char]$_})
    @
SECRET_KEY=$secretKey
BREVO_API_KEY=
BREVO_FROM_EMAIL=
BREVO_FROM_NAME=Sistema de Mantenimiento
@  Out-File -FilePath $envFile -Encoding utf8
    Write-Host ✅ Archivo .env creado -ForegroundColor Green
}

# Solicitar datos del administrador
Write-Host 📝 Configuración del administrador -ForegroundColor Yellow
Write-Host

$adminUser = Read-Host   Nombre de usuario (admin)
if (-not $adminUser) { $adminUser = admin }

$adminEmail = Read-Host   Correo electrónico
while ($adminEmail -notmatch '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}$') {
    Write-Host   ❌ Correo inválido. Intenta de nuevo. -ForegroundColor Red
    $adminEmail = Read-Host   Correo electrónico
}

$adminPassword = Read-Host   Contraseña -AsSecureString
$adminPassword2 = Read-Host   Confirmar contraseña -AsSecureString

$BSTR = [System.Runtime.InteropServices.Marshal]SecureStringToBSTR($adminPassword)
$adminPasswordPlain = [System.Runtime.InteropServices.Marshal]PtrToStringAuto($BSTR)
$BSTR2 = [System.Runtime.InteropServices.Marshal]SecureStringToBSTR($adminPassword2)
$adminPassword2Plain = [System.Runtime.InteropServices.Marshal]PtrToStringAuto($BSTR2)

if ($adminPasswordPlain -ne $adminPassword2Plain) {
    Write-Host ❌ Las contraseñas no coinciden. El instalador se cancelará. -ForegroundColor Red
    exit 1
}

$companyName = Read-Host   Nombre de la empresa

# Guardar variables temporales
@
ADMIN_USER=$adminUser
ADMIN_EMAIL=$adminEmail
ADMIN_PASSWORD=$adminPasswordPlain
COMPANY_NAME=$companyName
@  Out-File -FilePath $envTEMPmaintenance_env.txt -Encoding utf8

# Construir y levantar contenedores
Write-Host
Write-Host 🚀 Instalando y levantando el sistema... -ForegroundColor Yellow
docker-compose up --build -d

Write-Host ⏳ Esperando a que la base de datos esté lista... -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Crear usuario administrador dentro del contenedor usando las variables
Write-Host 👤 Creando usuario administrador personalizado... -ForegroundColor Yellow
docker exec -i maintenance_web python -c @
import os
from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

admin_user = os.environ.get('ADMIN_USER', 'admin')
admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
company_name = os.environ.get('COMPANY_NAME', 'Mi Empresa')

app = create_app()
with app.app_context()
    if not User.query.filter_by(username=admin_user).first()
        user = User(
            username=admin_user,
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            role='admin',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        print(f'✅ Usuario administrador creado {admin_user}')

    from app.models.setting import Setting
    Setting.set('company_name', company_name)
    print(f'✅ Nombre de empresa guardado {company_name}')
@

# Obtener IP local para acceso en red
function Get-LocalIP {
    $ip = Get-NetIPAddress -AddressFamily IPv4  Where-Object {
        $_.InterfaceAlias -notlike Loopback -and
        $_.InterfaceAlias -notlike Virtual -and
        $_.PrefixOrigin -ne WellKnown
    }  Select-Object -First 1
    return $ip.IPAddress
}
$localIP = Get-LocalIP

# Crear acceso directo en el escritorio con la IP dinámica
$desktopPath = [Environment]GetFolderPath(Desktop)
$shortcutPath = Join-Path $desktopPath Sistema de Mantenimiento.url

@
[InternetShortcut]
URL=http${localIP}5001
IconFile=CWindowsSystem32SHELL32.dll
IconIndex=42
@  Out-File -FilePath $shortcutPath -Encoding ascii

Write-Host
Write-Host ========================================== -ForegroundColor Green
Write-Host 🎉 ¡INSTALACIÓN COMPLETADA! -ForegroundColor Green
Write-Host ========================================== -ForegroundColor Green
Write-Host
Write-Host 📌 Acceso desde ESTA computadora -ForegroundColor White
Write-Host    httplocalhost5001 -ForegroundColor Cyan
Write-Host
Write-Host 📌 Acceso desde OTROS dispositivos en la RED -ForegroundColor White
Write-Host    http$localIP`5001 -ForegroundColor Yellow
Write-Host
Write-Host 📁 Se ha creado un acceso directo en el escritorio. -ForegroundColor Green
Write-Host
Write-Host 🔗 Abriendo el sistema en tu navegador... -ForegroundColor Yellow
Start-Process httplocalhost5001

Write-Host
Write-Host ✅ El sistema está corriendo en segundo plano. -ForegroundColor Green
Write-Host 🛑 Para detenerlo, ejecuta 'docker-compose down' en la carpeta de instalación. -ForegroundColor Yellow
Write-Host