FROM python:3.12-slim

WORKDIR /app
COPY backend/ /app/

EXPOSE 8140
CMD ["python", "dispatch_server.py"]
