"""Run the Linux CI image: bounded, named, and gone on every way out.

WHY THIS EXISTS
---------------
The Linux leg of CI runs locally in Docker (tools/linux-ci/Dockerfile). A
plain ``docker run`` of it was the documented command, and a docker client
that is killed -- a closed terminal, an agent's call that timed out --
leaves its container running in Docker's VM: nothing is signalled into the
container, and the suite ran on for tens of minutes, out of sight, while
the next run started beside it (final audit, round seven). Two heavy jobs
at once is how the computer went down (ISSUES_LOG: "The test that took the
computer down"). This is the one door to the image, and every document
uses it:

* it takes this machine's turn and the memory ceiling (tools/guest.py),
  so the docker client is in the runner's job and ends with it;
* the container has a name of its own (noteorg-ci-<pid>), a memory limit
  with no swap, two CPUs and a cap on its processes, and docker's init as
  its first process;
* inside, the run has a time limit of its own (``timeout -k``), and a
  watcher on the container's input, which this runner holds open and never
  writes: when the runner goes, however it goes, the input closes and the
  container ends itself;
* on every other way out (an error, Ctrl+C) the runner removes its own
  container by name, and a later run removes any that a dead run left
  (found by their label and the dead run's pid -- never another project's);
* it ends by printing the container's memory peak (cgroup memory.peak).

USAGE
-----
    py tools/linux_ci.py                  # the whole suite: tools/run_tests.py in the image
    py tools/linux_ci.py qa5 static       # whatever run_tests.py would select
    py tools/linux_ci.py --script qa/probe_bar_width.py
                                          # one script, in a throwaway copy inside the container
    py tools/linux_ci.py --probe <folder under %TEMP%>/probe.py
                                          # an audit's own probe, run as --script is; its
                                          # folder is /work, the one place it may write
    py tools/linux_ci.py --limit 1800 ... # the run's own time limit, in seconds
    py tools/linux_ci.py --build          # build the image once (tools/linux-ci/Dockerfile)

Exits with the run's code: 124 is a run stopped at its time limit (HANG),
137 one killed outright (the memory limit, when the line above says so).

After a Linux run, Docker's VM keeps the memory it took until it is shut
down: ``wsl --shutdown`` gives it back to Windows (qa/README, "Running
anything here").
"""

import os
import subprocess
import sys
import tempfile
import threading

import guest  # tools/guest.py: this machine's turn and the memory ceiling

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMAGE = "noteorg-linux-ci"
LABEL = "noteorg.ci"

# The container's share of Docker's VM. Measured: a full run peaks at a few
# hundred MB (qa/README, "Running anything here"); the VM has about 2.8 GB.
MEMORY = "1536m"
CPUS = "2"
PIDS = "512"
# The run's own time limit inside the container, and how much longer the
# runner waits for it before removing the container itself.
LIMIT_SUITE = 3600
LIMIT_SCRIPT = 600
GRACE = 60

# The script the container runs. $1 is the time limit; the rest is either
# run_tests.py's arguments, "--script <path in the repository>" or
# "--probe <name in /work>".
INSIDE = r"""
limit="$1"; shift
exec 3<&0
{ cat <&3 >/dev/null
  echo "linux_ci: the runner that started this container is gone -- ending it" >&2
  kill -TERM $$ 2>/dev/null; } &
if [ "$1" = "--script" ] || [ "$1" = "--probe" ]; then
  work=$(mktemp -d)
  cp /repo/note_organizer.py /repo/tools/guest.py /repo/qa/_qa_support.py "$work"/
  cp -r /repo/noteorganizer "$work"/
  if [ "$1" = "--script" ]; then cp "/repo/$2" "$work"/; else cp "/work/$2" "$work"/; fi
  cd "$work" || exit 2
  set -- python "$(basename "$2")"
else
  set -- python tools/run_tests.py "$@"
fi
start=$(date +%s)
timeout -k 10 "$limit" xvfb-run -a "$@" 3<&- </dev/null
status=$?
took=$(( $(date +%s) - start ))
peak=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)
max=$(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo max)
ooms=$(sed -n 's/^oom_kill //p' /sys/fs/cgroup/memory.events 2>/dev/null)
[ "$max" = max ] && max_mb="no limit" || max_mb="$(( max / 1048576 )) MB"
echo "container: memory at most $(( peak / 1048576 )) MB, of $max_mb (cgroup memory.peak); ${took} s"
if [ "${ooms:-0}" -gt 0 ]; then
  echo "KILLED: the container's memory limit was reached ($ooms process(es) killed by the kernel)"
elif [ "$status" -eq 124 ] || { [ "$status" -eq 137 ] && [ "$took" -ge "$limit" ]; }; then
  echo "HANG: the run did not finish within $limit s and was stopped"
fi
exit $status
"""


