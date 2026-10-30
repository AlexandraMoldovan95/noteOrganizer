"""The door to the browser walk: a turn, a ceiling and a time limit for Edge.

    py site/tools/check_demo.py <folder for the photographs>

check_demo.mjs drives headless Microsoft Edge, which is a tree of
processes. Started bare it took no turn, had no ceiling and no time limit,
and a walk interrupted midway -- Ctrl+C, a closed terminal, a call that
timed out -- ended node before its clean-up, leaving about ten headless
Edge processes running (final audit, round eight). Through this door:

* guest.settle() takes the machine's turn and puts this runner in its job
  object, which node, Edge and every process Edge starts are in too (the
  job refuses breakaway): they end with this runner, however it ends;
* the walk has a time limit; past it, on Ctrl+C or when the walk is over,
  every other process in the job is ended at once (guest.end_others),
  Edge's included after node has gone, and a walk that left any is a
  failure;
* Edge's profile is in a marked scratch folder of this run's, handed to
  the walk as guest.DOOR_ENV: removed here, or by a later run's sweep if
  this one is killed. check_demo.mjs refuses to start without it.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The repository's tools/guest.py: site/tools/ is two folders down from it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
import guest  # noqa: E402

WALK = os.path.join(HERE, "check_demo.mjs")
# The whole walk, Edge's start included, at most.
LIMIT = 900


def main(argv):
    if len(argv) != 2:
        print("usage: py site/tools/check_demo.py <folder for the photographs>")
        return 2
    for line in guest.settle(label="check_demo " + argv[1]):
        print(line, flush=True)
    folder = guest.scratch("noteorg-site-walk-")
    env = dict(os.environ)
    env[guest.DOOR_ENV] = folder
    code, left = 1, 0
    try:
        walk = subprocess.Popen(["node", WALK, os.path.abspath(argv[1])], env=env)
        code = walk.wait(timeout=LIMIT)
    except subprocess.TimeoutExpired:
        print("HANG: the walk did not finish within %d s; it ends here, Edge with it" % LIMIT,
              flush=True)
        code = 124
    except KeyboardInterrupt:
        print("check_demo: stopped; the walk ends here, Edge with it", flush=True)
        code = 130
    except OSError as exc:      # no node on this computer's PATH
        print("check_demo: node could not be started (%s)" % exc)
        code = 2
    finally:
        left = guest.end_others() or 0
        guest.remove(folder)
    if left and code not in (124, 130):
        print("FAIL the walk left %d process(es) running when it ended; ended now" % left)
        code = code or 1
    peak = guest.memory_peak()
    if peak:
        print(peak)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
