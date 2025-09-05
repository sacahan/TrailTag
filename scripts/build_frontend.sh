#!/usr/bin/env zsh

set -euo pipefail

# 簡單 log helper，統一資訊與錯誤輸出格式
info() { echo "[INFO] $*"; }
err()  { echo "[ERROR] $*" >&2; }

# 取得腳本所在目錄與專案根目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

info "=== 開始前端建制流程 ==="

# 處理環境變數配置
info "設定 TrailTag 配置環境變數..."

# 設定預設環境變數（如果未提供）
export TRAILTAG_API_BASE_URL="${TRAILTAG_API_BASE_URL:-http://localhost:8010}"
export TRAILTAG_FETCH_RETRIES="${TRAILTAG_FETCH_RETRIES:-2}"
export TRAILTAG_FETCH_BACKOFF_MS="${TRAILTAG_FETCH_BACKOFF_MS:-500}"
export TRAILTAG_MAX_RECONNECT="${TRAILTAG_MAX_RECONNECT:-1}"
export TRAILTAG_POLLING_INTERVAL_MS="${TRAILTAG_POLLING_INTERVAL_MS:-5000}"
export TRAILTAG_KEEPALIVE_MS="${TRAILTAG_KEEPALIVE_MS:-30000}"
export TRAILTAG_STATE_TTL_MS="${TRAILTAG_STATE_TTL_MS:-1800000}"

# 顯示當前配置
info "當前 TrailTag 配置:"
info "  API_BASE_URL: $TRAILTAG_API_BASE_URL"
info "  FETCH_RETRIES: $TRAILTAG_FETCH_RETRIES"
info "  FETCH_BACKOFF_MS: $TRAILTAG_FETCH_BACKOFF_MS"
info "  MAX_RECONNECT: $TRAILTAG_MAX_RECONNECT"
info "  POLLING_INTERVAL_MS: $TRAILTAG_POLLING_INTERVAL_MS"
info "  KEEPALIVE_MS: $TRAILTAG_KEEPALIVE_MS"
info "  STATE_TTL_MS: $TRAILTAG_STATE_TTL_MS"

# 前端 extension 的路徑（假設存放於 src/extension）
EXT_DIR="$PROJECT_ROOT/src/extension"

if [ -d "$EXT_DIR" ]; then
    info "Packaging extension in $EXT_DIR"
    cd "$EXT_DIR"

    # 若沒有 node_modules，先嘗試用 npm ci 安裝相依（較適合 CI），若失敗則退回到 npm install
    if [ ! -d node_modules ]; then
        info "node_modules not found — installing npm dependencies (npm ci preferred)..."
        if command -v npm >/dev/null 2>&1; then
            # npm ci 會比 npm install 更可預測（使用 lockfile），但某些專案或環境可能不支援
            if npm ci --silent; then
                info "npm ci completed"
            else
                # 若 npm ci 因 lockfile 或其他問題失敗，改為較寬容的 npm install
                info "npm ci failed or not supported; falling back to npm install"
                npm install
            fi
        else
            # 如果系統沒有安裝 npm，回報錯誤並停止前端打包流程
            err "npm is not installed or not in PATH; frontend packaging failed"
            exit 1
        fi
    fi

    # 執行專案定義的包裝腳本（package），此處不對輸出做額外處理，讓 npm 的錯誤直接冒出
    info "Running: npm run package"
    npm run package
    info "Extension packaging finished"

    info "=== 前端建制完成 ==="
else
    # 找不到前端目錄時，記錄並停止流程
    err "Extension directory not found: $EXT_DIR"
    err "=== 前端建制失敗 ==="
    exit 1
fi
