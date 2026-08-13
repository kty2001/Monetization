<#
.SYNOPSIS
장시간 크롤이 죽거나 멈추면 --resume으로 재시작하는 워치독.

.DESCRIPTION
크롤 프로세스가 외부 요인으로 종료되는 일이 반복돼(관측: 30~50분 간격) 장시간 크롤을
감시 없이 완주하기 어렵다. 이 스크립트는 주기적으로
  1) 대상 프로세스가 살아있는지 (커맨드라인 매칭)
  2) 체크포인트 로그 줄 수가 늘고 있는지
를 확인하고, 죽었거나 멈췄으면 --resume으로 다시 띄운다.

재시작 시 체크포인트 줄 수로 --start-page를 계산해 넘긴다. 이게 없으면 재개할 때마다
목록 앞 페이지를 전부 재스캔하느라 절반 진행 상태에서 20분 이상을 버린다.

⚠️ 이 스크립트는 사용자 터미널에서 직접 실행할 것. 에이전트 세션의 백그라운드로 띄우면
워치독 자신이 같은 수명 제한에 걸린다.

.EXAMPLE
# 유료 라벨 크롤을 감시하며 실행
powershell -File scripts/watch_and_resume.ps1 `
  -OutputDir data/raw/paid `
  -ExtraArgs '--section pl.serial_end --prefix paid_ --collect-stats --free-chapters-only --max-pages 0 --novel-limit 0 --delay 0.8'

.EXAMPLE
# 실제 재시작 없이 계산된 명령만 확인
powershell -File scripts/watch_and_resume.ps1 -OutputDir data/raw/paid -ExtraArgs '...' -DryRun
#>
[CmdletBinding()]
param(
    [string]   $ScriptPath      = "scripts/crawl_munpia.py",
    [Parameter(Mandatory = $true)]
    [string]   $OutputDir,
    [string]   $ExtraArgs       = "",
    [int]      $IntervalSeconds = 300,
    [int]      $StallMinutes    = 10,
    [int]      $MaxRestarts     = 3,
    [int]      $StartupCheckSeconds = 20,
    [int]      $ItemsPerPage    = 20,
    [int]      $PageBuffer      = 5,
    [switch]   $DryRun
)

$ErrorActionPreference = "Stop"
$RestartLog = Join-Path $OutputDir "watchdog_restarts.log"

# 명령을 여러 줄에 걸쳐 붙여넣으면 -ExtraArgs 문자열에 개행이 섞여 들어간다. 그대로
# 넘기면 토큰이 "--collect-stats`n"이 되어 argparse가 "unrecognized arguments"로 거부한다.
$ExtraArgs = ($ExtraArgs -replace '\s+', ' ').Trim()

function Get-CheckpointLineCount {
    $logs = Get-ChildItem -Path $OutputDir -Filter ".processed_novel_ids_*.log" -Force -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
    if (-not $logs) { return 0 }
    return (Get-Content $logs[0].FullName | Measure-Object -Line).Lines
}

function Get-CrawlProcess {
    # 커맨드라인에 대상 스크립트와 출력 디렉토리가 함께 들어간 python 프로세스
    $leaf = Split-Path $ScriptPath -Leaf
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$leaf*" -and $_.CommandLine -like "*$OutputDir*" } |
        Select-Object -First 1
}

function Get-StartPage([int]$lines) {
    # 처리 건수 / 페이지당 건수 에서 여유를 빼 조금 앞에서 시작한다.
    # 목록 정렬이 크롤 도중에도 바뀌므로 여유가 필요하고, 중복은 체크포인트가 거른다.
    $page = [math]::Floor($lines / $ItemsPerPage) - $PageBuffer
    if ($page -lt 1) { return 1 }
    return [int]$page
}

function Start-Crawl([int]$lines) {
    $startPage = Get-StartPage $lines
    $argList = "run python $ScriptPath --output-dir $OutputDir --resume --start-page $startPage $ExtraArgs"
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    if ($DryRun) {
        Write-Host "[$stamp] [DryRun] uv $argList"
        return $null
    }

    Write-Host "[$stamp] 재시작: uv $argList"
    Add-Content -Path $RestartLog -Value "$stamp restart lines=$lines start_page=$startPage" -Encoding utf8
    $proc = Start-Process -FilePath "uv" -ArgumentList $argList -PassThru -NoNewWindow

    # 인자 오타 등으로 즉시 죽는 경우를 다음 점검 주기(수 분 뒤)까지 기다리지 않고 바로 잡는다.
    if (-not $proc.WaitForExit($StartupCheckSeconds * 1000)) {
        return $proc
    }
    Write-Warning "크롤 프로세스가 ${StartupCheckSeconds}초 안에 종료됐습니다 (exit $($proc.ExitCode))."
    Write-Warning "인자가 잘못됐을 수 있습니다. 위 명령을 그대로 직접 실행해 오류를 확인하세요:"
    Write-Warning "  uv $argList"
    return $null
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

Write-Host "워치독 시작: $ScriptPath -> $OutputDir (점검 주기 ${IntervalSeconds}s, 정체 판정 ${StallMinutes}m)"

# 시간 창(예: 5분 내 N회)으로 세면 안 된다 — 점검 주기가 그 창과 같거나 크면 한 창에
# 한 번밖에 안 들어가 가드가 영영 발동하지 않는다. "진전 없는 연속 재시작 횟수"로 센다.
$restartsWithoutProgress = 0
$lastLines     = Get-CheckpointLineCount
$lastProgress  = Get-Date

if ($DryRun) {
    Start-Crawl $lastLines | Out-Null
    Write-Host "[DryRun] 현재 체크포인트 $lastLines줄 -> start-page $(Get-StartPage $lastLines). 종료합니다."
    return
}

while ($true) {
    Start-Sleep -Seconds $IntervalSeconds

    $lines = Get-CheckpointLineCount
    $proc  = Get-CrawlProcess
    $now   = Get-Date

    if ($lines -gt $lastLines) {
        $lastLines    = $lines
        $lastProgress = $now
        $restartsWithoutProgress = 0   # 실제로 수집이 진행됐으므로 가드를 초기화
    }

    $stalledMin = ($now - $lastProgress).TotalMinutes
    $needsRestart = $false
    $reason = ""

    if (-not $proc) {
        $needsRestart = $true
        $reason = "프로세스 없음"
    }
    elseif ($stalledMin -ge $StallMinutes) {
        $needsRestart = $true
        $reason = "체크포인트가 $([math]::Round($stalledMin))분간 정체"
        Stop-Process -Id $proc.ProcessId -Force -Confirm:$false
    }

    if (-not $needsRestart) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 정상 (처리 $lines건)"
        continue
    }

    # 무한 재시작 방지: 재시작해도 수집이 전혀 늘지 않으면 근본 원인이 있는 것이므로 멈춘다
    if ($restartsWithoutProgress -ge $MaxRestarts) {
        Write-Warning "$MaxRestarts회 연속 재시작했는데 수집이 늘지 않았습니다 — 워치독을 멈춥니다."
        Write-Warning "마지막 처리 건수: $lines. 로그: $RestartLog"
        break
    }

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $reason -> 재시작 (처리 $lines건)"
    $restartsWithoutProgress++
    $started = Start-Crawl $lines
    if (-not $started) {
        Write-Warning "시작 직후 종료돼 워치독을 멈춥니다(재시작을 반복해도 같은 결과일 것)."
        break
    }
    $lastProgress = Get-Date
}
