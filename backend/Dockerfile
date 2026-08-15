FROM python:3.12-slim

WORKDIR /app

# libsndfile1 은 soundfile(음독 VAD)이 요구하는 시스템 라이브러리다.
# slim 이미지에 기본 포함되지 않아, 없으면 VAD 가 비활성으로 떨어진다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 시작 스크립트
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
