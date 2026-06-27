#!/usr/bin/env bash
# 知识引擎 — 备份脚本
# 备份范围: 源码 + 索引数据 + 配置

set -euo pipefail

PROJECT_DIR="/root/projects/knowledge-engine"
BACKUP_DIR="${BACKUP_DIR:-/mnt/天权智库/天权智库/工作文档/知识引擎备份}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/knowledge_engine_${DATE}.tar.gz"
SHA_FILE="${BACKUP_FILE}.sha256"
RETENTION_DAYS=${RETENTION_DAYS:-7}

echo "📦 知识引擎备份 — ${DATE}"
echo "=========================================="

# 1. 确保备份目录存在
mkdir -p "${BACKUP_DIR}"

# 2. 打包
echo "打包中..."
tar czf "${BACKUP_FILE}" \
    -C "${PROJECT_DIR}" \
    --exclude=".venv" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".pytest_cache" \
    src/ main.py scripts/ data/ docs/ 

# 3. 校验和
echo "计算校验和..."
sha256sum "${BACKUP_FILE}" > "${SHA_FILE}"

# 4. 验证
echo "验证..."
sha256sum -c "${SHA_FILE}" --quiet && echo "  ✅ 校验通过"

# 5. 清理旧备份
echo "清理 ${RETENTION_DAYS} 天前的备份..."
find "${BACKUP_DIR}" -name "knowledge_engine_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "knowledge_engine_*.sha256" -mtime +${RETENTION_DAYS} -delete

# 6. 统计
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo ""
echo "=========================================="
echo "✅ 备份完成"
echo "   文件: ${BACKUP_FILE}"
echo "   大小: ${BACKUP_SIZE}"
echo "   位置: ${BACKUP_DIR}"
echo ""
echo "恢复命令: bash restore.sh ${BACKUP_FILE}"
