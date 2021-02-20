import multiprocessing


def number_of_workers():
    # According to rule-of-thumb in gunicorn documentation
    # https://docs.gunicorn.org/en/stable/design.html#how-many-workers
    return (multiprocessing.cpu_count() * 2) + 1


workers = number_of_workers()  # or an integer
preload_app = True
bind = "unix:/tmp/otokuna-web-server.sock"
umask = 0o007
accesslog = "/var/log/otokuna-web-server/gunicorn_access.log"
errorlog = "/var/log/otokuna-web-server/gunicorn_error.log"
