import gi, sys

#gi.require_version('Gst','1.0')
from gi.repository import Gst, GstRtspServer, GObject

GObject.threads_init()
#from twisted.internet import gireactor
#gireactor.install()

Gst.init(None)
from twisted.internet import reactor
from twisted.python import log

class PSrtspServer(object):
	def __init__(self):
		self.rtspServer = GstRtspServer.RTSPServer.new()
		self.rtspMediaFactory = GstRtspServer.RTSPMediaFactory.new()
	
	def start(self):
		mounts = self.rtspServer.get_mount_points()
		self.rtspServer.set_service("554")
		self.rtspMediaFactory.set_launch('videotestsrc ! \
		     video/x-raw,format=RGB,width=640,height=480,framerate=30/1 ! \
		     videoconvert ! vp8enc ! rtpvp8pay name=pay0 pt=96')
		mounts.add_factory('/live',self.rtspMediaFactory)
		stat = self.rtspServer.attach(None)
		print stat

if __name__ == '__main__':
	log.startLogging(sys.stdout)
	#loop = GObject.MainLoop()
	rtsp = PSrtspServer()
	rtsp.start()
	
	reactor.run()
	#loop.run()
