FROM python:3.12-slim

RUN useradd --create-home appuser
RUN pip install --no-cache-dir streamlit requests

COPY . /app
WORKDIR /app

USER appuser
EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
