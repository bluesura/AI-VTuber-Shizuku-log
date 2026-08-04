# ==========================================
# LLM相談用 フォルダ構成出力 (文字化け回避版)
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# ==========================================

$targetDirectory = Get-Location

# 無視したいファイルやフォルダのリスト
$ignorePatterns = @(
    ".git", ".vs", ".vscode", ".idea", "node_modules", "__pycache__",
    "bin", "obj", "*.exe", "*.dll", "*.pdb", "dist", "build",
    "package-lock.json", "yarn.lock", "*.log", ".DS_Store"
)

function Get-TreeStructure {
    param (
        [string]$Path,
        [string]$Indent = "",
        [bool]$IsLast = $true
    )

    $name = Split-Path $Path -Leaf
    
    if ($Indent -ne "") {
        # 文字化けしない記号に変更 (│ → |, ├── → +--, └── → \--)
        $marker = if ($IsLast) { "\-- " } else { "+-- " }
        $line = "$($Indent.Substring(0, $Indent.Length - 4))$marker$name"
    } else {
        $line = $name
    }
    
    $global:outputList += $line

    if (-not (Test-Path $Path -PathType Container)) { return }

    $items = Get-ChildItem -Path $Path -Force | Where-Object {
        $itemName = $_.Name
        $shouldIgnore = $false
        foreach ($pattern in $ignorePatterns) {
            if ($itemName -like $pattern) {
                $shouldIgnore = $true
                break
            }
        }
        -not $shouldIgnore
    }

    $count = $items.Count
    for ($i = 0; $i -lt $count; $i++) {
        $isLastItem = ($i -eq ($count - 1))
        # 次のインデント生成 (│ → |)
        $nextIndent = if ($Indent -eq "") { "    " } else {
            if ($IsLast) { $Indent + "    " } else { $Indent + "|   " }
        }
        Get-TreeStructure -Path $items[$i].FullName -Indent $nextIndent -IsLast $isLastItem
    }
}

# --- 実行処理 ---
$global:outputList = @()

# 日本語メッセージも文字化けリスクがあるため英語表記に変更
Write-Host "Generating file tree...: $targetDirectory" -ForegroundColor Cyan

Get-TreeStructure -Path $targetDirectory
$resultText = $global:outputList -join "`r`n"

Write-Host "`n--- Result ---" -ForegroundColor Green
Write-Host $resultText
Write-Host "--------------" -ForegroundColor Green

Set-Clipboard -Value $resultText
Write-Host "`n[Success] Copied to clipboard!" -ForegroundColor Yellow

Read-Host "Press Enter to exit..."