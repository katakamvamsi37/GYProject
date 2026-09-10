"""Container defaults; tune workers after measuring memory and request latency."""

import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = 60
graceful_timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
# Do not log query strings, cookies, credentials, or authorization headers.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'
capture_output = True
worker_tmp_dir = "/tmp"
