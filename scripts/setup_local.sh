#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
TEMPLATE_FILE="$ROOT_DIR/.env.example"

if [ -e "$ENV_FILE" ]; then
  printf '%s\n' "A local .env file already exists: $ENV_FILE" >&2
  printf '%s\n' "It was left unchanged. Edit that file to update local settings." >&2
  exit 1
fi

cp "$TEMPLATE_FILE" "$ENV_FILE"

cat <<'EOF'
Created .env from .env.example.

The app starts in deterministic mock AI mode by default. To use a real provider,
edit .env only. Never put API keys in .env.example or commit .env.

For OpenRouter:
  USE_MOCK_CLAUDE=false
  AI_PROVIDER=openrouter
  OPENROUTER_API_KEY=your-private-key
EOF
