FROM python:3.11-bookworm as build

WORKDIR /app
COPY . .

# Upgrade and install pandoc
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    pandoc &&  \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --root-user-action=ignore --upgrade pip

# Install docsteady python requirements
RUN pip install --root-user-action=ignore -r docsteady/requirements/main.in

# Install local docsteady
RUN pip install --root-user-action=ignore .

# Set the pythonpath
ENV PYTHONPATH "${PYTHONPATH}:/app/docsteady"

# Run a bash login shell as default
# CMD ["/bin/bash", "-l"]
CMD python -c "print('Docker for docsteady is in place')"
