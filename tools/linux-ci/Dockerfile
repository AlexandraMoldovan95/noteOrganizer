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
# Build once, and run it, only through the runner (from the repo root):
#   py tools/linux_ci.py --build
#   py tools/linux_ci.py              # the whole suite
#   py tools/linux_ci.py qa5          # one script
# The repo is mounted read-only and run_tests.py does its own scratch-copy
# ritual inside the container's /tmp. The runner gives the container a
# name, a memory limit, a time limit and docker's init, and ends it when
# the runner goes: a killed docker client leaves a container running on
# (final audit, round seven). The ENTRYPOINT below is what CI's leg does;
# the runner replaces it with its bounded one, so changing it means a
# rebuild for nothing.

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

# The version requirements.txt pins; tools/check_shipped.py keeps them equal.
RUN pip install --no-cache-dir Pillow==13.0.0

WORKDIR /repo
ENTRYPOINT ["/bin/sh", "-c", "xvfb-run -a python tools/run_tests.py \"$@\"", "--"]
