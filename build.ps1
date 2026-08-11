# 一键打包 Scrybe
$ErrorActionPreference = "Stop"
Write-Host "== 安装依赖 =="
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt pyinstaller
Write-Host "== 运行测试 =="
& .\.venv\Scripts\python.exe -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw "测试未通过，终止打包" }
Write-Host "== 打包 =="
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean build.spec
Write-Host ""
Write-Host "完成！exe 位于：$PWD\dist\Scrybe.exe"
