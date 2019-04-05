FROM python:3.7-stretch as build

ADD . /src
WORKDIR /src
RUN python setup.py sdist
RUN cp dist/$(python setup.py --fullname).tar.gz dist/docsteady.tar.gz


FROM python:3.7-stretch

COPY --from=build /src/dist/docsteady.tar.gz /

ADD https://github.com/jgm/pandoc/releases/download/2.2.1/pandoc-2.2.1-1-amd64.deb /
RUN dpkg -i pandoc-2.2.1-1-amd64.deb
RUN pip install docsteady.tar.gz
WORKDIR /workspace
