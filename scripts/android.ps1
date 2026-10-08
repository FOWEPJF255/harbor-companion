param(
    [Parameter(Mandatory = $true)][string]$BackendUrl,
    [ValidateSet('prepare', 'debug', 'open')][string]$Mode = 'prepare'
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskMobile = Join-Path $taskRoot 'mobile'
$taskWeb = Join-Path $taskRoot 'web'
$taskBackendUri = $null
if (-not [Uri]::TryCreate($BackendUrl, [UriKind]::Absolute, [ref]$taskBackendUri) -or
    $taskBackendUri.Scheme -ne 'https' -or
    $taskBackendUri.UserInfo -or $taskBackendUri.Query -or $taskBackendUri.Fragment -or
    $taskBackendUri.Host -in @('localhost', '127.0.0.1', '::1')) {
    throw 'Provide an HTTPS backend base URL reachable from the phone, without credentials, query, or fragment. Do not use localhost.'
}

$taskPreviousBase = $env:VITE_API_BASE_URL
try {
    # This is a public service address, never a model key or a compiled user token.
    $env:VITE_API_BASE_URL = $BackendUrl.TrimEnd('/')
    Push-Location $taskWeb
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Web dependencies could not be installed.' }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
    } finally { Pop-Location }

    Push-Location $taskMobile
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Mobile dependencies could not be installed.' }
        & npx cap sync android
        if ($LASTEXITCODE -ne 0) { throw 'Android sync failed.' }
        if ($Mode -eq 'open') {
            & npx cap open android
            if ($LASTEXITCODE -ne 0) { throw 'Android Studio could not be opened.' }
        } elseif ($Mode -eq 'debug') {
            if (-not (Get-Command java -ErrorAction SilentlyContinue) -and -not $env:JAVA_HOME) {
                throw 'Android packaging requires a JDK. Use the JDK bundled with Android Studio; no SDK is installed by this script.'
            }
            Push-Location (Join-Path $taskMobile 'android')
            try {
                & .\gradlew.bat assembleDebug
                if ($LASTEXITCODE -ne 0) { throw 'Debug APK build failed. Configure the Android SDK and JDK first.' }
                Write-Output 'Debug APK: mobile/android/app/build/outputs/apk/debug/app-debug.apk'
            } finally { Pop-Location }
        } else {
            Write-Output 'Android project synchronized. No APK was compiled.'
        }
    } finally { Pop-Location }
} finally {
    $env:VITE_API_BASE_URL = $taskPreviousBase
}
