#!/usr/bin/env bash
# Sprkey custom pack installer
#   - copies skills into ~/.sprkey/skills/productivity/  (source of truth)
#   - prints the mcp_servers block for sprkey-tools (config.yaml)
# Idempotent: safe to run repeatedly.
set -euo pipefail

SPRKEY_HOME="${SPRKEY_HOME:-$HOME/.sprkey}"
PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_TARGET="$SPRKEY_HOME/skills/productivity"
TOOLS_DIR="$PACK_DIR/optional-mcps/sprkey-tools"

echo "==> installing skills to $SKILL_TARGET"
mkdir -p "$SKILL_TARGET"
for skill in "$PACK_DIR"/skills/*/; do
  name="$(basename "$skill")"
  rm -rf "$SKILL_TARGET/$name"
  cp -a "$skill" "$SKILL_TARGET/$name"
  echo "    skill: $name"
done

echo
echo "==> sprkey-tools MCP server"
echo "    add this block to $SPRKEY_HOME/config.yaml (merge if it exists):"
echo
cat <<EOF
mcp_servers:
  sprkey-tools:
    command: "python3"
    args: ["$TOOLS_DIR/server.py"]
EOF
echo
if [ -f "$SPRKEY_HOME/config.yaml" ] && grep -q "sprkey-tools" "$SPRKEY_HOME/config.yaml" 2>/dev/null; then
  echo "    (sprkey-tools already present in config.yaml - nothing to do)"
else
  echo "    or run with --with-mcp to append the block automatically."
fi

if [ "${1:-}" = "--with-mcp" ]; then
  {
    echo ""
    echo "mcp_servers:"
    echo "  sprkey-tools:"
    echo "    command: \"python3\""
    echo "    args: [\"$TOOLS_DIR/server.py\"]"
  } >> "$SPRKEY_HOME/config.yaml"
  echo "==> appended sprkey-tools to $SPRKEY_HOME/config.yaml"
fi

echo "==> done. restart the Sprkey session to load skills + tools."
