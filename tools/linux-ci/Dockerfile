# The CI Linux job, reproduced locally.
#
# Mirrors .github/workflows/tests.yml's ubuntu leg: Python 3.13, Tk,
# Xvfb as the virtual display, DejaVu fonts (the metrics several checks
# learned to respect), and Pillow -- the app's one dependency. Running
# the suite here BEFORE a push catches the Linux-only behaviours (async
# window mapping, focus semantics, font metrics) that used to surface
# only as a red CI run.
#
# Build once (from the repo root):
#   docker build -t noteorg-linux-ci tools/linux-ci
# Run the whole suite (repo mounted read-only; run_tests.py does its own
# scratch-copy ritual inside the container's /tmp):
#   docker run --rm -v "${PWD}:/repo:ro" noteorg-linux-ci
# One script:
#   docker run --rm -v "${PWD}:/repo:ro" noteorg-linux-ci qa5

FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tk xvfb xauth fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    # The official python image links _tkinter against the system tcl/tk;
    # prove it at build time rather than discovering it at run time.
    && python -c "import tkinter; print('tkinter', tkinter.TkVersion)"

RUN pip install --no-cache-dir Pillow

WORKDIR /repo
ENTRYPOINT ["/bin/sh", "-c", "xvfb-run -a python tools/run_tests.py \"$@\"", "--"]
