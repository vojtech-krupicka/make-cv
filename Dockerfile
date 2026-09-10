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
        git \
        sudo \
        nano \
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

# Create and set user to vscode
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID --shell /bin/bash -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME

COPY make_cv.py .

ENTRYPOINT ["python3", "/app/make_cv.py"]
CMD ["--help"]
