# One image for both services; compose picks the command.
FROM python:3.14-slim

WORKDIR /code
# Requirements first: code changes don't redo pip install.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
