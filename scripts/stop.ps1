param(
  [string]$Project = "ticket-idempo-demo"
)

docker compose -p $Project down --volumes --remove-orphans