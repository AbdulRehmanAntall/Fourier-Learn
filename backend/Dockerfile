# Development image for the FourierLearn backend (source is bind-mounted by docker-compose).
FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# System tools Manim needs: FFmpeg, LaTeX (for MathTex), Cairo/Pango + build tools for pycairo,
# and espeak-ng, the local narration voice.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libcairo2-dev \
        libpango1.0-dev \
        ffmpeg \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-science \
        cm-super \
        dvisvgm \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The venv lives in its own named volume at /app/.venv (see docker-compose.yml),
# so it never mixes with a host-side backend/.venv.
ENV VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

COPY requirements.txt requirements-dev.txt docker-entrypoint.sh ./
RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt \
    && cat requirements.txt requirements-dev.txt | sha256sum > "$VIRTUAL_ENV/.requirements.sha256"

COPY . .

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]
