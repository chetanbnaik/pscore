from twisted.internet import reactor, threads, interfaces

import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst
GObject.threads_init()
Gst.init(None)

# gst-launch-1.0 -v rpicamsrc ! 
# video/x-h264,width=640,height=480,framerate=30/1 ! 
# h264parse ! avdec_h264 ! vp8enc ! webmmux ! 
# appsink sync=true async=true

def analyse_sample(appsink):
	gstsample = appsink.emit('pull-sample')
	gstbuffer = gstsample.get_buffer()
	frame_data = gstbuffer.extract_dup(0,gstbuffer.get_size())
	
	gstcaps = gstsample.get_caps()
	gst_caps_struct = gstcaps.get_structure(0)
	gst_caps_string = gst_caps_struct.to_string()
	print 'buffer length --> ',len(frame_data)
	print 'GST caps --> ',gst_caps_string
	
	return False
	
class GStreamerClient(object):
	def __init__(self):
		self._gstclient = True
		
	def make_pipeline(self):
		CLI = [
		'rpicamsrc bitrate=3000000 rotation=180 ! ',
		'video/x-h264,width=640,height=480,framerate=30/1 ! h264parse ! mpegtsmux ! ',
		#'video/x-h264,width=640,height=480,framerate=30/1 ! ',
		#'qtmux ! ',
		#'avdec_h264 ! vp8enc target-bitrate=256000 ! webmmux ! ',
		#'mp4mux faststart=true streamable=true ! ',
		#'mp4mux fragment-duration=500 faststart=true streamable=true ! ',
		'appsink name="sink"',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		appsink = self.pipeline.get_by_name("sink")
		appsink.set_property("max-buffers",30)
		appsink.set_property("emit-signals",True)
		appsink.set_property("sync",False)
		appsink.set_property("async",False)
		appsink.connect('new-sample', analyse_sample)
	
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
			
	def stop_pipeline(self):
		print 'KeyboardInterrupt: Stopping pipeline!'
		self.pipeline.set_state(Gst.State.READY)
		
if __name__ == '__main__':
	myGST = GStreamerClient()
	try:
		myGST.make_pipeline()
		myGST.play_pipeline()
		reactor.run()
	except KeyboardInterrupt:
		myGST.stop_pipeline()
		
