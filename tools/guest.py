"""How a test run behaves as a guest on the computer it runs on.

On 2026-10-29 a mutant made a qa check size its fixture from a bound the
mutant had turned into a billion: one python.exe took 43 GB, Windows ran out
of memory, its desktop window manager crashed, and the shadow copies of C:
were deleted under the load (ISSUES_LOG: "The test that took the computer
down"). Three heavy jobs were running at once. Every runner calls
``settle()`` first, before it builds the app or starts anything, and it does
these things:

1. One heavy job at a time, on the whole machine. A run takes an OS lock on
   ``noteorg-guest.lock`` in the temporary folder, which the OS frees when
   the run ends, however it ends. A second run waits, saying whose turn it
   is. The processes a holder starts share its turn (NOTEORG_GUEST_HOLDER,
   and failing that their parentage), so a child never waits on its parent.
   ``heavy=False`` is for a tool whose children are small and short (git, a
   static check), never for one that builds the app or runs a suite.
2. The memory ceiling for this process and everything it starts. On
   Windows a job object holds each process's committed memory and all of
   theirs together, and ends them with the runner. Elsewhere RLIMIT_AS, per
   process, never above half of what the box has (a container's cgroup
   limit, else MemTotal): above that, the kernel's OOM killer arrives first,
   with SIGKILL and no footer. A test past it gets MemoryError and fails
   like any check.
3. The leftovers of runs that died. A scratch folder made with
   ``scratch()`` carries a marker naming the process that made it; a later
   run removes the ones whose process is gone. Nothing without the marker
   is ever touched.
4. Homes of its own. APPDATA, LOCALAPPDATA and XDG_DATA_HOME name empty
   folders of the run's own, for it and every process it starts: the app
   run from source reads %APPDATA%\\NoteOrganizer, where the built app kept
   the owner's notebook until 2026-10-27, and an app started in an empty
   folder copies that notebook in. One test did, on every Windows run of
   the suite (final audit, round eight). USERPROFILE is left as it is: git
   and docker read their settings there, and only the built app keeps a
   notebook under it.
5. A floor under the disk. On Windows a heavy run does not start, and
   ends itself and everything it started, when the drive its scratch is on
   has less than DISK_FLOOR_MB free: nothing else bounds what a runaway
   test writes, and a full C: is where Windows deletes its restore points.

A runner in another language (a browser walk in JavaScript) is started
through a Python door that settles first and hands it DOOR_ENV, a marked
scratch folder of the run's own; the script refuses to start without it.

The figures are sized from measurements (qa/README, "Running anything
here"), not from the incident. The scratch stays on the system's temporary
folder: moved to an exFAT drive, a test of NTFS's Zone.Identifier stream
failed, and the notebooks the tests stand in for live on NTFS.
"""

import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time

PER_PROCESS_MB = 1024
ALL_TOGETHER_MB = 2048
# What a heavy run leaves free on its scratch's drive: room for Windows to
# page out a whole run at its ceiling (ALL_TOGETHER_MB), and 1 GB for
# itself. Overridden by DISK_ENV (in MB; 0 turns it off).
DISK_FLOOR_MB = ALL_TOGETHER_MB + 1024
DISK_ENV = "NOTEORG_GUEST_DISK_FLOOR_MB"
# How often a run looks, in seconds, and its exit code when it is short.
DISK_POLL_S = 2
DISK_LOW = 74
# Set by a Python door for the script in another language it starts: a
# marked scratch folder of the run's own, which the script checks for.
DOOR_ENV = "NOTEORG_GUEST_DOOR"

# Where the lock lives: the temporary folder, or this (the gate's own tests).
LOCK_DIR_ENV = "NOTEORG_GUEST_LOCK_DIR"
# "pid token lock-folder" of the run whose turn it is, for its children.
HOLDER_ENV = "NOTEORG_GUEST_HOLDER"
# How long a run waits for its turn, in seconds; 0 refuses at once.
WAIT_ENV = "NOTEORG_GUEST_WAIT"
WAIT_S = 3600
# The exit code of a run that did not get its turn (EX_TEMPFAIL: try later).
BUSY = 75
# The folder holding this run's own homes, for its children.
HOMES_ENV = "NOTEORG_GUEST_HOMES"
# Where programs keep a person's data, by the variable that names the place.
HOME_VARS = ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME")

