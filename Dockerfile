FROM python:3.11-slim

# system dependencies (required by rembg / pillow / onnx)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy requirements first (better layer caching)
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# copy application
COPY . .

# make sure folders exist
RUN mkdir -p uploads outputs assets

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]