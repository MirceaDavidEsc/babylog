import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/volume1/web/babylog_flask_app")

from app import app as application
