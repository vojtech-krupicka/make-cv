# syntax=docker/dockerfile:1

FROM debian:bookworm-slim

# Avoid interactive prompts (e.g. tzdata) during apt installs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------
# System packages: Python 3 + a LaTeX toolchain providing latexmk/pdflatex.
#
# texlive-latex-extra / texlive-fonts-extra pull in a lot; trim this list
# down if you know exactly which LaTeX packages your template needs, or
# switch to `texlive-full` if you'd rather not think about it (much larger
# image).
# --------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        latexmk \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        lmodern \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so this layer is cached unless
# requirements.txt changes.
COPY requirements.txt .
# Debian's system Python is "externally managed" (PEP 668); this is an
# isolated container so installing system-wide is fine.
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY make_cv.py .

# Templates/data/output are expected to be mounted at runtime, e.g.:
#   docker run --rm -v "$PWD:/data" make_cv \
#       -t /data/template.tex.jinja -d /data/data.yaml -o /data/cv --pdf
WORKDIR /data

ENTRYPOINT ["python3", "/app/make_cv.py"]
CMD ["--help"]
