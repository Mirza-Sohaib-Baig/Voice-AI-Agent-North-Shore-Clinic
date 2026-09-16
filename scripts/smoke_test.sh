#!/usr/bin/env bash
# Hit a running API (local or Render). Usage: BASE_URL=https://.... ./scripts/smoke_test.sh
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "health..."
curl -fsS "$BASE_URL/health" | head -c 400
echo

echo "create..."
RESP=$(curl -fsS -X POST "$BASE_URL/patients" -H "Content-Type: application/json" -d '{
  "first_name": "Riley",
  "last_name": "Chen",
  "date_of_birth": "11/02/1994",
  "sex": "Other",
  "phone_number": "2066246827",
  "address_line_1": "400 Broad St",
  "city": "Seattle",
  "state": "WA",
  "zip_code": "98109"
}')
echo "$RESP"

echo "list last_name=Chen..."
curl -fsS "$BASE_URL/patients?last_name=Chen"
echo
echo "ok"
