import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["VERCEL"] = "1"
os.environ["DB_PATH"] = "/tmp/net_radio.db"

from server import app as asgi_app
