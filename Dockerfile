FROM python:3.11-slim

WORKDIR /app

ENV FLASK_APP=run.py

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

EXPOSE 80

CMD ["./start.sh"]