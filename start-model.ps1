$ErrorActionPreference = 'Stop'
$modelRoot = Join-Path $PSScriptRoot 'ACE-Step-1.5'
$python = Join-Path $modelRoot 'venv_xpu\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "ACE-Step environment is not installed yet. Run the setup instructions in README.md first."
}
Set-Location $modelRoot
$env:SYCL_CACHE_PERSISTENT = '1'
$env:SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS = '1'
$env:PYTORCH_DEVICE = 'xpu'
$env:ACESTEP_DEVICE = 'cpu'
$env:ACESTEP_OFFLOAD_TO_CPU = 'false'
$env:TORCH_COMPILE_BACKEND = 'eager'
$env:TOKENIZERS_PARALLELISM = 'false'
$env:ACESTEP_INIT_LLM = 'false'
$env:ACESTEP_DOWNLOAD_SOURCE = 'modelscope'
$env:ACESTEP_CHECKPOINTS_DIR = Join-Path $modelRoot 'checkpoints'
$env:TORCHINDUCTOR_CACHE_DIR = Join-Path $modelRoot '.torchinductor-cache'
Write-Host 'Starting ACE-Step API on http://127.0.0.1:8001'
Write-Host 'Using CPU inference because Intel Iris Xe XPU loading is unreliable on this machine.'
Write-Host 'Model weights are already downloaded; first CPU initialization may take a few minutes.'
& $python -u -m acestep.api_server --host 127.0.0.1 --port 8001
