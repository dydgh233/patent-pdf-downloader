FROM python:3.12-slim

# apt 캐시 정리 및 wkhtmltopdf 설치 (재시도 로직 포함)
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    fonts-nanum \
    fonts-nanum-coding \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . .

# 포트 설정
EXPOSE 10000

# 실행
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
