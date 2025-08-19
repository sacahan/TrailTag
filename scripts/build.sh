
#!/usr/bin/env zsh
# 這個腳本會：
# 1) 重建後端（docker compose service 名稱為 backend）的映像
# 2) 使用 docker compose 啟動/重啟該 service（僅針對 backend，避免重啟其他服務）
# 3) 在前端 extension 目錄執行 `npm run package`，並在必要時安裝相依套件
# 使用方式：在專案根目錄執行 `./scripts/build.sh`

set -euo pipefail

# 取得腳本所在目錄與專案根目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

# 簡單 log helper，統一資訊與錯誤輸出格式
info() { echo "[INFO] $*"; }
err()  { echo "[ERROR] $*" >&2; }

# 檢查系統上可用的 docker-compose 指令：優先使用 `docker compose`，無則退回到 `docker-compose`
# 成功時會設定全域陣列變數 DC_CMD，後續以 "${DC_CMD[@]}" 呼叫
detect_dc() {
    # 偵測新版的 docker CLI 的子命令 `docker compose`
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        DC_CMD=(docker compose)
    # 若環境只有舊版的獨立二進位 `docker-compose`，使用它
    elif command -v docker-compose >/dev/null 2>&1; then
        DC_CMD=(docker-compose)
    else
        # 無可用 compose 指令，回報錯誤並讓呼叫端處理
        err "Neither 'docker compose' nor 'docker-compose' found in PATH. Install Docker Compose."
        return 1
    fi
}

# 主流程：檢查 docker-compose、重建後端映像、啟動後端服務、打包前端 extension
main() {
    detect_dc

    info "Repository root: $REPO_ROOT"

    # 重建 backend 映像
    info "Building backend Docker image..."
    # 使用 docker compose build backend（依 docker-compose.yml 中的服務名稱）
    "${DC_CMD[@]}" build backend

    # 使用 docker compose up 重建並啟動 backend 容器
    info "Restarting backend service using docker compose..."
    # --no-deps 避免同時重建或重啟相依服務（例如 redis），僅針對 backend 服務做更新
    "${DC_CMD[@]}" up -d --force-recreate --no-deps backend

    # 列出目前 compose 中的服務狀態，方便除錯或確認
    info "Current docker-compose services status:"
    "${DC_CMD[@]}" ps

    # 前端 extension 的路徑（假設存放於 src/extension）
    EXT_DIR="$REPO_ROOT/src/extension"
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
                err "npm is not installed or not in PATH; skipping frontend packaging"
                return 1
            fi
        fi

        # 執行專案定義的包裝腳本（package），此處不對輸出做額外處理，讓 npm 的錯誤直接冒出
        info "Running: npm run package"
        npm run package
        info "Extension packaging finished"
    else
        # 找不到前端目錄時，記錄並略過打包步驟
        err "Extension directory not found: $EXT_DIR — skipping frontend packaging"
    fi

    info "Build script completed"
}

# 以參數呼叫主流程（保留原行為）
main "$@"
