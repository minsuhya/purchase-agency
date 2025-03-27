# 스크립트가 있는 디렉토리의 부모 디렉토리로 이동 (프로젝트 루트)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptPath '..')

Write-Host "해외 상품 수집 프로토타입 설정 스크립트" -ForegroundColor Green
Write-Host "---------------------------------------------"

# uv가 설치되어 있는지 확인
try {
    $uvVersion = (uv --version) | Out-String
} catch {
    Write-Host "ERROR: uv가 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "설치 방법: powershell -c `"irm https://windows.uv.dev | iex`"" -ForegroundColor Yellow
    exit 1
}

Write-Host "uv 버전: $uvVersion" -ForegroundColor Green

# 가상환경 생성
Write-Host "`n가상환경 생성 중..." -ForegroundColor Green
uv venv

# 가상환경 활성화
Write-Host "`n가상환경 활성화 중..." -ForegroundColor Green
. .\.venv\Scripts\Activate.ps1

# 의존성 설치
Write-Host "`n의존성 설치 중..." -ForegroundColor Green
uv pip install -r requirements.txt

# .env 파일 생성
if (-not (Test-Path .env)) {
    Write-Host "`n.env 파일 생성 중..." -ForegroundColor Green
    Copy-Item .env.example .env
    Write-Host "주의: .env 파일을 수정하여 필요한 API 키를 설정하세요." -ForegroundColor Yellow
} else {
    Write-Host "`n.env 파일이 이미 존재합니다." -ForegroundColor Green
}

Write-Host "`n설정 완료!" -ForegroundColor Green
Write-Host "실행 방법: python run.py" 