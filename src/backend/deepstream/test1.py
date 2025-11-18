#!/usr/bin/env python3

################################################################################
# SPDX-FileCopyrightText: Copyright (c) 2020-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

import sys

sys.path.append('../')
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from bus_call import bus_call
from utils import *
from threading import Lock

import pyds
import time

MUXER_BATCH_TIMEOUT_USEC = 33000

_inference_start_time = {}

def inference_start_probe(pad, info, u_data):
    global _inference_start_time

    caps = pad.get_current_caps()
    if caps:
        print(f"  Pad: {pad.get_name()}")
        for i in range(caps.get_size()):
            s = caps.get_structure(i)
            print(f"    {s.to_string()}")

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    key = hash(gst_buffer)
    _inference_start_time[key] = time.perf_counter()

    return Gst.PadProbeReturn.OK

def inference_stop_probe(pad, info, u_data):
    global _inference_start_time

    caps = pad.get_current_caps()
    if caps:
        print(f"  Pad: {pad.get_name()}")
        for i in range(caps.get_size()):
            s = caps.get_structure(i)
            print(f"    {s.to_string()}")

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

def osd_sink_pad_buffer_probe2(pad, info, u_data):
    global _fps_last_time

    now = time.perf_counter()
    elapsed = now - _fps_last_time
    fps = 1 / elapsed
    print(f"FPS: {fps:.2f}, frame time: {elapsed * 1000:.2f} ms")
    _fps_last_time = now

    return Gst.PadProbeReturn.OK

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # pts_ns = gst_buffer.pts  # nanoseconds
    # if pts_ns != Gst.CLOCK_TIME_NONE:
    #     now = pts_ns / 1e9
    #     elapsed = now - _fps_last_time
    #     fps = 1 / elapsed
    #     # print(f"FPS: {fps:.2f}, frame time: {elapsed * 1000:.2f} ms")
    #     _fps_last_time = now


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

        #print(frame_meta)


        l_obj = frame_meta.obj_meta_list
        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            # print(obj_meta)

            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        # Acquiring a display meta object. The memory ownership remains in
        # the C code so downstream plugins can still access it. Otherwise
        # the garbage collector will claim it when this probe function exits.
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1

        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

        try:
            l_frame = l_frame.next
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK


def main(args):
    # Check input arguments
    camera = "/dev/video0"

    # Standard GStreamer initialization
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Source element for reading from the file
    print("Creating Source \n ")
    source = Gst.ElementFactory.make("v4l2src", "usb-cam-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")

    caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
    if not caps_v4l2src:
        sys.stderr.write(" Unable to create v4l2src capsfilter \n")

    queue_1 = Gst.ElementFactory.make("queue", "queue1")
    if not queue_1:
        sys.stderr.write(" Unable to create queue1 \n")

    caps_v4l2src_2 = Gst.ElementFactory.make("capsfilter", "v4l2src_caps_2")
    if not caps_v4l2src:
        sys.stderr.write(" Unable to create v4l2src capsfilter \n")

    print("Creating Video Converter \n")

    # Adding videoconvert -> nvvideoconvert as not all
    # raw formats are supported by nvvideoconvert;
    # Say YUYV is unsupported - which is the common
    # raw format for many logi usb cams
    # In case we have a camera with raw format supported in
    # nvvideoconvert, GStreamer plugins' capability negotiation
    # shall be intelligent enough to reduce compute by
    # videoconvert doing passthrough (TODO we need to confirm this)

    # nvvideoconvert to convert incoming raw buffers to NVMM Mem (NvBufSurface API)
    nvvidconvsrc = Gst.ElementFactory.make("nvvideoconvert", "convertor_src2")
    if not nvvidconvsrc:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    caps_vidconvsrc = Gst.ElementFactory.make("capsfilter", "nvmm_caps")
    if not caps_vidconvsrc:
        sys.stderr.write(" Unable to create capsfilter \n")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")



    # Use nvinfer to run inferencing on camera's output,
    # behaviour of inferencing is set through config file
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    # queue_2 = Gst.ElementFactory.make("queue", "queue2")
    # if not queue_2:
    #     sys.stderr.write(" Unable to create queue2 \n")

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    # Finally render the osd output
    print("Creating nv3dsink \n")
    sink = Gst.ElementFactory.make("fpsdisplaysink", "nv3d-sink")
    if not sink:
        sys.stderr.write(" Unable to create nv3dsink \n")

    print("Playing cam %s " % camera)
    caps_v4l2src.set_property('caps', Gst.Caps.from_string("video/x-raw, framerate=60/1, width=1920, height=1080"))
    caps_v4l2src_2.set_property('caps', Gst.Caps.from_string("video/x-raw, framerate=60/1, width=1920, height=1080"))
    caps_vidconvsrc.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM)"))
    source.set_property('device', camera)
    source.set_property('io-mode', 2)
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', 1)
    streammux.set_property('live-source', 1)
    streammux.set_property('buffer-pool-size', 1)
    streammux.set_property('compute-hw', 1)
    streammux.set_property('batched-push-timeout', MUXER_BATCH_TIMEOUT_USEC)
    queue_1.set_property('max-size-buffers', 2)
    pgie.set_property('config-file-path', "dstest1_pgie_config.txt")
    # queue_2.set_property('max-size-buffers', 1)
    # Set sync = false to avoid late frame drops at the display-sink
    sink.set_property('sync', False)

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(caps_v4l2src)
    pipeline.add(nvvidconvsrc)
    pipeline.add(caps_vidconvsrc)
    pipeline.add(caps_v4l2src_2)
    pipeline.add(streammux)
    pipeline.add(queue_1)
    pipeline.add(pgie)
    # pipeline.add(queue_2)
    pipeline.add(nvvidconv)
    pipeline.add(sink)

    # we link the elements together
    # v4l2src -> nvvideoconvert -> mux -> 
    # nvinfer -> nvvideoconvert -> nvosd -> video-renderer
    print("Linking elements in the Pipeline \n")
    # source.link(caps_v4l2src)
    # caps_v4l2src.link(nvvidconvsrc)
    # nvvidconvsrc.link(caps_vidconvsrc)

    # sinkpad = streammux.request_pad_simple("sink_0")
    # if not sinkpad:
    #     sys.stderr.write(" Unable to get the sink pad of streammux \n")
    # srcpad = caps_vidconvsrc.get_static_pad("src")
    # if not srcpad:
    #     sys.stderr.write(" Unable to get source pad of caps_vidconvsrc \n")
    # srcpad.link(sinkpad)
    # streammux.link(pgie)
    # pgie.link(nvvidconv)
    # nvvidconv.link(sink)
    source.link(caps_v4l2src)
    caps_v4l2src.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = sink.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    # osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe2, 0)
    #
    # infersinkpad = pgie.get_static_pad("sink")
    # if not infersinkpad:
    #     sys.stderr.write(" Unable to get sink pad of pgie \n")
    # infersinkpad.add_probe(Gst.PadProbeType.BUFFER, inference_start_probe, 0)
    #
    # infersrcpad = pgie.get_static_pad("src")
    # if not infersrcpad:
    #     sys.stderr.write(" Unable to get src pad of pgie \n")
    # infersrcpad.add_probe(Gst.PadProbeType.BUFFER, inference_stop_probe, 0)

    # start play back and listen to events
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
    sys.exit(main(sys.argv))
