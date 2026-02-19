"""
CrewLedger — Gunicorn production configuration.

Usage:
    gunicorn -c deploy/gunicorn.conf.py 'src.app:create_app()'
"""

import multiprocessing

# Server socket
bind = "127.0.0.1:5000"
backlog = 256

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/crewledger/access.log"
errorlog = "/var/log/crewledger/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "crewledger"

# Server mechanics
daemon = False
pidfile = "/run/crewledger/crewledger.pid"
umask = 0o022
tmp_upload_dir = None

# Preload app for better memory usage
preload_app = True

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50
