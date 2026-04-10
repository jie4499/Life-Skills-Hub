#!/bin/bash

# AI Skills 安装脚本
# 将项目中的技能目录安装到 ~/.claude/skills/

set -e

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 目标目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QODER_SKILLS_DIR="$SCRIPT_DIR/.qoder/skills"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
BACKUP_DIR="$HOME/.ai_skills_backup"

# 获取当前日期
DATE=$(date +%Y%m%d_%H%M%S)

echo -e "${GREEN}=== AI Skills 安装程序 ===${NC}"
echo ""

# 检查安装目标
if [ -d "$QODER_SKILLS_DIR" ]; then
    SKILLS_DIR="$QODER_SKILLS_DIR"
    echo -e "${GREEN}检测到 Qoder 项目，安装到: $SKILLS_DIR${NC}"
elif [ -d "$HOME/.claude" ]; then
    SKILLS_DIR="$CLAUDE_SKILLS_DIR"
    echo -e "${GREEN}检测到 Claude Code，安装到: $SKILLS_DIR${NC}"
    mkdir -p "$SKILLS_DIR"
else
    echo -e "${YELLOW}未检测到 Claude Code 或 Qoder，安装到项目本地${NC}"
    SKILLS_DIR="$QODER_SKILLS_DIR"
    mkdir -p "$SKILLS_DIR"
fi
echo ""

# 创建备份目录（如果不存在）
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${YELLOW}创建备份目录: $BACKUP_DIR${NC}"
    mkdir -p "$BACKUP_DIR"
fi

# 查找所有技能目录（排除隐藏目录、脚本文件等）
echo -e "${GREEN}扫描技能目录...${NC}"
SKILL_COUNT=0

for dir in "$SCRIPT_DIR"/*/; do
    # 跳过不存在的目录
    [ ! -d "$dir" ] && continue
    
    # 获取目录名称
    skill_name=$(basename "$dir")
    
    # 跳过隐藏目录和非技能目录
    if [[ "$skill_name" == .* ]] || [[ "$skill_name" == "scripts" ]] || [[ "$skill_name" == "docs" ]]; then
        continue
    fi
    
    # 检查是否包含 SKILL.md 文件（判断是否为技能目录）
    if [ ! -f "$dir/SKILL.md" ]; then
        echo -e "${YELLOW}跳过 $skill_name (不包含 SKILL.md)${NC}"
        continue
    fi
    
    echo ""
    echo -e "${GREEN}处理技能: $skill_name${NC}"
    
    # 目标路径
    target_path="$SKILLS_DIR/$skill_name"
    
    # 如果目标目录已存在，先备份
    if [ -d "$target_path" ]; then
        backup_name="${skill_name}_${DATE}"
        backup_path="$BACKUP_DIR/$backup_name"
        
        echo -e "${YELLOW}  备份现有目录到: $backup_path${NC}"
        mv "$target_path" "$backup_path"
    fi
    
    # 复制技能目录
    echo -e "${GREEN}  安装技能到: $target_path${NC}"
    cp -r "$dir" "$target_path"
    
    SKILL_COUNT=$((SKILL_COUNT + 1))
done

echo ""
echo -e "${GREEN}=== 安装完成 ===${NC}"
echo -e "${GREEN}成功安装 $SKILL_COUNT 个技能${NC}"
echo ""
echo -e "${YELLOW}提示：${NC}"
echo -e "  - 技能已安装到: $SKILLS_DIR"
if [ $SKILL_COUNT -gt 0 ]; then
    echo -e "  - 备份目录: $BACKUP_DIR"
fi
if [ "$SKILLS_DIR" = "$QODER_SKILLS_DIR" ]; then
    echo -e "  - Qoder 将自动识别项目中的技能"
else
    echo -e "  - 在 Claude Code 中询问 'What Skills are available?' 查看已安装的技能"
fi
echo ""
