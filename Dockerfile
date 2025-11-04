# Use Ubuntu as base
FROM ubuntu:22.04

# Install dependencies
RUN apt update && apt install -y \
    python3-pip python3-venv zip unzip openjdk-17-jdk \
    build-essential git curl wget \
    zlib1g-dev libffi-dev libssl-dev libncurses5 libncurses5-dev \
    libreadline-dev libsqlite3-dev libbz2-dev liblzma-dev libgdbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a builder user
RUN useradd --create-home builder
USER builder
WORKDIR /home/builder

# Install Buildozer and related Python packages
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --user buildozer cython virtualenv

# Add Buildozer to PATH
ENV PATH="/home/builder/.local/bin:$PATH"

# Set entrypoint to Buildozer
ENTRYPOINT ["buildozer"]
