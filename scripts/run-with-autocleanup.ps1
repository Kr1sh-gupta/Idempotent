param(
  [string]$Project = "ticket-idempo-demo"
)

$stopping = $false
function Stop-Demo {
  if ($stopping) { return }
  $stopping = $true
  Write-Host "Stopping demo and cleaning only project-scoped resources..."
  docker compose -p $Project down --volumes --remove-orphans
}

try {
  docker compose -p $Project up --build
}
finally {
  Stop-Demo
}