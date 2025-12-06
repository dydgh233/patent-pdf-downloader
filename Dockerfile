FROM python:3.12-bullseye

# 필수 패키지 및 wkhtmltopdf 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    xfonts-75dpi \
    xfonts-base \
    fontconfig \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    libssl1.1 || true && \
    wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_amd64.deb && \
    apt-get install -y ./wkhtmltox_0.12.6.1-2.bullseye_amd64.deb || true && \
    rm -f wkhtmltox_0.12.6.1-2.bullseye_amd64.deb && \
    apt-get install -y fonts-nanum fonts-nanum-coding || true && \
    fc-cache -fv && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

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
