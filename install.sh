#!/usr/bin/env sh
# 安装 绕弯说话术 Skill 到常见 Agent 平台的 Skill 目录。
#
# 用法：
#   ./install.sh                 # 复制到检测到的基础目录
#   ./install.sh --link          # 用软链接代替复制（便于就地改）
#   ./install.sh --path DIR      # 只装到指定目录下的 double-negative-speech/
#   ./install.sh --dry-run       # 只打印将要做的事
#
# 已存在同名目录时默认跳过；加 --force 覆盖。
set -eu

NAME="double-negative-speech"
SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MODE="copy"
FORCE=0
DRY=0
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --link) MODE="link" ;;
    --copy) MODE="copy" ;;
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    --path)
      shift
      [ $# -gt 0 ] || { echo "--path 需要一个目录参数" >&2; exit 2; }
      TARGET="$1"
      ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$TARGET" ]; then
  ROOTS="$TARGET"
else
  ROOTS="${DOUBAO_SKILLS:-$HOME/.doubao/agent_mode/workspace/.user_skills}
${CLAUDE_SKILLS:-$HOME/.claude/skills}
${CODEX_SKILLS:-$HOME/.codex/skills}
${AGENTS_SKILLS:-$HOME/.agents/skills}"
fi

install_one() {
  root="$1"
  dest="$root/$NAME"
  if [ -e "$dest" ] && [ "$FORCE" -ne 1 ]; then
    echo "跳过（已存在）：$dest   （加 --force 覆盖）"
    return 0
  fi
  if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] mkdir -p $root && $MODE $SRC -> $dest"
    return 0
  fi
  mkdir -p "$root"
  [ -e "$dest" ] && rm -rf "$dest"
  if [ "$MODE" = "link" ]; then
    ln -s "$SRC" "$dest"
  else
    cp -R "$SRC" "$dest"
    rm -rf "$dest/.git" "$dest/__pycache__" "$dest/tests/__pycache__"
  fi
  echo "已安装：$dest"
}

echo "$ROOTS" | while IFS= read -r root; do
  [ -n "$root" ] || continue
  install_one "$root"
done

echo
echo "验证：python3 \"$SRC/scripts/negation_count.py\" --ambiguity \"差点没赶上\""
echo "测试：python3 -m unittest discover -s \"$SRC/tests\""
