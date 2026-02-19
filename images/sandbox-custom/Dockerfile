FROM python:3.11-slim

# tắt bộ nhớ đệm & tắt buffer
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git ca-certificates ripgrep \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*


# Cài thư viện Python
RUN python -m pip install --no-cache-dir \
    pandas matplotlib seaborn ipykernel pytz bs4 \
    VNSFintech lightweight-charts

# Tạo user daytona (bắt buộc cho Daytona)
RUN useradd -m daytona 
USER daytona

# BẮT BUỘC: Container phải chạy liên tục
ENTRYPOINT ["sleep", "infinity"]
