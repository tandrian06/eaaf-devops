FROM python:3.14-alpine

WORKDIR /app
COPY index.html .
USER 65532:65532
EXPOSE 8080
CMD ["python", "-B", "-m", "http.server", "8080", "--bind", "0.0.0.0"]
