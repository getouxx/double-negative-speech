#!/usr/bin/env sh
# 安装 绕弯说话术 Skill 到已存在的 Agent 平台 Skill 目录。
#
# 用法：
#   ./install.sh                 # 只装到已存在的候选目录（不新建）
#   ./install.sh --link          # 用软链接代替复制（便于就地改）
#   ./install.sh --path DIR      # 只装到指定目录下的 double-negative-speech/（目录不存在则创建）
#   ./install.sh --dry-run       # 只打印将要做的事
#
# 候选目录一个都不存在时，脚本什么也不装，打印检查过的路径并以退出码 1 结束，
# 提示改用 --path DIR 或设置 DOUBAO_SKILLS / CLAUDE_SKILLS / CODEX_SKILLS / AGENTS_SKILLS。
# 已存在同名目录时默认跳过；加 --force 覆盖。
set -eu

NAME="double-negative-speech"
SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MODE="copy"
FORCE=0
DRY=0
TARGET=""
INSTALLED=0
SKIPPED=0

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

install_one() {
  root="$1"
  dest="$root/$NAME"
  if [ -e "$dest" ] && [ "$FORCE" -ne 1 ]; then
    echo "跳过（已存在）：$dest   （加 --force 覆盖）"
    SKIPPED=$((SKIPPED + 1))
    return 0
  fi
  if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] $MODE $SRC -> $dest"
    INSTALLED=$((INSTALLED + 1))
    return 0
  fi
  [ -e "$dest" ] && rm -rf "$dest"
  if [ "$MODE" = "link" ]; then
    ln -s "$SRC" "$dest"
  else
    cp -R "$SRC" "$dest"
    rm -rf "$dest/.git" "$dest/__pycache__" "$dest/tests/__pycache__"
  fi
  echo "已安装：$dest"
  INSTALLED=$((INSTALLED + 1))
}

if [ -n "$TARGET" ]; then
  if [ ! -d "$TARGET" ]; then
    if [ "$DRY" -eq 1 ]; then
      echo "[dry-run] 会创建目录：$TARGET"
    else
      mkdir -p "$TARGET"
      echo "已创建目录：$TARGET"
    fi
  fi
  install_one "$TARGET"
else
  ROOTS="${DOUBAO_SKILLS:-$HOME/.doubao/agent_mode/workspace/.user_skills}
${CLAUDE_SKILLS:-$HOME/.claude/skills}
${CODEX_SKILLS:-$HOME/.codex/skills}
${AGENTS_SKILLS:-$HOME/.agents/skills}"

  FOUND=0
  MISSING=""
  OLDIFS=$IFS
  IFS='
'
  for root in $ROOTS; do
    [ -n "$root" ] || continue
    if [ -d "$root" ]; then
      FOUND=$((FOUND + 1))
      install_one "$root"
    else
      MISSING="$MISSING
  $root"
    fi
  done
  IFS=$OLDIFS

  if [ "$FOUND" -eq 0 ]; then
    echo "未发现任何候选 Skill 目录，本次未安装。" >&2
    echo "检查过的路径：$MISSING" >&2
    echo "改用指定目录：./install.sh --path ~/skills" >&2
    echo "或用环境变量覆盖：DOUBAO_SKILLS=/your/skills ./install.sh" >&2
    exit 1
  fi

  if [ -n "$MISSING" ]; then
    echo
    echo "以下候选目录不存在，已跳过（不会自动创建）：$MISSING"
    echo "要装到这些位置，先建目录再用 --path，或用对应环境变量指到已有目录。"
  fi
fi

echo
echo "本次：安装/计划 $INSTALLED 处，跳过 $SKIPPED 处"
echo "验证：python3 \"$SRC/scripts/negation_count.py\" --ambiguity \"差点没赶上\""
echo "测试：python3 -m unittest discover -s \"$SRC/tests\""
