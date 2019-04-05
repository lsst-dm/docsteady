#!/bin/bash

set -e

TAG=$1

if [[ -z ${TAG} ]]; then
    printf "Need a tag\n"
    exit 1
fi

printf "Releasing ${TAG}...\n"

# Tag repo
git tag -a -m "${TAG} Release" ${TAG}

# Some tags get a different python version, 1.1pre1 -> 1.1rc1
export PYTHON_VERSION=$(python setup.py --version)
export FULLNAME=$(python setup.py --fullname)

# Build
docker build -t lsstdm/docsteady:${PYTHON_VERSION} .
docker tag lsstdm/docsteady:${PYTHON_VERSION} lsstdm/docsteady:latest

printf "Push tag, containers\n"

# If you haven't already...
# docker login
docker push lsstdm/docsteady:${PYTHON_VERSION
docker push lsstdm/docsteady:latest

printf "Pushing Tag"
git push origin ${TAG}

# Upload with twine (pip install twine). You should have configired your ~/.pypirc
printf "Success.\nPlease execute `twine upload dist/${FULLNAME}.tar.gz`\n"
