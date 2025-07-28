# Gunicorn configuration for SaneApe.com
# Handles long-running AI analysis requests

bind = "0.0.0.0:5000"
workers = 1
worker_class = "sync"
timeout = 180  # 3 minutes to handle long OpenAI requests
keepalive = 5
preload_app = True
reload = True
max_requests = 1000
max_requests_jitter = 100