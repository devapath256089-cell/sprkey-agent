#!/usr/bin/env bash
# Sprkey custom pack installer
#   - copies skills into ~/.sprkey/skills/productivity/  (source of truth)
#   - prints the mcp_servers blocks for sprkey-tools + sprkey-cloak
# Idempotent: safe to run repeatedly.
set -euo pipefail

SPRKEY_HOME="${SPRKEY_HOME:-$HOME/.sprkey}"
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_TARGET="$SPRKEY_HOME/skills/productivity"
TOOLS_DIR="$PACK_DIR/optional-mcps/sprkey-tools"
CLOAK_DIR="$PACK_DIR/optional-mcps/sprkey-cloak"

echo "==> installing skills to $SKILL_TARGET"
mkdir -p "$SKILL_TARGET"
for skill in "$PACK_DIR"/skills/*/; do
  name="$(basename "$skill")"
  rm -rf "$SKILL_TARGET/$name"
  cp -a "$skill" "$SKILL_TARGET/$name"
  echo "    skill: $name"
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
