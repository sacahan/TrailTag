
#!/usr/bin/env zsh

set -euo pipefail

# 簡單 log helper，統一資訊與錯誤輸出格式
info() { echo "[INFO] $*"; }
err()  { echo "[ERROR] $*" >&2; }

# 取得腳本所在目錄與專案根目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

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


# 預設要支援的平台
# PLATFORMS="linux/amd64,linux/arm64"
PLATFORMS="linux/amd64"
# 預設的映像名稱
IMAGE_NAME="sacahan/trailtag-backend"

# 檢查 Docker 是否安裝
if ! command -v docker &> /dev/null
then
    err "Docker 未安裝，請先安裝 Docker。"
    exit 1
fi

BUILDER_NAME="multiarch-builder"
if ! docker buildx inspect "$BUILDER_NAME" &> /dev/null; then
    info "建立 buildx builder: $BUILDER_NAME"
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --use
else
    info "使用已存在的 buildx builder: $BUILDER_NAME"
    docker buildx use "$BUILDER_NAME"
fi
docker buildx inspect --bootstrap
info "註冊 QEMU multiarch binfmt 支援 (需要 Docker 允許 --privileged) ..."
docker run --rm --privileged tonistiigi/binfmt:latest --install all || \
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes || true

DOCKERFILE_PATH="$PROJECT_ROOT/Dockerfile"
IMAGE_TAG="${IMAGE_NAME}:latest"
info "建置並推送多平台映像: image=$IMAGE_TAG, dockerfile=$DOCKERFILE_PATH"
# buildx --push 只推送，不保留本地 image
docker buildx build --platform "$PLATFORMS" --push -t "$IMAGE_TAG" -f "$DOCKERFILE_PATH" "$PROJECT_ROOT"
