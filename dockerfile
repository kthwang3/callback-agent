FROM python:3.14-slim
WORKDIR /usr/src/app

# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code
COPY main.py db.py sms.py ./
EXPOSE 8080

RUN useradd app
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]