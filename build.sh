#!/bin/bash
python setup.py sdist
cp dist/$(python setup.py --fullname).tar.gz dist/docsteady.tar.gz
