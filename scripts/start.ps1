param(
  [string]$Project = "ticket-idempo-demo"
)

docker compose -p $Project up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Frontend: http://localhost:3000"
Write-Host "API: http://localhost:8000/docs"
Write-Host "pgAdmin: http://localhost:5050 (admin@demo.local / admin)"