def docker(*args, timeout=120):
    return subprocess.run(["docker"] + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def remove(name):
    """Remove this runner's own container, if it is still there."""
    try:
        docker("rm", "-f", name, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        pass


def sweep():
    """Remove the containers dead runs of this runner left: only those with
    this runner's label, and only when the run that started them is gone."""
    try:
        listed = docker("ps", "-a", "--filter", "label=%s=1" % LABEL, "--format",
                        '{{.Names}}\t{{.Label "%s.pid"}}\t{{.Label "%s.born"}}' % (LABEL, LABEL))
    except (OSError, subprocess.TimeoutExpired):
        return
    for line in listed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("noteorg-ci-"):
            continue
        try:
            pid, born = int(parts[1]), float(parts[2]) if parts[2] else None
        except ValueError:
            continue
        if not guest.alive(pid, born):
            print("linux_ci: removing %s, left by a run that died" % parts[0])
            remove(parts[0])


def build():
    print("linux_ci: docker build -t %s tools/linux-ci" % IMAGE, flush=True)
    try:
        return subprocess.run(["docker", "build", "-t", IMAGE, os.path.join(ROOT, "tools", "linux-ci")],
                              timeout=1800).returncode
    except subprocess.TimeoutExpired:
        print("HANG: the build did not finish within 1800 s")
        return 124


def worktree_git():
    """The docker arguments that let git read a worktree inside the image.

    A git worktree's .git is a file naming its git folder by a Windows path,
    which git in the container cannot follow: the two gates that ask git
    what is tracked then refuse to run. The repository's common git folder
    is mounted read-only beside /repo, and git is pointed at this worktree's
    folder inside it. A plain checkout needs nothing."""
    dot_git = os.path.join(ROOT, ".git")
    if not os.path.isfile(dot_git):
        return []
    with open(dot_git, encoding="utf-8") as fh:
        gitdir = fh.read().strip().partition("gitdir:")[2].strip()
    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            common = os.path.normpath(os.path.join(gitdir, fh.read().strip()))
    except OSError:
        return []
    inside = os.path.relpath(os.path.normpath(gitdir), common).replace(os.sep, "/")
    return ["--mount", "type=bind,source=%s,target=/gitcommon,readonly" % common,
            "-e", "GIT_DIR=/gitcommon/%s" % inside, "-e", "GIT_WORK_TREE=/repo",
            "-e", "GIT_CONFIG_COUNT=1", "-e", "GIT_CONFIG_KEY_0=safe.directory",
            "-e", "GIT_CONFIG_VALUE_0=*"]


def probe_folder(path):
    """The folder an audit's own probe is in, mounted read-write at /work: a
    .py file in a folder below the temporary folder and outside this
    repository -- never the temporary folder itself, which holds every other
    run's. Read through its links, so a link cannot carry /work elsewhere.
    An audit's agents may not write in the repository, and a docker run of
    their own is what left containers running (final audit, round eight)."""
    real = os.path.realpath(path)
    folder = os.path.dirname(real)

    def below(p, top):
        return os.path.normcase(p).startswith(os.path.normcase(os.path.realpath(top)) + os.sep)

    if (real.endswith(".py") and os.path.isfile(real)
            and below(folder, tempfile.gettempdir()) and not below(real, ROOT)):
        return folder
    return None


def run(args, limit, mounts=()):
    name = "noteorg-ci-%d" % os.getpid()
    born = guest.born_at(os.getpid())
    cmd = ["docker", "run", "--rm", "--init", "-i", "--name", name,
           "--label", "%s=1" % LABEL, "--label", "%s.pid=%d" % (LABEL, os.getpid()),
           "--label", "%s.born=%s" % (LABEL, "" if born is None else "%.3f" % born),
           "--memory", MEMORY, "--memory-swap", MEMORY, "--cpus", CPUS,
           "--pids-limit", PIDS, "-e", "PYTHONUNBUFFERED=1",
           "--mount", "type=bind,source=%s,target=/repo,readonly" % ROOT] + worktree_git()
    cmd += list(mounts)
    cmd += ["--entrypoint", "/bin/sh", IMAGE, "-c", INSIDE, "linux_ci", str(limit)] + args
    print("linux_ci: %s, at most %s of memory, %s CPUs, %d s" % (name, MEMORY, CPUS, limit),
          flush=True)
    # The input is held open and never written: its closing is what tells
    # the container that this runner is gone.
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    reader = threading.Thread(target=_echo, args=(proc.stdout,), daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=limit + GRACE)
    except subprocess.TimeoutExpired:
        print("HANG: the container outlived its own limit by %d s; removing it" % GRACE)
        code = 124
    finally:
        remove(name)
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        reader.join(timeout=10)
    return code


def _echo(stream):
    for raw in iter(stream.readline, b""):
        sys.stdout.write(raw.decode("utf-8", "replace"))
        sys.stdout.flush()


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = list(argv[1:])
    limit = None
    if "--limit" in args:
        at = args.index("--limit")
        limit = int(args[at + 1])
        del args[at:at + 2]
    mounts = []
    if args[:1] == ["--probe"]:
        # Asked before the turn: a wrong path is said at once, not after a wait.
        folder = probe_folder(args[1]) if len(args) == 2 else None
        if folder is None:
            print("linux_ci: --probe takes one .py file in a folder of its own below %s, "
                  "outside this repository" % tempfile.gettempdir())
            return 2
        mounts = ["--mount", "type=bind,source=%s,target=/work" % folder]
        args = ["--probe", os.path.basename(os.path.realpath(args[1]))]
    for line in guest.settle(label="linux_ci " + " ".join(args)):
        print(line)
    sweep()
    if args == ["--build"]:
        return build()
    if docker("image", "inspect", IMAGE, "--format", "{{.Id}}").returncode != 0:
        print("linux_ci: there is no %s image here; build it once with "
              "py tools/linux_ci.py --build" % IMAGE)
        return 2
    if args[:1] == ["--script"]:
        if len(args) != 2 or not os.path.isfile(os.path.join(ROOT, args[1])):
            print("linux_ci: --script takes one script of this repository, e.g. "
                  "qa/probe_bar_width.py")
            return 2
        args = ["--script", args[1].replace("\\", "/")]
    try:
        return run(args, limit or (LIMIT_SCRIPT if args[:1] in (["--script"], ["--probe"])
                                   else LIMIT_SUITE), mounts)
    except KeyboardInterrupt:
        print("linux_ci: stopped; the container is removed")
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv))
