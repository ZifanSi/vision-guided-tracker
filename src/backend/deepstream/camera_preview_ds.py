import sys
import os
os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/tmp/"
sys.path.append('../')
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from bus_call import bus_call

import time

MUXER_BATCH_TIMEOUT_USEC = 33000


_inference_start_time = {}

def inference_start_probe(pad, info, u_data):
    global _inference_start_time

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    key = hash(gst_buffer)
    _inference_start_time[key] = time.perf_counter()

    return Gst.PadProbeReturn.OK

def inference_stop_probe(pad, info, u_data):
    global _inference_start_time

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    key = hash(gst_buffer)
    start_time = _inference_start_time[key]
    now = time.perf_counter()
    elapsed = now - start_time
    del _inference_start_time[key]
    print("Inference took {} ms, {} in queue".format(elapsed*1000, len(_inference_start_time)))
    return Gst.PadProbeReturn.OK

_fps_last_time = time.perf_counter()
_fps_time_list = [0]
_inspected = False

def osd_sink_pad_buffer_probe(pad, info, u_data):
    global _fps_last_time
    global _fps_time_list
    global _inspected
    global pipeline

    # if not _inspected:
    #     # inspect_caps(pipeline)
    #     Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, "pipeline")
    #     _inspected = True

    now = time.perf_counter()
    elapsed = now - _fps_last_time
    avg_fps = len(_fps_time_list)/(now - _fps_time_list[0])
    print(f"FPS: {avg_fps:.1f}, frame time: {elapsed * 1000:.1f} ms")
    _fps_last_time = now
    _fps_time_list.append(now)
    if len(_fps_time_list) > 60:
        _fps_time_list.pop(0)

    return Gst.PadProbeReturn.OK


def main():
    global pipeline
    Gst.init(None)

    camera = "/dev/video0"

    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write("Unable to create Pipeline \n")

    source = Gst.ElementFactory.make("nvv4l2camerasrc", "usb-cam-source")
    if not source:
        sys.stderr.write("Unable to create Source \n")

    caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
    if not caps_v4l2src:
        sys.stderr.write("Unable to create v4l2src capsfilter \n")

    converter1 = Gst.ElementFactory.make("nvvideoconvert", "convertor_src1")
    if not converter1:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    converter = Gst.ElementFactory.make("nvvideoconvert", "convertor_src2")
    if not converter:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    sink = Gst.ElementFactory.make("nvdrmvideosink", "nv3d-sink")
    if not sink:
        sys.stderr.write(" Unable to create sink \n")

    source.set_property('device', camera)
    source.set_property('cap-buffers', 2)
    # source.set_property('io-mode', 2)
    caps_v4l2src.set_property('caps', Gst.Caps.from_string("framerate=60/1,width=1920,height=1080"))
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('live-source', 1)
    streammux.set_property('batch-size', 1)
    pgie.set_property('config-file-path', "dstest1_pgie_config.txt")
    sink.set_property('sync', False)
    sink.set_property('set-mode', 1)

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(caps_v4l2src)
    pipeline.add(converter1)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(converter)
    pipeline.add(nvosd)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    source.link(caps_v4l2src)
    caps_v4l2src.link(converter1)
    converter1.get_static_pad("src").link(streammux.request_pad_simple("sink_0"))
    streammux.link(pgie)
    pgie.link(converter)
    converter.link(nvosd)
    nvosd.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    #
    # for pad in source.pads:
    #     caps = pad.get_current_caps()
    #     if not caps:
    #         caps = pad.get_allowed_caps()
    #     if caps:
    #         print(f"  Pad: {pad.get_name()}")
    #         for i in range(caps.get_size()):
    #             s = caps.get_structure(i)
    #             print(f"    {s.to_string()}")

    sinkpad = sink.get_static_pad("sink")
    if not sinkpad:
        sys.stderr.write(" Unable to get sink pad \n")

    sinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    infersinkpad = pgie.get_static_pad("sink")
    if not infersinkpad:
        sys.stderr.write(" Unable to get sink pad of pgie \n")
    infersinkpad.add_probe(Gst.PadProbeType.BUFFER, inference_start_probe, 0)
    infersrcpad = pgie.get_static_pad("src")
    if not infersrcpad:
        sys.stderr.write(" Unable to get src pad of pgie \n")
    infersrcpad.add_probe(Gst.PadProbeType.BUFFER, inference_stop_probe, 0)

    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)

def inspect_caps(pipeline):
    pipeline.set_state(Gst.State.PAUSED)
    pipeline.get_state(Gst.CLOCK_TIME_NONE)

    print("=== Pipeline negotiated caps ===")
    iter = pipeline.iterate_elements()
    elem = iter.next()
    while elem:
        elem = elem[1] if isinstance(elem, tuple) else elem
        if not elem:
            break
        print(f"\nElement: {elem.get_name()}")
        for pad in elem.pads:
            caps = pad.get_current_caps()
            if not caps:
                caps = pad.get_allowed_caps()
            if caps:
                print(f"  Pad: {pad.get_name()}")
                for i in range(caps.get_size()):
                    s = caps.get_structure(i)
                    print(f"    {s.to_string()}")

        elem = iter.next()

if __name__ == '__main__':
    # sudo is configured to not require password
    os.system("sudo nvpmodel -m 2") # MAXN_SUPER mode
    os.system("sudo jetson_clocks") # set all clocks to max
    os.system("sudo modprobe nvidia-drm modeset=1") # I can't get this to persist across reboots
    os.nice(-10)


    # set_display_env()
    sys.exit(main())
