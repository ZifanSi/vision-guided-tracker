import gi

from ipc import create_rocam_ipc_client, BoundingBox

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
import time
import pyds
import sys
import os
import logging

logger = logging.getLogger("cv_process")

WIDTH = 1920
HEIGHT = 1080
CAMERA = "/dev/video0"
ipc_client = None
osd = None

def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End-of-stream\n")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()
    return True


_fps_last_time = time.perf_counter()
_fps_time_list = [0.0]

def inference_stop_probe(pad, info, u_data):
    global _fps_last_time
    global _fps_time_list
    global osd
    global ipc_client
    global glshader

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    pts_s = gst_buffer.pts  / 1e9  # presentation timestamp in seconds

    now = time.perf_counter()
    avg_fps = len(_fps_time_list) / (now - _fps_time_list[0])
    _fps_last_time = now
    _fps_time_list.append(now)
    if len(_fps_time_list) > 60:
        _fps_time_list.pop(0)

    osd.set_property("text", f"FPS: {avg_fps:.1f}")

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    bounding_box = None
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

        l_obj = frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break

            bbox = obj_meta.detector_bbox_info.org_bbox_coords
            if not bounding_box or obj_meta.confidence > bounding_box.conf:
                bounding_box = BoundingBox(
                    pts_s=pts_s,
                    conf=obj_meta.confidence,
                    left=bbox.left / WIDTH,
                    top=bbox.top / HEIGHT,
                    width=bbox.width / WIDTH,
                    height=bbox.height / HEIGHT
                )
            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    if bounding_box and bounding_box.conf > 0.4:
        ipc_client.send(bounding_box)
        cx = bounding_box.left + bounding_box.width / 2.0
        cy = bounding_box.top + bounding_box.height / 2.0

        tx = 0.5 - cx
        ty = 0.5 - cy
        glshader.set_property('uniforms',
                              Gst.Structure.new_from_string(f"uniforms, tx=(float){tx}, ty=(float){ty}, scale=(float)1.0"))

    return Gst.PadProbeReturn.OK


def main():
    global pipeline, osd, glshader
    global ipc_client

    logger.info("Trying to connect to IPC server...")
    ipc_client = create_rocam_ipc_client()
    logger.info("Connected to IPC server.")

    Gst.init(None)

    pipeline_desc = f"""
        nvv4l2camerasrc device={CAMERA} cap-buffers=2 !
        video/x-raw(memory:NVMM),framerate=60/1,width={WIDTH},height={HEIGHT} !
        tee name=t

        t. !
        nvvideoconvert !
        mux.sink_0 nvstreammux name=mux width={WIDTH} height={HEIGHT} live-source=1 batch-size=1 !
        nvinfer name=infer config-file-path=pgie_config.txt !
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
        nvvideoconvert dest-crop=0:0:{int(WIDTH/4)}:{int(HEIGHT/4)} !
        video/x-raw(memory:NVMM),width={int(WIDTH/4)},height={int(HEIGHT/4)} !
        videorate !
        video/x-raw(memory:NVMM),framerate=30/1 !
        nvjpegenc quality=70 !
        multipartmux boundary=spionisto !
        tcpclientsink port=5001
    """

    # convert avi -> mp4: ffmpeg -i recording.avi -vf "transpose=1" -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 21 -an output.mp4
    pipeline = Gst.parse_launch(pipeline_desc)

    glshader = pipeline.get_by_name("shader")
    glshader.set_property('fragment', open("shader.frag").read())
    glshader.set_property('uniforms', Gst.Structure.new_from_string("uniforms, tx=(float)0.0, ty=(float)0.0, scale=(float)1.0"))

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    infer = pipeline.get_by_name("infer")
    infer_source_pad = infer.get_static_pad("src")
    infer_source_pad.add_probe(Gst.PadProbeType.BUFFER, inference_stop_probe, 0)

    osd = pipeline.get_by_name("osd")

    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    os.nice(-10)
    main()
