FROM python:3.6-stretch


ADD https://github.com/jgm/pandoc/releases/download/2.2.1/pandoc-2.2.1-1-amd64.deb /
RUN dpkg -i pandoc-2.2.1-1-amd64.deb
COPY setup.py /
COPY docsteady /docsteady
RUN python setup.py install
WORKDIR /workspace
