import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst, GstVideo
GObject.threads_init()
Gst.init(None)

def scan(element,userdata):
	sinkpads = element.iterate_sink_pads()
	print element,sinkpads

CLI = [
'v4l2src ! video/x-raw,format=RGB,width=640,height=480,framerate=30/1 ! ',
'videoconvert ! x264enc bitrate=128 ! mpegtsmux name="mux" ! hlssink name="sink"',
]

gcmd = ''.join(CLI)
pipeline = Gst.parse_launch(gcmd)
hlssink = pipeline.get_by_name("sink")
sinks = pipeline.iterate_sinks()
sinks.foreach(scan,"check")
