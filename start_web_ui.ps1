$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} else {
    $python = "python"
}

& $python -m streamlit run ".\hans_web_ui.py" `
    --server.address "0.0.0.0" `
    --server.port "8501" `
    --server.headless "true" `
    --browser.gatherUsageStats "false"
