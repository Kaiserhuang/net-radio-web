import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DB path for Vercel (ephemeral /tmp)
os.environ["VERCEL"] = "1"
os.environ["DB_PATH"] = "/tmp/net_radio.db"
os.environ["HOST"] = "0.0.0.0"
os.environ["PORT"] = "8000"

from server import app as asgi_app
