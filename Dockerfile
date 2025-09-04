FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 複製只需要的檔案以加速建構（只帶入必要的 package）
COPY pyproject.toml pyproject.toml
COPY src/__init__.py src/__init__.py
COPY src/api/ src/api/
COPY src/trailtag/ src/trailtag/

# 安裝套件
RUN pip install --upgrade pip setuptools wheel \
  && pip install . --no-cache-dir

# 暴露埠號
EXPOSE 8010

# 預設啟動命令
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8010"]
