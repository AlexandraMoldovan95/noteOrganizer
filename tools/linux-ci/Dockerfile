# The CI Linux job, reproduced locally.
#
# Mirrors .github/workflows/tests.yml's ubuntu leg: Python 3.13, Tk,
# Xvfb as the virtual display, DejaVu fonts (the metrics several checks
# learned to respect) and no colour emoji font (CI removes the runner's
# to match), and Pillow -- the app's one dependency. Running
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

# git is here for the language gate, not for version control: it asks git
# which files are TRACKED, and refuses to run at all outside a checkout
# rather than reporting "0 files, all clean" -- a gate that cannot pass
# vacuously. Without git in the image, the one check that reads every
# tracked file was the only thing this image could not reproduce, and it
# failed here for a reason that has nothing to do with the code.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tk xvfb xauth fonts-dejavu-core git \
    && rm -rf /var/lib/apt/lists/* \
    # The official python image links _tkinter against the system tcl/tk;
    # prove it at build time rather than discovering it at run time.
    && python -c "import tkinter; print('tkinter', tkinter.TkVersion)"

RUN pip install --no-cache-dir Pillow

WORKDIR /repo
ENTRYPOINT ["/bin/sh", "-c", "xvfb-run -a python tools/run_tests.py \"$@\"", "--"]
