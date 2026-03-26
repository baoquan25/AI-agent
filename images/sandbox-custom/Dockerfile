FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NVM_DIR=/usr/local/nvm \
    NODE_VERSION=22.14.0

SHELL ["/bin/bash", "-lc"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git ca-certificates ripgrep sudo \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

RUN python -m pip install --retries 10 --timeout 180 \
    pandas ipykernel pytz bs4

RUN python -m pip install --retries 10 --timeout 180 \
    VNSFintech lightweight-charts

RUN useradd -m daytona \
    && mkdir -p /etc/sudoers.d \
    && echo "daytona ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/91-daytona \
    && chmod 0440 /etc/sudoers.d/91-daytona

RUN mkdir -p $NVM_DIR \
    && curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash \
    && source $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default \
    && npm install -g ts-node@10.9.2 typescript@5.9.3 typescript-language-server@5.1.3

ENV NODE_PATH=$NVM_DIR/versions/node/v$NODE_VERSION/lib/node_modules
ENV PATH=$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH

USER daytona

RUN mkdir -p /usr/local/lib

ENTRYPOINT ["sleep", "infinity"]