LOCK_NAME = "noteorg-guest.lock"
HOLDER_NAME = "noteorg-guest.holder"

# The scratch marker. Not a .json: run_tests and the qa scripts wipe *.json
# in their working folder, and the marker must outlive that.
MARKER = ".noteorg-scratch"
# Only folders named so are even opened to look for a marker.
PREFIXES = ("notesorg-", "noteorg-", "look-", "story-", "audit-")
# A folder a run kept on purpose (a story's photographs) goes after this.
KEPT_DAYS = 7

_job = None        # held for the run's life: its processes end when it closes
_lock_file = None  # held for the run's life: the OS frees the lock with it
_token = None


def settle(per_process_mb=PER_PROCESS_MB, all_together_mb=ALL_TOGETHER_MB,
           label=None, heavy=True, wait_s=None):
    """Give this run homes of its own, take its turn (when heavy), set the
    memory ceiling, remove what dead runs left, and keep a floor under the
    disk. Returns the lines a runner prints. A run that does not get its
    turn within ``wait_s`` exits with BUSY, one short of disk with
    DISK_LOW; a ceiling the OS will not set is said, never silent, and
    never refuses a run."""
    homes = own_homes()   # first, before anything could start the app's code
    lines = []
    if heavy:
        lines.append(take_turn(label, wait_s))
    lines.append(cap_memory(per_process_mb, all_together_mb))
    lines.append(homes)
    if heavy and _lock_file is not None:
        swept = sweep()
        if swept:
            lines.append(swept)
        # After the sweep, which may give back what dead runs left.
        floor = guard_disk()
        if floor:
            lines.append(floor)
    return lines


def guard_disk(floor_mb=None):
    """Refuse a heavy run below the floor, and watch the drive while it
    runs; returns the line to print, or '' where there is no floor. Only
    where this run holds a job to end everything with (Windows): the Linux
    image's /tmp is a tmpfs sized inside its memory limit (linux_ci.py)."""
    if _job is None or _watching:
        return ""
    if floor_mb is None:
        try:
            floor_mb = int(os.environ.get(DISK_ENV, DISK_FLOOR_MB))
        except ValueError:
            floor_mb = DISK_FLOOR_MB
    if floor_mb <= 0:
        return ""
    folder = tempfile.gettempdir()
    free = _free_mb(folder)
    if free is not None and free < floor_mb:
        print("disk    : REFUSED -- %s has %s MB free, under the floor of %s MB a run "
              "leaves; free some space and try again" % (folder, format(free, ","),
                                                          format(floor_mb, ",")), flush=True)
        raise SystemExit(DISK_LOW)
    _watching.append(floor_mb)
    threading.Thread(target=_watch_disk, args=(folder, floor_mb), daemon=True).start()
    return ("disk    : %s MB free where runs write; this run ends itself below %s MB"
            % ("?" if free is None else format(free, ","), format(floor_mb, ",")))


_watching = []   # the floor, once a run watches its drive


def _free_mb(folder):
    try:
        return shutil.disk_usage(folder).free // (1024 * 1024)
    except OSError:
        return None


def _watch_disk(folder, floor_mb):
    while True:
        time.sleep(DISK_POLL_S)
        free = _free_mb(folder)
        if free is not None and free < floor_mb:
            print("disk    : STOPPED -- %s has %s MB free, under the floor of %s MB: this "
                  "run and everything it started end here" % (folder, format(free, ","),
                                                              format(floor_mb, ",")), flush=True)
            # Its job closes with it, and ends every process in it.
            os._exit(DISK_LOW)


