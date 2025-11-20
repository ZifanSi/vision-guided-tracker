import sys
import os
os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/tmp/"
os.environ["GST_DEBUG"] = "2,caps:6,pad:6"
sys.path.append('../')
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from bus_call import bus_call
import time
import pyds

MUXER_BATCH_TIMEOUT_USEC = 33000

FRAGMENT_SHADER = """
#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {
    // Input: 1920x1080 (16:9)
    // Rotated: 1080x1920 (9:16)
    // Output: 1920x1080 (16:9)
    // Rotated image is letterboxed horizontally.

    float outputAspect  = 16.0 / 9.0;
    float rotatedAspect = 9.0 / 16.0;
    float contentWidth  = rotatedAspect / outputAspect; // normalized width of rotated content
    float border        = (1.0 - contentWidth) * 0.5;

    float s = v_texcoord.x;
    float t = v_texcoord.y;

    // Common vertical coord in rotated space
    float Y = clamp(t, 0.0, 1.0);

    // Inside content region: just rotate and sample normally
    if (s >= border && s <= 1.0 - border) {
        float X = (s - border) / contentWidth; // 0..1 across rotated image
        X = clamp(X, 0.0, 1.0);

        // Rotate 90° clockwise: (X, Y) -> (Y, 1 - X)
        vec2 src;
        src.x = Y;
        src.y = 1.0 - X;

        gl_FragColor = texture2D(tex, src);
        return;
    }

    // Border region: vertical blur using edge pixels of rotated image

    bool isLeft = (s < border);
    float X_edge = isLeft ? 0.0 : 1.0;

    // Vertical texel size in 1080p
    float texelSize = 1.0 / 1080.0;

    vec4 accum = vec4(0.0);
    float count = 0.0;

    for (int i = -50; i <= 50; i += 5) {
        float sampleY = clamp(Y + float(i) * texelSize, 0.0, 1.0);

        // Rotated coords: (X_edge, sampleY) -> (sampleY, 1 - X_edge)
        vec2 src;
        src.x = sampleY;
        src.y = 1.0 - X_edge;

        accum += texture2D(tex, src);
        count += 1.0;
    }

    gl_FragColor = accum / count;
}

"""

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

    # gst_buffer = info.get_buffer()
    # if not gst_buffer:
    #     print("Unable to get GstBuffer ")
    #     return
    #
    # key = hash(gst_buffer)
    # start_time = _inference_start_time[key]
    # now = time.perf_counter()
    # elapsed = now - start_time
    # del _inference_start_time[key]
    # print("Inference took {} ms, {} in queue".format(elapsed*1000, len(_inference_start_time)))

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.NvDsFrameMeta.cast()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        # Intiallizing object counter with 0.
        num_rects = frame_meta.num_obj_meta
        l_obj = frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            # obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.8)
            bbox = obj_meta.detector_bbox_info.org_bbox_coords
            bbox = {
                "conf": obj_meta.confidence,
                "left": bbox.left,
                "top": bbox.top,
                "width": bbox.width,
                "height": bbox.height
            }
            print(bbox)
            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        try:
            l_frame = l_frame.next
        except StopIteration:
            break



    return Gst.PadProbeReturn.OK

_fps_last_time = time.perf_counter()
_fps_time_list = [0]
_inspected = False

def osd_sink_pad_buffer_probe(pad, info, u_data):
    global _fps_last_time
    global _fps_time_list
    global _inspected
    global pipeline, osd

    # if not _inspected:
    #     # inspect_caps(pipeline)
    #     Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, "pipeline")
    #     _inspected = True

    now = time.perf_counter()
    elapsed = now - _fps_last_time
    avg_fps = len(_fps_time_list)/(now - _fps_time_list[0])
    # print(f"FPS: {avg_fps:.1f}, frame time: {elapsed * 1000:.1f} ms")
    _fps_last_time = now
    _fps_time_list.append(now)
    if len(_fps_time_list) > 60:
        _fps_time_list.pop(0)

    osd.set_property("text", f"FPS: {avg_fps:.1f}")

    return Gst.PadProbeReturn.OK


def main():
    global pipeline, osd
    Gst.init(None)

    camera = "/dev/video0"

    pipeline_desc = f"""
            nvv4l2camerasrc device={camera} cap-buffers=2 !
            video/x-raw(memory:NVMM),framerate=60/1,width=1920,height=1080 !
            tee name=t
            
            t. !
            nvvideoconvert !
            mux.sink_0 nvstreammux name=mux width=1920 height=1080 live-source=1 batch-size=1 !
            nvinfer name=infer config-file-path=dstest1_pgie_config.txt !
            nvvideoconvert !
            video/x-raw,format=RGBA !
            queue leaky=1 max-size-buffers=1 !
            glupload !
            glshader name=shader !
            gldownload !
            video/x-raw !
            textoverlay name=osd valignment=top halignment=left font-desc="Sans, 12" draw-outline=0 draw-shadow=0 color=0xFFFF0000 !
            nvvideoconvert !
            nvdrmvideosink name=drm-sink sync=false set-mode=1
            
            t. !
            queue !
            nvvideoconvert !
            nvjpegenc quality=70 !
            queue leaky=1 !
            avimux !
            filesink location=recording.avi
            
            t. !
            queue !
            nvvideoconvert dest-crop=0:0:480:270 !
            video/x-raw(memory:NVMM),width=480,height=270 !
            videorate !
            video/x-raw(memory:NVMM),framerate=30/1 !
            nvjpegenc quality=70 !
            multipartmux boundary=spionisto !
            tcpclientsink port=9999
            
        """

    # convert avi -> mp4: ffmpeg -i recording.avi -vf "transpose=1" -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 21 -an output.mp4
    pipeline = Gst.parse_launch(pipeline_desc)

    glshader = pipeline.get_by_name("shader")
    glshader.set_property('fragment', FRAGMENT_SHADER)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    infer = pipeline.get_by_name("infer")
    infer_source_pad = infer.get_static_pad("src")
    if not infer_source_pad:
        sys.stderr.write(" Unable to get src pad \n")
    infer_source_pad.add_probe(Gst.PadProbeType.BUFFER, inference_stop_probe, 0)

    osd = pipeline.get_by_name("osd")

    drm_sink = pipeline.get_by_name("drm-sink")
    drm_sink_pad = drm_sink.get_static_pad("sink")
    if not drm_sink_pad:
        sys.stderr.write(" Unable to get sink pad \n")

    drm_sink_pad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)


    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        print("Loop error! Exiting")
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
    # os.system("sudo setcap 'cap_net_bind_service=+eip' /usr/bin/python3.10") # give permission to bind to low-numbered ports
    # os.system("sudo setcap 'cap_sys_nice=+eip' /usr/bin/python3.10") # give permission to set high priority
    # os.system("sudo nvpmodel -m 2") # MAXN_SUPER mode
    # os.system("sudo jetson_clocks") # set all clocks to max
    # os.system("sudo modprobe nvidia-drm modeset=1") # I can't get this to persist across reboots
    os.nice(-10)


    # set_display_env()
    sys.exit(main())
