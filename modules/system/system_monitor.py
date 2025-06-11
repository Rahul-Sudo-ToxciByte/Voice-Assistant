#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Monitor for Jarvis Assistant

This module handles the system monitoring and control capabilities of the Jarvis assistant,
including CPU, memory, disk, network, and process monitoring.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import platform

# Import for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Import for Windows-specific functionality
if platform.system() == "Windows":
    try:
        import winreg
        import ctypes
        from ctypes import windll
        WINDOWS_UTILS_AVAILABLE = True
    except ImportError:
        WINDOWS_UTILS_AVAILABLE = False
else:
    WINDOWS_UTILS_AVAILABLE = False


class SystemMonitor:
    """System monitor for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the system monitor
        
        Args:
            config: Configuration dictionary for system monitor settings
        """
        self.logger = logging.getLogger("jarvis.system")
        self.config = config
        
        # Set up system monitor configuration
        self.enabled = config.get("enable_system_monitor", True)
        self.monitor_interval = config.get("monitor_interval", 5)  # seconds
        self.history_size = config.get("history_size", 60)  # number of data points to keep
        self.enable_process_monitor = config.get("enable_process_monitor", True)
        self.enable_network_monitor = config.get("enable_network_monitor", True)
        self.enable_disk_monitor = config.get("enable_disk_monitor", True)
        
        # System information
        self.system_info = self._get_system_info()
        
        # Monitoring data
        self.cpu_percent = 0
        self.memory_percent = 0
        self.cpu_history = []
        self.memory_history = []
        self.disk_usage = {}
        self.network_io = {}
        self.battery_info = {}
        self.top_processes = []
        
        # Monitoring thread
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # Start monitoring if enabled
        if self.enabled:
            self._start_monitoring()
        
        self.logger.info(f"System monitor initialized (enabled: {self.enabled})")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information
        
        Returns:
            Dictionary with system information
        """
        info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
        }
        
        if PSUTIL_AVAILABLE:
            # Add CPU information
            cpu_info = {
                "physical_cores": psutil.cpu_count(logical=False),
                "total_cores": psutil.cpu_count(logical=True),
                "max_frequency": None,
            }
            
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    cpu_info["max_frequency"] = cpu_freq.max
                    cpu_info["min_frequency"] = cpu_freq.min
                    cpu_info["current_frequency"] = cpu_freq.current
            except Exception:
                pass
            
            info["cpu"] = cpu_info
            
            # Add memory information
            memory = psutil.virtual_memory()
            info["memory"] = {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            }
            
            # Add disk information
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "filesystem": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    })
                except Exception:
                    # Some partitions may not be accessible
                    pass
            
            info["disks"] = disks
            
            # Add network information
            networks = []
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == 2:  # AF_INET (IPv4)
                        networks.append({
                            "interface": name,
                            "address": addr.address,
                            "netmask": addr.netmask,
                        })
            
            info["networks"] = networks
            
            # Add battery information if available
            if hasattr(psutil, "sensors_battery"):
                battery = psutil.sensors_battery()
                if battery:
                    info["battery"] = {
                        "percent": battery.percent,
                        "power_plugged": battery.power_plugged,
                        "secsleft": battery.secsleft,
                    }
        
        # Add Windows-specific information
        if info["platform"] == "Windows" and WINDOWS_UTILS_AVAILABLE:
            try:
                info["windows"] = self._get_windows_info()
            except Exception as e:
                self.logger.error(f"Error getting Windows information: {e}")
        
        return info
    
    def _get_windows_info(self) -> Dict[str, Any]:
        """Get Windows-specific information
        
        Returns:
            Dictionary with Windows information
        """
        windows_info = {}
        
        # Get Windows version information
        try:
            windows_info["version"] = platform.win32_ver()
        except Exception:
            pass
        
        # Get Windows product name from registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                windows_info["product_name"] = winreg.QueryValueEx(key, "ProductName")[0]
                windows_info["build_number"] = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
        except Exception:
            pass
        
        # Get system metrics
        try:
            windows_info["metrics"] = {
                "screen_width": windll.user32.GetSystemMetrics(0),  # SM_CXSCREEN
                "screen_height": windll.user32.GetSystemMetrics(1),  # SM_CYSCREEN
                "multiple_monitors": windll.user32.GetSystemMetrics(80) > 0,  # SM_CMONITORS
            }
        except Exception:
            pass
        
        return windows_info
    
    def _start_monitoring(self):
        """Start the monitoring thread"""
        if not PSUTIL_AVAILABLE:
            self.logger.error("psutil not available. System monitoring will be disabled.")
            self.enabled = False
            return
        
        # Reset stop event
        self.stop_event.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info(f"System monitoring started with interval: {self.monitor_interval}s")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while not self.stop_event.is_set():
            try:
                # Update CPU and memory usage
                self.cpu_percent = psutil.cpu_percent(interval=0.1)
                self.memory_percent = psutil.virtual_memory().percent
                
                # Update history
                timestamp = datetime.now().isoformat()
                self.cpu_history.append((timestamp, self.cpu_percent))
                self.memory_history.append((timestamp, self.memory_percent))
                
                # Trim history to configured size
                if len(self.cpu_history) > self.history_size:
                    self.cpu_history = self.cpu_history[-self.history_size:]
                if len(self.memory_history) > self.history_size:
                    self.memory_history = self.memory_history[-self.history_size:]
                
                # Update disk usage if enabled
                if self.enable_disk_monitor:
                    self._update_disk_usage()
                
                # Update network I/O if enabled
                if self.enable_network_monitor:
                    self._update_network_io()
                
                # Update battery information if available
                self._update_battery_info()
                
                # Update top processes if enabled
                if self.enable_process_monitor:
                    self._update_top_processes()
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
            
            # Wait for next update
            self.stop_event.wait(self.monitor_interval)
    
    def _update_disk_usage(self):
        """Update disk usage information"""
        try:
            self.disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    self.disk_usage[partition.mountpoint] = {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    }
                except Exception:
                    # Some partitions may not be accessible
                    pass
        except Exception as e:
            self.logger.error(f"Error updating disk usage: {e}")
    
    def _update_network_io(self):
        """Update network I/O information"""
        try:
            self.network_io = psutil.net_io_counters(pernic=True)
        except Exception as e:
            self.logger.error(f"Error updating network I/O: {e}")
    
    def _update_battery_info(self):
        """Update battery information"""
        try:
            if hasattr(psutil, "sensors_battery"):
                battery = psutil.sensors_battery()
                if battery:
                    self.battery_info = {
                        "percent": battery.percent,
                        "power_plugged": battery.power_plugged,
                        "secsleft": battery.secsleft,
                    }
        except Exception as e:
            self.logger.error(f"Error updating battery information: {e}")
    
    def _update_top_processes(self, limit: int = 10):
        """Update top processes by CPU and memory usage
        
        Args:
            limit: Maximum number of processes to include
        """
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'create_time']):
                try:
                    # Get process information
                    proc_info = proc.info
                    proc_info['cpu_percent'] = proc.cpu_percent(interval=0.1)
                    
                    # Add to processes list
                    processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Sort by CPU usage and get top processes
            top_cpu = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:limit]
            
            # Sort by memory usage and get top processes
            top_memory = sorted(processes, key=lambda p: p['memory_percent'], reverse=True)[:limit]
            
            # Combine and deduplicate
            top_combined = {}
            for proc in top_cpu + top_memory:
                if proc['pid'] not in top_combined:
                    top_combined[proc['pid']] = proc
            
            # Convert to list and sort by CPU usage
            self.top_processes = sorted(top_combined.values(), key=lambda p: p['cpu_percent'], reverse=True)[:limit]
        
        except Exception as e:
            self.logger.error(f"Error updating top processes: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information
        
        Returns:
            Dictionary with system information
        """
        return self.system_info
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status
        
        Returns:
            Dictionary with current system status
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": self.cpu_percent,
                "history": self.cpu_history,
            },
            "memory": {
                "percent": self.memory_percent,
                "history": self.memory_history,
            },
        }
        
        if self.enable_disk_monitor:
            status["disk"] = self.disk_usage
        
        if self.enable_network_monitor:
            status["network"] = {}
            for interface, counters in self.network_io.items():
                status["network"][interface] = {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errin": counters.errin,
                    "errout": counters.errout,
                    "dropin": counters.dropin,
                    "dropout": counters.dropout,
                }
        
        if self.battery_info:
            status["battery"] = self.battery_info
        
        if self.enable_process_monitor:
            status["processes"] = self.top_processes
        
        return status
    
    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific process
        
        Args:
            pid: Process ID
            
        Returns:
            Dictionary with process information, or None if not found
        """
        if not PSUTIL_AVAILABLE:
            return None
        
        try:
            proc = psutil.Process(pid)
            info = proc.as_dict(attrs=[
                'pid', 'name', 'exe', 'cmdline', 'ppid', 'username',
                'status', 'create_time', 'cpu_percent', 'memory_percent',
                'memory_info', 'io_counters', 'num_threads', 'nice',
                'cwd', 'cpu_times', 'open_files', 'connections'
            ])
            
            # Format create time
            if 'create_time' in info:
                info['create_time'] = datetime.fromtimestamp(info['create_time']).isoformat()
            
            # Update CPU percent
            info['cpu_percent'] = proc.cpu_percent(interval=0.1)
            
            return info
        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        except Exception as e:
            self.logger.error(f"Error getting process info: {e}")
            return None
    
    def find_processes(self, name: str) -> List[Dict[str, Any]]:
        """Find processes by name
        
        Args:
            name: Process name to search for
            
        Returns:
            List of matching processes
        """
        if not PSUTIL_AVAILABLE:
            return []
        
        try:
            matching_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username', 'cpu_percent', 'memory_percent', 'create_time']):
                try:
                    # Check if process name matches
                    if name.lower() in proc.info['name'].lower():
                        # Get process information
                        proc_info = proc.info
                        proc_info['cpu_percent'] = proc.cpu_percent(interval=0.1)
                        
                        # Format create time
                        if 'create_time' in proc_info:
                            proc_info['create_time'] = datetime.fromtimestamp(proc_info['create_time']).isoformat()
                        
                        matching_processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            return matching_processes
        
        except Exception as e:
            self.logger.error(f"Error finding processes: {e}")
            return []
    
    def kill_process(self, pid: int) -> bool:
        """Kill a process by PID
        
        Args:
            pid: Process ID to kill
            
        Returns:
            True if successful, False otherwise
        """
        if not PSUTIL_AVAILABLE:
            return False
        
        try:
            proc = psutil.Process(pid)
            proc.kill()
            return True
        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        except Exception as e:
            self.logger.error(f"Error killing process: {e}")
            return False
    
    def get_disk_usage(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Get disk usage for a specific path or all disks
        
        Args:
            path: Path to check, or None for all disks
            
        Returns:
            Dictionary with disk usage information
        """
        if not PSUTIL_AVAILABLE:
            return {}
        
        try:
            if path:
                # Get usage for specific path
                usage = psutil.disk_usage(path)
                return {
                    path: {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    }
                }
            else:
                # Return all disk usage
                return self.disk_usage
        
        except Exception as e:
            self.logger.error(f"Error getting disk usage: {e}")
            return {}
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics
        
        Returns:
            Dictionary with network statistics
        """
        if not PSUTIL_AVAILABLE or not self.enable_network_monitor:
            return {}
        
        try:
            stats = {}
            for interface, counters in self.network_io.items():
                stats[interface] = {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errin": counters.errin,
                    "errout": counters.errout,
                    "dropin": counters.dropin,
                    "dropout": counters.dropout,
                }
            return stats
        
        except Exception as e:
            self.logger.error(f"Error getting network stats: {e}")
            return {}
    
    def get_battery_status(self) -> Dict[str, Any]:
        """Get battery status
        
        Returns:
            Dictionary with battery status, or empty dict if not available
        """
        return self.battery_info
    
    def get_system_uptime(self) -> float:
        """Get system uptime in seconds
        
        Returns:
            System uptime in seconds
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            return time.time() - psutil.boot_time()
        except Exception as e:
            self.logger.error(f"Error getting system uptime: {e}")
            return 0.0
    
    def get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature if available
        
        Returns:
            CPU temperature in Celsius, or None if not available
        """
        if not PSUTIL_AVAILABLE or not hasattr(psutil, "sensors_temperatures"):
            return None
        
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            
            # Try to find CPU temperature
            for name, entries in temps.items():
                if name.lower() in ("coretemp", "cpu_thermal", "cpu"):
                    # Return the highest temperature
                    return max(temp.current for temp in entries)
            
            # If no specific CPU temperature found, return the first one
            for entries in temps.values():
                if entries:
                    return entries[0].current
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error getting CPU temperature: {e}")
            return None
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information
        
        Returns:
            Dictionary with memory information
        """
        if not PSUTIL_AVAILABLE:
            return {}
        
        try:
            virtual = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                "virtual": {
                    "total": virtual.total,
                    "available": virtual.available,
                    "used": virtual.used,
                    "free": virtual.free,
                    "percent": virtual.percent,
                },
                "swap": {
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free,
                    "percent": swap.percent,
                    "sin": swap.sin,
                    "sout": swap.sout,
                }
            }
        
        except Exception as e:
            self.logger.error(f"Error getting memory info: {e}")
            return {}
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get detailed CPU information
        
        Returns:
            Dictionary with CPU information
        """
        if not PSUTIL_AVAILABLE:
            return {}
        
        try:
            info = {
                "physical_cores": psutil.cpu_count(logical=False),
                "total_cores": psutil.cpu_count(logical=True),
                "current_frequency": None,
                "min_frequency": None,
                "max_frequency": None,
                "percent": self.cpu_percent,
                "per_core": [],
            }
            
            # Get CPU frequency if available
            try:
                freq = psutil.cpu_freq()
                if freq:
                    info["current_frequency"] = freq.current
                    info["min_frequency"] = freq.min
                    info["max_frequency"] = freq.max
            except Exception:
                pass
            
            # Get per-core usage
            try:
                per_core = psutil.cpu_percent(interval=0.1, percpu=True)
                info["per_core"] = per_core
            except Exception:
                pass
            
            # Get CPU temperature if available
            temp = self.get_cpu_temperature()
            if temp is not None:
                info["temperature"] = temp
            
            return info
        
        except Exception as e:
            self.logger.error(f"Error getting CPU info: {e}")
            return {}
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of logged-in users
        
        Returns:
            List of logged-in users
        """
        if not PSUTIL_AVAILABLE:
            return []
        
        try:
            users = []
            for user in psutil.users():
                users.append({
                    "name": user.name,
                    "terminal": user.terminal,
                    "host": user.host,
                    "started": datetime.fromtimestamp(user.started).isoformat(),
                    "pid": user.pid if hasattr(user, "pid") else None,
                })
            return users
        
        except Exception as e:
            self.logger.error(f"Error getting users: {e}")
            return []
    
    def get_boot_time(self) -> str:
        """Get system boot time
        
        Returns:
            Boot time as ISO format string
        """
        if not PSUTIL_AVAILABLE:
            return ""
        
        try:
            boot_time = psutil.boot_time()
            return datetime.fromtimestamp(boot_time).isoformat()
        except Exception as e:
            self.logger.error(f"Error getting boot time: {e}")
            return ""
    
    def get_system_summary(self) -> str:
        """Get a human-readable summary of the system status
        
        Returns:
            String with system summary
        """
        if not PSUTIL_AVAILABLE:
            return "System monitoring not available"
        
        try:
            summary = []
            
            # Add CPU information
            cpu_info = self.get_cpu_info()
            summary.append(f"CPU: {self.cpu_percent}% used")
            if "temperature" in cpu_info:
                summary.append(f"CPU Temperature: {cpu_info['temperature']:.1f}°C")
            
            # Add memory information
            summary.append(f"Memory: {self.memory_percent}% used")
            
            # Add disk information
            if self.disk_usage:
                for path, usage in self.disk_usage.items():
                    # Convert to GB for display
                    total_gb = usage["total"] / (1024 ** 3)
                    free_gb = usage["free"] / (1024 ** 3)
                    summary.append(f"Disk {path}: {usage['percent']}% used ({free_gb:.1f} GB free of {total_gb:.1f} GB)")
            
            # Add battery information if available
            if self.battery_info:
                battery = self.battery_info
                status = "Charging" if battery["power_plugged"] else "Discharging"
                time_left = ""
                if battery["secsleft"] > 0:
                    hours = battery["secsleft"] // 3600
                    minutes = (battery["secsleft"] % 3600) // 60
                    time_left = f", {hours}h {minutes}m remaining"
                summary.append(f"Battery: {battery['percent']}% ({status}{time_left})")
            
            # Add uptime
            uptime_seconds = self.get_system_uptime()
            days = int(uptime_seconds // (24 * 3600))
            hours = int((uptime_seconds % (24 * 3600)) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            if days > 0:
                uptime_str = f"{days}d {hours}h {minutes}m"
            else:
                uptime_str = f"{hours}h {minutes}m"
            summary.append(f"Uptime: {uptime_str}")
            
            return "\n".join(summary)
        
        except Exception as e:
            self.logger.error(f"Error getting system summary: {e}")
            return "Error generating system summary"
    
    def shutdown(self):
        """Shutdown the system monitor"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.stop_event.set()
            self.monitor_thread.join(timeout=2.0)
        
        self.logger.info("System monitor shut down")