def end_others():
    """End every process this run started, and every one they started: on
    Windows, every process in this run's job but this one. A tree whose
    root has died is still in the job, where its parentage no longer leads
    (Edge, after node is gone). Returns how many were ended; None where
    there is no job to ask."""
    if sys.platform != "win32" or _job is None:
        return None
    ctypes, k32, _ = _structures()
    import ctypes.wintypes as wt

    class Listed(ctypes.Structure):
        _fields_ = [("Assigned", wt.DWORD), ("InList", wt.DWORD),
                    ("Ids", ctypes.c_size_t * 4096)]

    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.TerminateProcess.argtypes = [wt.HANDLE, ctypes.c_uint]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    ended = set()
    for _ in range(10):   # one being ended may start another on its way out
        listed = Listed()
        k32.QueryInformationJobObject(_job, 3, ctypes.byref(listed),   # BasicProcessIdList
                                      ctypes.sizeof(listed), None)
        others = [pid for pid in listed.Ids[:listed.InList] if pid != os.getpid()]
        if not others:
            break
        for pid in others:
            handle = k32.OpenProcess(0x0001, False, pid)               # PROCESS_TERMINATE
            if handle:
                if k32.TerminateProcess(handle, 1):
                    ended.add(pid)
                k32.CloseHandle(handle)
        time.sleep(0.2)
    return len(ended)


def own_homes():
    """Point HOME_VARS at empty folders of this run's own, for it and every
    process it starts; returns the line to print. A child of a run keeps
    the homes its parent was given."""
    inherited = os.environ.get(HOMES_ENV, "")
    if inherited and os.path.isdir(inherited) and all(
            _inside(os.environ.get(var, ""), inherited) for var in HOME_VARS):
        return "homes   : the run that started this one's (%s)" % inherited
    # Python's folder for packages a person installed for themselves is
    # under APPDATA: named where it is, so the run still finds them.
    import site
    os.environ.setdefault("PYTHONUSERBASE", site.getuserbase())
    homes = scratch("noteorg-homes-")
    for var in HOME_VARS:
        path = os.path.join(homes, var.lower())
        os.makedirs(path, exist_ok=True)
        os.environ[var] = path
    os.environ[HOMES_ENV] = homes
    import atexit
    atexit.register(remove, homes)
    return ("homes   : %s are this run's own, empty (%s): the app's code it runs "
            "finds no notebook of the owner's there" % (", ".join(HOME_VARS), homes))


def _inside(path, folder):
    return bool(path) and os.path.normcase(os.path.abspath(path)).startswith(
        os.path.normcase(os.path.abspath(folder)) + os.sep)


def cap_memory(per_process_mb=PER_PROCESS_MB, all_together_mb=ALL_TOGETHER_MB):
    try:
        if sys.platform == "win32":
            _cap_windows(per_process_mb, all_together_mb)
            return ("memory  : at most %s MB a process, %s MB in all"
                    % (format(per_process_mb, ","), format(all_together_mb, ",")))
        # Address space, not memory used: Python and Tk reserve more than
        # they touch, so twice the Windows figure -- but never more than
        # half of what this box has, or the OOM killer comes first.
        limit, box = posix_limit_mb(per_process_mb)
        _cap_posix(limit)
        return ("memory  : at most %s MB of address space a process (%s)"
                % (format(limit, ","), box))
    except Exception as exc:   # an OS without the call, or a job that refuses one
        return "memory  : NO ceiling set (%s)" % exc


