#!/usr/bin/env bash
# PChome 搶購排程腳本 — 在指定開賣時間前 5 分鐘自動啟動監控
#
# 用法:
#   ./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX DGCQ39-A900JRDBJ
#   ./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX --headless
#
# 參數:
#   第一個參數: 開賣時間 (格式: "YYYY-MM-DD HH:MM")
#   之後的參數: 直接傳給 main.py buy（商品 ID 和選項）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SALE_TIME="$1"
shift
PRODUCT_ARGS="$@"

if [ -z "$SALE_TIME" ] || [ -z "$PRODUCT_ARGS" ]; then
    echo "用法: $0 \"YYYY-MM-DD HH:MM\" <商品ID...> [--headless] [--interval N]"
    exit 1
fi

# 計算開賣前 5 分鐘的時間戳
SALE_TS=$(date -d "$SALE_TIME" +%s)
START_TS=$((SALE_TS - 300))
START_TIME=$(date -d "@$START_TS" "+%Y-%m-%d %H:%M:%S")
NOW_TS=$(date +%s)
WAIT_SECS=$((START_TS - NOW_TS))

echo "============================================"
echo "  PChome 搶購排程"
echo "============================================"
echo "開賣時間: $SALE_TIME"
echo "啟動時間: $START_TIME（提前 5 分鐘）"
echo "商品參數: $PRODUCT_ARGS"
echo "--------------------------------------------"

if [ "$WAIT_SECS" -le 0 ]; then
    echo "已超過啟動時間，立即開始監控！"
else
    echo "等待 $WAIT_SECS 秒後啟動（$(date -d "@$START_TS" "+%H:%M:%S")）..."
    sleep "$WAIT_SECS"
fi

echo ""
echo "開始執行搶購腳本..."
cd "$SCRIPT_DIR"
# 傳入 --sale-time 讓腳本分段輪詢：開賣前 15 秒才全速
uv run python main.py buy --sale-time "$SALE_TIME" $PRODUCT_ARGS
