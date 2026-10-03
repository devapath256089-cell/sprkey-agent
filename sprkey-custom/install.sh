#!/usr/bin/env bash
# Sprkey custom pack installer
#   - copies skills into ~/.sprkey/skills/<category>/  (source of truth)
#   - prints the mcp_servers blocks for sprkey-tools + sprkey-cloak
# Idempotent: safe to run repeatedly.
set -euo pipefail

SPRKEY_HOME="${SPRKEY_HOME:-$HOME/.sprkey}"
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$PACK_DIR/optional-mcps/sprkey-tools"
CLOAK_DIR="$PACK_DIR/optional-mcps/sprkey-cloak"

declare -A SKILL_CATEGORY=(
  [worklog-keeper]=productivity
  [nepali-calendar]=productivity
  [nepse]=finance
)

echo "==> installing skills to $SPRKEY_HOME/skills/<category>"
for skill in "$PACK_DIR"/skills/*/; do
  name="$(basename "$skill")"
  cat="${SKILL_CATEGORY[$name]:-productivity}"
  target="$SPRKEY_HOME/skills/$cat"
  mkdir -p "$target"
  rm -rf "$target/$name"
  cp -a "$skill" "$target/$name"
  echo "    skill: $name -> skills/$cat"
done

echo
echo "==> MCP servers (add to $SPRKEY_HOME/config.yaml, merge if it exists):"
echo
cat <<EOF
mcp_servers:
  sprkey-tools:
    command: "python3"
    args: ["$TOOLS_DIR/server.py"]
  sprkey-cloak:
    command: "python3"
    args: ["$CLOAK_DIR/server.py"]
EOF
echo

if [ "${1:-}" = "--with-mcp" ]; then
  CFG="$SPRKEY_HOME/config.yaml"
  touch "$CFG"
  if grep -q "sprkey-tools" "$CFG" && grep -q "sprkey-cloak" "$CFG"; then
    echo "==> both servers already present in $CFG - nothing to do"
  else
    {
      echo ""
      echo "mcp_servers:"
      grep -q "sprkey-tools" "$CFG" || {
        echo "  sprkey-tools:"
        echo "    command: \"python3\""
        echo "    args: [\"$TOOLS_DIR/server.py\"]"
      }
      grep -q "sprkey-cloak" "$CFG" || {
        echo "  sprkey-cloak:"
        echo "    command: \"python3\""
        echo "    args: [\"$CLOAK_DIR/server.py\"]"
      }
    } >> "$CFG"
    echo "==> appended missing servers to $CFG"
  fi
else
  echo "    (run with --with-mcp to append missing blocks automatically)"
fi

echo "==> done. restart the Sprkey session to load skills + tools."
