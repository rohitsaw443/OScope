import os
import signal
import platform
import socket
import datetime
import threading
import webbrowser
from flask import Flask, render_template, jsonify, request, session
import psutil

app = Flask(__name__)
app.secret_key = os.environ.get('OSCOPE_SECRET_KEY', 'oscope-academic-project-secret-key')

# Local academic-project authentication. Change these before real deployment.
DEMO_USERNAME = os.environ.get('OSCOPE_USERNAME', 'admin')
DEMO_PASSWORD = os.environ.get('OSCOPE_PASSWORD', 'oscope123')

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'success': False, 'message': 'Authentication required.'}), 401
        return fn(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/session')
def api_session():
    return jsonify({'authenticated': bool(session.get('authenticated')), 'username': session.get('username')})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    if username == DEMO_USERNAME and password == DEMO_PASSWORD:
        session['authenticated'] = True
        session['username'] = username
        return jsonify({'success': True, 'username': username})
    return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/system')
def api_system():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_percent_per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    
    try:
        cpu_freq_info = psutil.cpu_freq()
        cpu_freq = {
            'current': cpu_freq_info.current if cpu_freq_info else None,
            'min': cpu_freq_info.min if cpu_freq_info else None,
            'max': cpu_freq_info.max if cpu_freq_info else None
        }
    except Exception:
        cpu_freq = {'current': None, 'min': None, 'max': None}

    # Memory
    virtual_mem = psutil.virtual_memory()
    memory = {
        'total': round(virtual_mem.total / (1024**3), 2),
        'available': round(virtual_mem.available / (1024**3), 2),
        'used': round(virtual_mem.used / (1024**3), 2),
        'percent': virtual_mem.percent
    }

    # Swap
    swap_mem = psutil.swap_memory()
    swap = {
        'total': round(swap_mem.total / (1024**3), 2),
        'used': round(swap_mem.used / (1024**3), 2),
        'free': round(swap_mem.free / (1024**3), 2),
        'percent': swap_mem.percent
    }

    # Disk
    disk_partitions = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_partitions.append({
                'device': partition.device,
                'mountpoint': partition.mountpoint,
                'fstype': partition.fstype,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'free_gb': round(usage.free / (1024**3), 2),
                'percent': usage.percent
            })
        except PermissionError:
            continue
        except Exception:
            continue

    disk_io_counters = psutil.disk_io_counters()
    disk_io = {
        'read_bytes': round(disk_io_counters.read_bytes / (1024**3), 2) if disk_io_counters else 0,
        'write_bytes': round(disk_io_counters.write_bytes / (1024**3), 2) if disk_io_counters else 0,
        'read_count': disk_io_counters.read_count if disk_io_counters else 0,
        'write_count': disk_io_counters.write_count if disk_io_counters else 0
    }

    # Network
    net_io = psutil.net_io_counters()
    network_io = {
        'bytes_sent': round(net_io.bytes_sent / (1024**2), 2),
        'bytes_recv': round(net_io.bytes_recv / (1024**2), 2),
        'packets_sent': net_io.packets_sent,
        'packets_recv': net_io.packets_recv
    }

    net_if_addrs = psutil.net_if_addrs()
    network_interfaces = []
    for interface_name, interface_addresses in net_if_addrs.items():
        addrs = []
        for addr in interface_addresses:
            addrs.append({
                'family': str(addr.family),
                'address': addr.address
            })
        network_interfaces.append({
            'name': interface_name,
            'addresses': addrs
        })

    # Boot time & Uptime
    boot_time_timestamp = psutil.boot_time()
    boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp).strftime("%Y-%m-%d %H:%M:%S")
    uptime_seconds = (datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time_timestamp)).total_seconds()
    uptime_td = datetime.timedelta(seconds=uptime_seconds)
    days = uptime_td.days
    hours, remainder = divmod(uptime_td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{days}d {hours}h {minutes}m {seconds}s"

    # Platform Info
    platform_info = {
        'system': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }

    return jsonify({
        'cpu_percent': cpu_percent,
        'cpu_percent_per_core': cpu_percent_per_core,
        'cpu_count_logical': cpu_count_logical,
        'cpu_count_physical': cpu_count_physical,
        'cpu_freq': cpu_freq,
        'memory': memory,
        'swap': swap,
        'disk_partitions': disk_partitions,
        'disk_io': disk_io,
        'network_io': network_io,
        'network_interfaces': network_interfaces,
        'boot_time': boot_time,
        'uptime': uptime,
        'platform_info': platform_info
    })

@app.route('/api/processes')
def api_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'num_threads']):
        try:
            pinfo = proc.info
            # Formatting create_time
            if pinfo.get('create_time'):
                pinfo['create_time'] = datetime.datetime.fromtimestamp(pinfo['create_time']).strftime("%Y-%m-%d %H:%M:%S")
            
            if pinfo.get('memory_percent') is not None:
                pinfo['memory_percent'] = round(pinfo['memory_percent'], 2)
            
            if pinfo.get('memory_info'):
                pinfo['memory_mb'] = round(pinfo['memory_info'].rss / (1024 * 1024), 2)
            else:
                pinfo['memory_mb'] = 0.0

            pinfo.pop('memory_info', None)
            processes.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Sort by memory_percent descending
    processes.sort(key=lambda p: p.get('memory_percent', 0) or 0, reverse=True)
    return jsonify(processes)

@app.route('/api/process/<int:pid>/kill', methods=['POST'])
def kill_process(pid):
    try:
        proc = psutil.Process(pid)
        if pid in {os.getpid(), 0, 4}:
            return jsonify({'success': False, 'message': 'Protected system process cannot be terminated from OScope.'}), 403
        proc.kill()
        return jsonify({'success': True, 'message': f'Process {pid} killed successfully.'})
    except psutil.NoSuchProcess:
        return jsonify({'success': False, 'message': f'Process {pid} not found.'}), 404
    except psutil.AccessDenied:
        return jsonify({'success': False, 'message': f'Access denied to kill process {pid}.'}), 403
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def open_browser():
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("=========================================")
    print("OScope System Monitor started")
    print("Dashboard available at: http://localhost:5000")
    print("=========================================")
    threading.Timer(1.5, open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
