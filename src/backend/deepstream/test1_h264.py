#!/usr/bin/env python3

################################################################################
# SPDX-FileCopyrightText: Copyright (c) 2019-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
import os
import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from bus_call import bus_call
from utils import *
import pyds
import time

PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3
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

def osd_sink_pad_buffer_probe(pad, info, u_data):
    global _fps_last_time

    caps = pad.get_current_caps()
    if caps:
        print(f"  Pad: {pad.get_name()}")
        for i in range(caps.get_size()):
            s = caps.get_structure(i)
            print(f"    {s.to_string()}")

    now = time.perf_counter()
    elapsed = now - _fps_last_time
    fps = 1 / elapsed
    print(f"FPS: {fps:.2f}, frame time: {elapsed * 1000:.2f} ms")
    _fps_last_time = now

    return Gst.PadProbeReturn.OK


def main(args):
    # Check input arguments
    file_path = "/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264"

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
    source = Gst.ElementFactory.make("filesrc", "file-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")

    # Since the data format in the input file is elementary h264 stream,
    # we need a h264parser
    print("Creating H264Parser \n")
    h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
    if not h264parser:
        sys.stderr.write(" Unable to create h264 parser \n")

    # Use nvdec_h264 for hardware accelerated decode on GPU
    print("Creating Decoder \n")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
    if not decoder:
        sys.stderr.write(" Unable to create Nvv4l2 Decoder \n")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    # Use nvinfer to run inferencing on decoder's output,
    # behaviour of inferencing is set through config file
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    # Use convertor to convert from NV12 to RGBA as required by nvosd
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    # Create OSD to draw on the converted RGBA buffer
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")

    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    # Finally render the osd output
    print("Creating nv3dsink \n")
    sink = Gst.ElementFactory.make("nvdrmvideosink", "nv3d-sink")
    if not sink:
        sys.stderr.write(" Unable to create nv3dsink \n")


    print("Playing file %s " % file_path)
    source.set_property('location', file_path)
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batched-push-timeout', MUXER_BATCH_TIMEOUT_USEC)
    streammux.set_property('live-source', 1)
    streammux.set_property('buffer-pool-size', 1)
    streammux.set_property('compute-hw', 1)
    streammux.set_property('batch-size', 1)
    pgie.set_property('config-file-path', "dstest1_pgie_config.txt")
    sink.set_property('sync', False)

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(h264parser)
    pipeline.add(decoder)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(sink)

    # we link the elements together
    # file-source -> h264-parser -> nvh264-decoder ->
    # nvinfer -> nvvidconv -> nvosd -> video-renderer
    print("Linking elements in the Pipeline \n")
    source.link(h264parser)
    h264parser.link(decoder)

    sinkpad = streammux.request_pad_simple("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")
    srcpad = decoder.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of decoder \n")
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(nvvidconv)
    nvvidconv.link(nvosd)
    nvosd.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # Lets add probe to get informed of the meta data generated, we add probe to
    # the sink pad of the osd element, since by that time, the buffer would have
    # had got all the metadata.
    osdsinkpad = nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    infersinkpad = pgie.get_static_pad("sink")
    if not infersinkpad:
        sys.stderr.write(" Unable to get sink pad of pgie \n")
    infersinkpad.add_probe(Gst.PadProbeType.BUFFER, inference_start_probe, 0)

    infersrcpad = pgie.get_static_pad("src")
    if not infersrcpad:
        sys.stderr.write(" Unable to get src pad of pgie \n")
    infersrcpad.add_probe(Gst.PadProbeType.BUFFER, inference_stop_probe, 0)

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
