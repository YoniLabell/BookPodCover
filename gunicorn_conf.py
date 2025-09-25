bind = "0.0.0.0:10000"  # Render typically exposes PORT via env; the platform maps it correctly
workers = 2
threads = 2
timeout = 120
graceful_timeout = 30
keepalive = 5
