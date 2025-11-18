import sys

sys.path.append('../')
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from bus_call import bus_call
from utils import *

import time

MUXER_BATCH_TIMEOUT_USEC = 33000

_fps_last_time = time.perf_counter()

def osd_sink_pad_buffer_probe(pad, info, u_data):
    global _fps_last_time

    now = time.perf_counter()
    elapsed = now - _fps_last_time
    fps = 1 / elapsed
    print(f"FPS: {fps:.2f}, frame time: {elapsed * 1000:.2f} ms")
    _fps_last_time = now

    return Gst.PadProbeReturn.OK


def main():
    Gst.init(None)

    camera = "/dev/video0"

    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write("Unable to create Pipeline \n")

    source = Gst.ElementFactory.make("v4l2src", "usb-cam-source")
    if not source:
        sys.stderr.write("Unable to create Source \n")

    caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
    if not caps_v4l2src:
        sys.stderr.write("Unable to create v4l2src capsfilter \n")

    converter = Gst.ElementFactory.make("videoconvert", "convertor_src2")
    if not converter:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    sink = Gst.ElementFactory.make("glimagesink", "nv3d-sink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")

    source.set_property('device', camera)
    source.set_property('io-mode', 2)
    caps_v4l2src.set_property('caps', Gst.Caps.from_string("video/x-raw, framerate=60/1, width=1920, height=1080"))
    sink.set_property('sync', False)

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(caps_v4l2src)
    pipeline.add(converter)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    source.link(caps_v4l2src)
    caps_v4l2src.link(converter)
    converter.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    sinkpad = sink.get_static_pad("sink")
    if not sinkpad:
        sys.stderr.write(" Unable to get sink pad \n")

    sinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    import os

    os.nice(-10)
    set_display_env()
    sys.exit(main())
