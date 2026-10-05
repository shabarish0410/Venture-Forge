$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$workspacePath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\')
$archivePath = Join-Path $workspacePath 'archive'
New-Item -ItemType Directory -Path $archivePath -Force | Out-Null
if (@(Get-ChildItem -LiteralPath $archivePath -Filter 'agents-office-reference-*.zip.manifest.json').Count) {
    Write-Output 'Legacy cleanup was already completed. Refusing to archive the current application files.'
    exit
}
$names = @('.vscode', 'assets', 'brain', 'dist', 'mcp-servers', 'scripts', 'skills', 'src', 'build.mjs', 'CHANGELOG.md', 'check.mjs', 'CLAUDE.md', 'config.mjs', 'graph-build.mjs', 'learn.mjs', 'LICENSE', 'mcp.mjs', 'office.agents.json', 'office.config.json', 'onboard.mjs', 'package-lock.json', 'package.json', 'README.md', 'roster.mjs', 'routines.mjs', 'serve.mjs', 'setup', 'SKILLS.md', 'skills.mjs', 'teams.mjs', 'usage.mjs', '.gitignore')
$targets = @()
$files = @()
foreach ($name in $names) {
    $targetPath = [IO.Path]::GetFullPath((Join-Path $workspacePath $name))
    if (-not $targetPath.StartsWith($workspacePath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Target escapes workspace.' }
    if (-not (Test-Path -LiteralPath $targetPath)) { continue }
    $target = Get-Item -LiteralPath $targetPath -Force
    if ($target.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked target: $name" }
    $targets += $targetPath
    if ($target.PSIsContainer) {
        $items = @(Get-ChildItem -LiteralPath $targetPath -Recurse -Force)
        if (@($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Refusing linked contents: $name" }
        $files += @($items | Where-Object { -not $_.PSIsContainer })
    } else { $files += $target }
}
if (-not $targets.Count) { Write-Output 'No legacy targets remain.'; exit }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$zipPath = Join-Path $archivePath "agents-office-reference-$stamp.zip"
$manifest = @()
$zip = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        $entryName = $file.FullName.Substring($workspacePath.Length + 1).Replace('\', '/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $entryName, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
        $manifest += [pscustomobject]@{ path = $entryName; sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash; bytes = $file.Length }
    }
} finally { $zip.Dispose() }
# Verify every archived byte before any source removal.
$zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    if ($zip.Entries.Count -ne $manifest.Count) { throw 'Archive entry count mismatch.' }
    foreach ($record in $manifest) {
        $entry = $zip.GetEntry($record.path)
        if (-not $entry -or $entry.Length -ne $record.bytes) { throw "Archive size mismatch: $($record.path)" }
        $stream = $entry.Open()
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
        finally { $stream.Dispose(); $sha.Dispose() }
        if ($hash -ne $record.sha256) { throw "Archive hash mismatch: $($record.path)" }
        $originalPath = Join-Path $workspacePath $record.path
        if ((Get-FileHash -LiteralPath $originalPath -Algorithm SHA256).Hash -ne $record.sha256) { throw 'Source changed while archiving; refusing cleanup.' }
    }
} finally { $zip.Dispose() }
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath ($zipPath + '.manifest.json') -Encoding UTF8
foreach ($targetPath in $targets) {
    $resolvedTarget = (Resolve-Path -LiteralPath $targetPath).Path
    if (-not $resolvedTarget.StartsWith($workspacePath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved removal target escapes workspace.' }
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}
Write-Output "Archived and verified $($manifest.Count) files. Removed $($targets.Count) legacy entries."
Write-Output "Backup: $zipPath"
