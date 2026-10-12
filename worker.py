"""Dedicated telemetry writer for independent production hosting."""
import time
from app import app
from thermovolt.fleet import start_fleet_stream
if __name__=='__main__':
    start_fleet_stream(app)
    try:
        while True:time.sleep(30)
    finally:app.extensions['fleet_stream'].set()
