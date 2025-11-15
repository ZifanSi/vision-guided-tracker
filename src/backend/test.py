import time
from utils import *
from cv import CVPipeline
import logging
logging.basicConfig(level=logging.DEBUG)

def noop_callback(result):
    # optional: user can process result here
    pass

def main():
    set_display_env()
    pipeline = CVPipeline("/dev/video0", 1280, 720, 60, "./pega_11n_map95.engine", noop_callback)
    pipeline.start()
    try:
        while pipeline.running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pipeline.stop()
    finally:
        pipeline.stop()

if __name__ == "__main__":
    main()
