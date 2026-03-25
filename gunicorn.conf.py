"""
Gunicorn settings for Stage0 Launch.

Flask-Mongo style SIGTERM handlers in application code apply when you run the
Flask dev server directly. Under Gunicorn, the **master** receives Docker's
SIGTERM and coordinates worker shutdown; tuning ``graceful_timeout`` here is
what makes ``docker stop`` finish in a few seconds instead of waiting on the
default ~30s worker drain.
"""

bind = "0.0.0.0:8080"
workers = 1
threads = 8

# Default 30s: Docker often SIGKILLs the container at ~10s, leaving a messy stop.
graceful_timeout = 8

# Job log SSE sends chunks regularly; default worker timeout is sufficient.
timeout = 120

accesslog = "-"
errorlog = "-"
loglevel = "info"


def on_exit(server) -> None:
    """Log clean master exit (helps distinguish SIGTERM handling from a crash)."""
    server.log.info("stage0_launch: gunicorn master exiting")
