# 배포용 데스크톱 앱을 처음부터 끝까지 빌드한다.
#
#     powershell -File scripts/build_desktop_app.ps1
#
# 산출물: dist/MunpiaRevenue.exe — **이 파일 하나만** 작가에게 보내면 된다(압축 불필요).
# 안내문 dist/사용법.txt는 곁들여 보낼 수 있는 선택 사항이다.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '[1/4] 번들 생성 (카탈로그 + 모델)' -ForegroundColor Cyan
uv run python scripts/build_app_bundle.py
if ($LASTEXITCODE -ne 0) { throw '번들 생성 실패' }

Write-Host '[2/4] 스플래시 이미지 생성' -ForegroundColor Cyan
# onefile은 첫 실행에서 ~150MB를 푸느라 10초쯤 걸린다. 그동안 띄울 안내 이미지.
uv run python scripts/make_splash.py
if ($LASTEXITCODE -ne 0) { throw '스플래시 생성 실패' }

Write-Host '[3/4] PyInstaller 빌드 (onefile)' -ForegroundColor Cyan
uv run pyinstaller app/munpia_app.spec --noconfirm --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 빌드 실패' }

Write-Host '[4/4] 빌드본 자체 점검' -ForegroundColor Cyan
# console=False라 실행 출력이 보이지 않으므로 결과를 파일로 받는다.
# 모델 언피클(hiddenimports)이 깨졌는지를 여기서 잡는다.
$report = Join-Path $env:TEMP 'munpia_selftest.txt'
if (Test-Path $report) { Remove-Item $report }
$proc = Start-Process -FilePath 'dist\MunpiaRevenue.exe' `
    -ArgumentList '--selftest', $report -PassThru -Wait
if (-not (Test-Path $report)) { throw "자체 점검 결과가 생성되지 않았습니다 (exit $($proc.ExitCode))" }
$result = Get-Content $report -Encoding utf8
$result | ForEach-Object { Write-Host "    $_" }
if ($result -notcontains 'RESULT: OK') { throw '자체 점검 실패 — 위 메시지 확인' }

Copy-Item 'app\사용법.txt' 'dist\사용법.txt' -Force

$mb = [math]::Round((Get-Item 'dist\MunpiaRevenue.exe').Length / 1MB, 1)
Write-Host "완료: dist\MunpiaRevenue.exe ($mb MB) — 이 파일 하나만 전달" -ForegroundColor Green
