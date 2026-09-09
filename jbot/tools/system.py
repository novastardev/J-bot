import os
import platform

from jbot.tools.registry import tool


@tool
def system_info(info_type: str = "all"):
    """
    Get information about the current system.

    Args:
        info_type: One of "all", "os", "cpu", "memory", "disk", "python".
    """
    if info_type == "os":
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        }
    if info_type == "cpu":
        return {"cpu_count": os.cpu_count(), "machine": platform.machine()}
    if info_type == "memory":
        return _memory()
    if info_type == "disk":
        return _disk()
    if info_type == "python":
        return {"python_version": platform.python_version(), "hostname": platform.node()}

    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
    }
    mem = _memory()
    disk = _disk()
    if "error" not in mem:
        info["memory_total_gb"] = mem.get("total_gb")
        info["memory_percent_used"] = mem.get("percent_used")
    if "error" not in disk:
        info["disk_total_gb"] = disk.get("total_gb")
        info["disk_percent_used"] = disk.get("percent_used")
    return info


def _memory():
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent_used": vm.percent,
        }
    except ImportError:
        return {"error": "psutil is not installed."}


def _disk():
    try:
        import psutil

        du = psutil.disk_usage(os.getcwd())
        return {
            "total_gb": round(du.total / (1024**3), 2),
            "used_gb": round(du.used / (1024**3), 2),
            "free_gb": round(du.free / (1024**3), 2),
            "percent_used": du.percent,
        }
    except ImportError:
        return {"error": "psutil is not installed."}
