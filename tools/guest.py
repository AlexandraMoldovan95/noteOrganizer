"""How a test run behaves as a guest on the computer it runs on.

On 2026-10-29 a mutant made a qa check size its fixture from a bound the
mutant had turned into a billion: one python.exe took 43 GB, Windows ran out
of memory, its desktop window manager crashed, and the shadow copies of C:
were deleted under the load (ISSUES_LOG: "The test that took the computer
down"). Every runner -- run_tests.py, mutate.py, the story scripts,
run_coverage.py, bench.py, pre_push_check.py -- calls ``settle()`` first,
and the memory ceiling it sets holds for every process the runner starts:
on Windows a job object holding each process's committed memory and all of
theirs together, which ends them with the runner; elsewhere RLIMIT_AS, per
process. A test past it gets MemoryError and fails like any check.

The scratch stays on the system's temporary folder: moved to an exFAT drive,
a test of NTFS's Zone.Identifier stream failed, and the notebooks the tests
stand in for live on NTFS.
"""

import sys

PER_PROCESS_MB = 4096
ALL_TOGETHER_MB = 8192

_job = None   # held for the run's life: its processes end when it closes


def settle(per_process_mb=PER_PROCESS_MB, all_together_mb=ALL_TOGETHER_MB):
    """Set the memory ceiling for this process and every process it starts.
    Returns the lines a runner prints: what was set, or that it was not and
    why -- a run is never refused for it, and never silent about it."""
    return [cap_memory(per_process_mb, all_together_mb)]


def cap_memory(per_process_mb=PER_PROCESS_MB, all_together_mb=ALL_TOGETHER_MB):
    try:
        if sys.platform == "win32":
            _cap_windows(per_process_mb, all_together_mb)
            return ("memory  : at most %s MB a process, %s MB in all"
                    % (format(per_process_mb, ","), format(all_together_mb, ",")))
        # Address space, not memory used: Python and Tk reserve far more
        # than they touch, so twice the Windows figure.
        _cap_posix(per_process_mb * 2)
        return "memory  : at most %s MB of address space a process" % format(
            per_process_mb * 2, ",")
    except Exception as exc:   # an OS without the call, or a job that refuses one
        return "memory  : NO ceiling set (%s)" % exc


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
