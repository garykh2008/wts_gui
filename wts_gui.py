import sys
from wts_server import run_server

if __name__ == "__main__":
    default_port = 8000
    if len(sys.argv) > 1:
        try: default_port = int(sys.argv[1])
        except: pass
    run_server(default_port)
