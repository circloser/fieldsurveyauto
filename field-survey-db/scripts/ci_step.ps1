# GitHub Actions 단계 실행기 — 명령이 실패하면 마지막 출력 40줄을 주석(annotation)으로 남긴다.
# 공개 저장소의 주석은 로그인 없이 API로 읽을 수 있어, 로그를 못 여는 환경에서도 실패 원인을 알 수 있다.
# 사용: ./scripts/ci_step.ps1 "단계 이름" 명령 인자...
# (param 선언을 쓰지 않는다 — 선언하면 명령 인자 '-m'·'-c' 를 이 스크립트의 옵션으로 오해한다)
$Title = $args[0]
$exe = $args[1]
# 항상 배열로 — 인자가 하나뿐일 때 $args[2..2] 는 문자열이 되어 splat 이 글자 단위로 쪼개진다
$rest = @($args | Select-Object -Skip 2)
$tmp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$log = Join-Path $tmp ("step_" + [guid]::NewGuid().ToString("N") + ".log")
& $exe @rest *>&1 | Tee-Object -FilePath $log
$code = $LASTEXITCODE
if ($code -ne 0) {
  $tail = (Get-Content $log -Tail 40) -join "`n"
  $msg = $tail.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
  Write-Output "::error title=$Title (exit $code)::$msg"
  exit $code
}
