$certPath = (Resolve-Path "$PSScriptRoot\certs\cert.crt").Path
Write-Host "Importing certificate: $certPath"
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certPath)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
$store.Add($cert)
$store.Close()
Write-Host "SUCCESS: Certificate added to Windows Trusted Root Authorities."
