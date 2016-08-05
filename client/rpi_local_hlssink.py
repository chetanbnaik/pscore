import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst, GstVideo
#GObject.threads_init()
import sys
from twisted.internet import gireactor # for non-GUI apps
gireactor.install()
Gst.init(None)
from twisted.internet import reactor, interfaces, defer

class HLSProducer(object):
	def __init__(self):
		self.started = False
		self.paused = False
		self.ts_pool = []
		self.playlist_pool = []
		self.make_pipeline()
		
	def pauseProducing(self):
		self.paused = True
		
	def resumeProducing(self):
		self.paused = False
		if not self.started:
			self.play_pipeline()
			self.started = True
	
	def probe_callback(self,hlssink_pad,info):
		#info_event = info.get_event()
		print info.type
		#info_structure = info_event.get_structure()
		#print info_structure.to_string()
		#if info_structure.has_name("GstForceKeyUnit"):
			#tscount = info_structure.get_uint("count")
			#tsfilename = "segment%05d.ts" % (tscount[1] - 1)
			##d = defer.Deferred()
			##d.callback(self.push_ts(tsfilename))
			##d.addCallback(self.push_pl)
		return Gst.PadProbeReturn.PASS

	def make_pipeline(self):
		CLI = [
		'v4l2src ! video/x-raw,format=RGB,width=640,height=480,framerate=30/1 ! ',
		'videoconvert ! x264enc bitrate=128 ! mpegtsmux name="mux" ! hlssink name="sink"',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		self.hlssink = self.pipeline.get_by_name("sink")
		self.hlssink.set_property("target-duration",2)
		
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
		self.hlssink_pad = self.hlssink.get_static_pad("sink")
		probe_id = self.hlssink_pad.add_probe(Gst.PadProbeType.EVENT_UPSTREAM,self.probe_callback)
			
	def stop_pipeline(self):
		self.pipeline.set_state(Gst.State.READY)
		
	def delete_pipeline(self):
		self.pipeline.set_state(Gst.State.NULL)

	def stopProducing(self):
		self.ts_pool = []
		self.playlist_pool = []
		self.stop_pipeline()
		self.started = False
	
	def stopHLS(self):
		self.ts_pool = []
		self.playlist_pool = []
		self.delete_pipeline()
		self.started = False

			
if __name__ == '__main__':
	from twisted.python import log
	log.startLogging(sys.stdout)
	hls = HLSProducer()
	try:
		hls.make_pipeline()
		hls.play_pipeline()
		reactor.run()
	except KeyboardInterrupt:
		hls.stopHLS()

		
