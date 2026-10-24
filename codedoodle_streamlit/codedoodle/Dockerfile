FROM python:3.12-slim

# g++ is only needed if you want the Run button to work for C++.
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/codedoodle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY .streamlit ./.streamlit
COPY streamlit_app.py .

# Run as an unprivileged user.
RUN useradd --create-home runner
USER runner

# Never bake the key into the image. Pass it at runtime:
#   docker run -p 8501:8501 -e GEMINI_API_KEY=... codedoodle
# For any public deployment also pass -e ENABLE_RUN=0.
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
