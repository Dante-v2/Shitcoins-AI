try:
    import sys, os
    from threading import Lock
    from colorama import Fore, init
    from datetime import datetime
except Exception as e:
    print(e)
    raise SystemExit()

init(autoreset=True)

lock = Lock()

# Helper function to write to file with UTF-8 encoding
def _write_to_file(message, mode="a"):
    log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "logs.log")
    with open(log_path, mode, encoding="utf-8") as f:
        f.write(message)

def info(s, end='\n'):
    now = str(datetime.now())[:-3]
    string = f'[{now}] {Fore.GREEN}{s}{end}'
    with lock:
        sys.stdout.write(string)
        sys.stdout.flush()
        _write_to_file(f"[{now}] {s}{end}")

def warn(s, end='\n'):
    now = str(datetime.now())[:-3]
    string = f'[{now}] {Fore.YELLOW}{s}{end}'
    with lock:
        sys.stdout.write(string)
        sys.stdout.flush()
        _write_to_file(f"[{now}] {s}{end}")

def status(s, end='\n'):
    now = str(datetime.now())[:-3]
    string = f'[{now}] {Fore.CYAN}{s}{end}'
    with lock:
        sys.stdout.write(string)
        sys.stdout.flush()
        _write_to_file(f"[{now}] {s}{end}")

def error(s, end='\n'):
    now = str(datetime.now())[:-3]
    string = f'[{now}] {Fore.RED}{s}{end}'
    with lock:
        sys.stdout.write(string)
        sys.stdout.flush()
        _write_to_file(f"[{now}] {s}{end}")

def debug(s, end='\n'):
    now = str(datetime.now())[:-3]
    _write_to_file(f"[{now}] {s}{end}")

def critical(s, end='\n'):
    now = str(datetime.now())[:-3]
    string = f'[{now}] {Fore.MAGENTA}{s}{end}'
    with lock:
        sys.stdout.write(string)
        sys.stdout.flush()
        _write_to_file(f"[{now}] {s}{end}")