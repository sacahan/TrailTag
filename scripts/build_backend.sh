#!/usr/bin/env zsh

set -euo pipefail

# 簡單 log helper，統一資訊與錯誤輸出格式
info() { echo "[INFO] $*"; }
err()  { echo "[ERROR] $*" >&2; }

# 取得腳本所在目錄與專案根目錄
SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"

info "=== 開始後端建制流程 ==="

# 預設要支援的平台
# PLATFORMS="linux/amd64,linux/arm64"
PLATFORMS="linux/amd64"
# 預設的映像名稱
IMAGE_NAME="sacahan/trailtag-backend"

# 檢查 Docker 是否安裝
if ! command -v docker &> /dev/null; then
    err "Docker 未安裝，請先安裝 Docker。"
    err "=== 後端建制失敗 ==="
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

info "=== 後端建制完成 ==="
