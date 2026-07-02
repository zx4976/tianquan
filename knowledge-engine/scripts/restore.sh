#!/usr/bin/env bash
# 知识引擎 — 恢复脚本
# 用法: bash restore.sh [备份文件路径]
#       如果不指定，默认恢复最新的备份

set -euo pipefail

PROJECT_DIR="/root/projects/knowledge-engine"
BACKUP_DIR="${BACKUP_DIR:-/mnt/天权智库/天权智库/工作文档/知识引擎备份}"

echo "🔄 知识引擎恢复工具"
echo "=========================================="

# 1. 确定备份文件
if [ $# -ge 1 ]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE=$(ls -t ${BACKUP_DIR}/knowledge_engine_*.tar.gz 2>/dev/null | head -1)
    if [ -z "${BACKUP_FILE}" ]; then
        echo "❌ 未找到备份文件"
        echo "   用法: bash restore.sh [备份文件路径]"
        exit 1
    fi
fi

echo "使用备份: ${BACKUP_FILE}"

# 2. 校验
SHA_FILE="${BACKUP_FILE}.sha256"
if [ -f "${SHA_FILE}" ]; then
    echo "校验中..."
    sha256sum -c "${SHA_FILE}" --quiet && echo "  ✅ 校验通过" || {
        echo "  ❌ 校验失败！文件已损坏"
        exit 1
    }
else
    echo "  ⚠️ 未找到校验文件，跳过校验"
fi

# 3. 备份当前状态
BACKUP_OLD="${PROJECT_DIR}.bak.$(date +%Y%m%d_%H%M%S)"
if [ -d "${PROJECT_DIR}/src" ]; then
    echo "备份当前状态到 ${BACKUP_OLD}..."
    cp -a "${PROJECT_DIR}" "${BACKUP_OLD}"
    echo "  ✅ 当前状态已保存"
fi

# 4. 恢复
echo "恢复中..."
mkdir -p "${PROJECT_DIR}"
tar xzf "${BACKUP_FILE}" -C "${PROJECT_DIR}"
echo "  ✅ 恢复完成"

# 5. 验证
echo "验证..."
if [ -f "${PROJECT_DIR}/main.py" ] && [ -d "${PROJECT_DIR}/src" ]; then
    echo "  ✅ 核心文件存在"
    ls -la "${PROJECT_DIR}/src/" | head -10
else
    echo "  ❌ 恢复可能不完整，核心文件缺失"
fi

echo ""
echo "=========================================="
echo "✅ 恢复完成"
echo "   来源: ${BACKUP_FILE}"
echo "   位置: ${PROJECT_DIR}"
echo "   旧状态: ${BACKUP_OLD}"
echo ""
echo "恢复后运行环境重建:"
echo "  cd ${PROJECT_DIR} && uv venv --python 3.14 .venv"
echo "  uv pip install tantivy kuzu scikit-learn jieba"