def posix_limit_mb(per_process_mb=PER_PROCESS_MB):
    """The address-space ceiling for one process here, and what it is half of."""
    box_mb, where = box_memory_mb()
    if box_mb is None:
        return per_process_mb * 2, "this box's memory unknown"
    limit = min(per_process_mb * 2, box_mb // 2)
    return limit, "this box has %s MB, %s" % (format(box_mb, ","), where)


def box_memory_mb():
    """What this box has: a cgroup's memory limit when one is set (a
    container), else the machine's MemTotal."""
    for path in ("/sys/fs/cgroup/memory.max",                     # cgroup v2
                 "/sys/fs/cgroup/memory/memory.limit_in_bytes"):  # cgroup v1
        try:
            with open(path) as fh:
                text = fh.read().strip()
        except OSError:
            continue
        if text.isdigit() and int(text) < (1 << 60):
            return int(text) // (1024 * 1024), "its cgroup limit"
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024, "MemTotal"
    except OSError:
        pass
    return None, ""


def memory_peak():
    """The line a runner prints at the end: the most one process took, and
    on Windows all of them together; '' where it is not known."""
    try:
        if sys.platform == "win32":
            if _job is None:
                return ""
            info = _query(_job)
            mb = 1024 * 1024
            return ("memory  : the largest process took %s MB, all together at most %s MB"
                    % (format(info.PeakProcessMemoryUsed // mb, ","),
                       format(info.PeakJobMemoryUsed // mb, ",")))
        import resource
        kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return "memory  : the largest finished process used %s MB" % format(kb // 1024, ",")
    except Exception:
        return ""


# ---- One heavy job at a time ----

def lock_dir():
    """Where the turn is: the gate's own folder (LOCK_DIR_ENV), else where
    the run that started this one took it -- run_tests gives each suite a
    temporary folder of its own, and a suite settles too -- else here."""
    held_in = os.environ.get(HOLDER_ENV, "").partition(" ")[2]
    return (os.environ.get(LOCK_DIR_ENV)
            or (held_in if held_in and os.path.isdir(held_in) else tempfile.gettempdir()))


def take_turn(label=None, wait_s=None):
    """Wait for this machine's one heavy-job lock and hold it until this
    process ends; returns the line to print. A child of the holder shares
    its turn and does not wait."""
    global _lock_file, _token
    if _lock_file is not None:
        return "machine : this run's turn"
    folder = lock_dir()
    inherited = _inherited_turn(folder)
    if wait_s is None:
        try:
            wait_s = int(os.environ.get(WAIT_ENV, WAIT_S))
        except ValueError:
            wait_s = WAIT_S
    try:
        handle = open(os.path.join(folder, LOCK_NAME), "a+b")
    except OSError as exc:   # said, never silent, and never a refused run
        return "machine : NO turn taken, the lock could not be opened (%s)" % exc
    started = time.time()
    said, last_word = None, started
    while True:
        if _try_lock(handle):
            break
        holder = read_holder(folder)
        if holder and (holder.get("token") == inherited
                       or holder.get("pid") in _ancestors()):
            handle.close()
            return ("machine : the turn of the run that started this one (%s)"
                    % describe(holder))
        who = describe(holder)
        waited = time.time() - started
        if waited >= wait_s:
            handle.close()
            print("machine : BUSY -- after %d s it is still the turn of %s; try again "
                  "later (one heavy job at a time on this computer)" % (waited, who), flush=True)
            raise SystemExit(BUSY)
        if who != said or time.time() - last_word >= 60:
            print("machine : waiting for %s -- one heavy job at a time on this "
                  "computer (%d s so far, %d at most)" % (who, waited, wait_s), flush=True)
            said, last_word = who, time.time()
        time.sleep(2)
    _lock_file = handle
    _token = "%d-%d" % (os.getpid(), int(time.time() * 1000))
    me = {"pid": os.getpid(), "token": _token, "born": born_at(os.getpid()),
          "label": (label or _label()).strip(), "since": time.strftime("%H:%M:%S"),
          "folder": os.getcwd()}
    try:
        with open(os.path.join(folder, HOLDER_NAME), "w", encoding="utf-8") as fh:
            json.dump(me, fh)
    except OSError:
        pass
    os.environ[HOLDER_ENV] = "%s %s" % (_token, folder)
    import atexit
    atexit.register(_give_up_turn, folder)
    return "machine : this run's turn (one heavy job at a time; a run started now waits for it)"


def read_holder(folder=None):
    try:
        with open(os.path.join(folder or lock_dir(), HOLDER_NAME), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def describe(holder):
    if not holder:
        return "another run"
    return "%s (pid %s, since %s)" % (holder.get("label", "a run"), holder.get("pid"),
                                      holder.get("since", "?"))


def _label():
    return " ".join([os.path.basename(sys.argv[0])] + sys.argv[1:])[:120] or "python"


def _inherited_turn(folder):
    """The token of the turn this process was started inside, if any."""
    value = os.environ.get(HOLDER_ENV, "")
    token, _, where = value.partition(" ")
    if token and os.path.normcase(os.path.abspath(where)) == os.path.normcase(
            os.path.abspath(folder)):
        return token
    return None


def _try_lock(handle):
    try:
        if sys.platform == "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _give_up_turn(folder):
    """At an ordinary exit: the holder's name first, then the lock. A run
    that is killed leaves the name behind, and the OS frees the lock."""
    global _lock_file
    holder = read_holder(folder)
    if holder and holder.get("token") == _token:
        try:
            os.remove(os.path.join(folder, HOLDER_NAME))
        except OSError:
            pass
    if _lock_file is not None:
        try:
            _lock_file.close()
        except OSError:
            pass
        _lock_file = None


# ---- Processes: alive, born when, whose child ----

_KERNEL = []


def _kernel32():
    """(ctypes, wintypes, kernel32) with the calls below declared, once."""
    if not _KERNEL:
        import ctypes
        import ctypes.wintypes as wt
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wt.HANDLE
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.CloseHandle.argtypes = [wt.HANDLE]
        k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
        k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
        k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
        _KERNEL.extend([ctypes, wt, k32])
    return _KERNEL


def alive(pid, born=None):
    """Is the process that wrote a marker still running? Unsure means yes:
    a folder is removed only when its owner is certainly gone."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        ctypes, wt, k32 = _kernel32()
        handle = k32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() != 87       # INVALID_PARAMETER: no such pid
        try:
            code = wt.DWORD()
            if k32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259:
                return False                           # 259: STILL_ACTIVE
            started = _born_from_handle(handle)
        finally:
            k32.CloseHandle(handle)
        # The pid is in use: by the same process, or by a later one.
        return born is None or started is None or abs(started - born) < 2
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    started = born_at(pid)
    return born is None or started is None or abs(started - born) < 2


def born_at(pid):
    """When the process started, in seconds since the epoch; None if unknown."""
    try:
        if sys.platform == "win32":
            ctypes, wt, k32 = _kernel32()
            handle = k32.OpenProcess(0x1000, False, pid)
            if not handle:
                return None
            try:
                return _born_from_handle(handle)
            finally:
                k32.CloseHandle(handle)
        with open("/proc/%d/stat" % pid) as fh:
            ticks = int(fh.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/stat") as fh:
            boot = next(int(l.split()[1]) for l in fh if l.startswith("btime"))
        return boot + ticks / float(os.sysconf("SC_CLK_TCK"))
    except Exception:
        return None


def _born_from_handle(handle):
    ctypes, wt, k32 = _kernel32()
    times = [wt.FILETIME() for _ in range(4)]
    if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        return None
    ft = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    return ft / 1e7 - 11644473600.0


def _ancestors():
    """The pids of this process's parent, its parent, and so on."""
    parents = {}
    try:
        if sys.platform == "win32":
            parents = _windows_parents()
        else:
            for name in os.listdir("/proc"):
                if name.isdigit():
                    try:
                        with open("/proc/%s/stat" % name) as fh:
                            parents[int(name)] = int(fh.read().rsplit(")", 1)[1].split()[1])
                    except (OSError, ValueError, IndexError):
                        pass
    except Exception:
        return set()
    seen, pid = set(), os.getpid()
    while pid in parents and len(seen) < 64:
        pid = parents[pid]
        if pid in seen or pid <= 0:
            break
        seen.add(pid)
    return seen


def _windows_parents():
    ctypes, wt, k32 = _kernel32()

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                    ("th32ProcessID", wt.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(Entry)]
    k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(Entry)]
    snap = k32.CreateToolhelp32Snapshot(2, 0)          # TH32CS_SNAPPROCESS
    if not snap or snap == wt.HANDLE(-1).value:
        return {}
    parents = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return parents


# ---- Scratch folders: made with a marker, removed on every way out ----

def scratch(prefix):
    """A fresh folder in the temporary folder, marked as this process's, so
    that a later run can remove it if this one dies before it does."""
    if not prefix.startswith(PREFIXES):
        raise ValueError("a scratch folder's name starts with one of %s" % (PREFIXES,))
    path = tempfile.mkdtemp(prefix=prefix)
    _write_marker(path, {"pid": os.getpid(), "born": born_at(os.getpid()),
                         "made_by": _label(), "made": time.time()})
    return path


def keep(path, why):
    """Mark a scratch folder as kept on purpose (photographs to look at): a
    later run removes it only after KEPT_DAYS."""
    marker = read_marker(path) or {}
    marker.update({"kept": why, "kept_at": time.time()})
    _write_marker(path, marker)


def remove(path):
    """Remove a scratch folder this module made; anything else is left."""
    marker = read_marker(path) if path else None
    if marker is not None and _in_temp(path):
        _remove_marked(path, marker)


def _remove_marked(path, marker):
    """Remove a marked folder, read-only files too (git keeps its objects
    so). A file something still holds keeps the folder, and the marker is
    put back beside it, so a later sweep finishes the job: unmarked, it
    would stay for good."""
    def again(func, failed, _exc):
        try:
            os.chmod(failed, stat.S_IWRITE | stat.S_IREAD)
            func(failed)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=again)
    else:
        shutil.rmtree(path, onerror=again)
    if os.path.isdir(path) and read_marker(path) is None:
        try:
            _write_marker(path, marker)
        except OSError:
            pass


def read_marker(path):
    try:
        with open(os.path.join(path, MARKER), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def sweep(folder=None):
    """Remove the scratch folders whose run is gone; returns the line to
    print, or '' when there were none."""
    folder = folder or tempfile.gettempdir()
    gone, size = 0, 0
    try:
        entries = [e for e in os.scandir(folder) if e.name.startswith(PREFIXES)]
    except OSError:
        return ""
    now = time.time()
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        marker = read_marker(entry.path)
        if not isinstance(marker, dict):
            continue
        if marker.get("kept"):
            if now - float(marker.get("kept_at") or now) < KEPT_DAYS * 86400:
                continue
        elif alive(marker.get("pid"), marker.get("born")):
            continue
        size += _size_of(entry.path)
        _remove_marked(entry.path, marker)
        if not os.path.exists(entry.path):
            gone += 1
    if not gone:
        return ""
    return ("leftover: removed %d scratch folder(s) left by runs that died, or kept past "
            "%d days (%s MB)" % (gone, KEPT_DAYS, format(size // (1024 * 1024), ",")))


def _write_marker(path, data):
    with open(os.path.join(path, MARKER), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def _in_temp(path):
    temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
    return os.path.normcase(os.path.abspath(path)).startswith(temp + os.sep)


def _size_of(path):
    total = 0
    for top, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(top, name))
            except OSError:
                pass
    return total


def _cap_posix(limit_mb):
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    limit = limit_mb * 1024 * 1024
    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)
    resource.setrlimit(resource.RLIMIT_AS, (limit, hard))


# ---- Windows: a job object (kernel32), through ctypes ----

_PROCESS_MEMORY = 0x100       # JOB_OBJECT_LIMIT_PROCESS_MEMORY
_JOB_MEMORY = 0x200           # JOB_OBJECT_LIMIT_JOB_MEMORY
_KILL_ON_JOB_CLOSE = 0x2000   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
_EXTENDED_LIMITS = 9          # JobObjectExtendedLimitInformation


def _structures():
    import ctypes
    import ctypes.wintypes as wt

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wt.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wt.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wt.DWORD),
                    ("SchedulingClass", wt.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic),
                    ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wt.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    k32.QueryInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                              wt.DWORD, ctypes.c_void_p]
    k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
    k32.GetCurrentProcess.restype = wt.HANDLE
    return ctypes, k32, Extended


def _cap_windows(per_process_mb, all_together_mb):
    global _job
    ctypes, k32, Extended = _structures()
    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
    info = Extended()
    info.BasicLimitInformation.LimitFlags = _PROCESS_MEMORY | _JOB_MEMORY | _KILL_ON_JOB_CLOSE
    info.ProcessMemoryLimit = per_process_mb * 1024 * 1024
    info.JobMemoryLimit = all_together_mb * 1024 * 1024
    if not k32.SetInformationJobObject(job, _EXTENDED_LIMITS, ctypes.byref(info),
                                       ctypes.sizeof(info)):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    _job = job


def _query(job):
    ctypes, k32, Extended = _structures()
    info = Extended()
    k32.QueryInformationJobObject(job, _EXTENDED_LIMITS, ctypes.byref(info),
                                  ctypes.sizeof(info), None)
    return info
