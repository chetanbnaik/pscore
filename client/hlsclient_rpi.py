import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst, GstVideo
#GObject.threads_init()

from twisted.internet import gireactor # for non-GUI apps
gireactor.install()
Gst.init(None)

from twisted.internet import reactor, interfaces, defer
from twisted.internet.protocol import ReconnectingClientFactory
from zope.interface import implementer
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory, connectWS

import requests, json, Cookie, sys
from requests.auth import HTTPDigestAuth
from twisted.python.filepath import FilePath

camid = 'mushak0001'
tokenURL = b"http://www.packetservo.com/ps/register"
wsurl = "ws://www.packetservo.com/hls/live/"+camid

@implementer(interfaces.IPushProducer)
class HLSProducer:
	def __init__(self,proto):
		self.proto = proto
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
	
	def probe_callback(self,hlssink_pad,info,userdata):
		info_event = info.get_event()
		info_structure = info_event.get_structure()
		if info_structure.has_name("GstForceKeyUnit"):
			tscount = info_structure.get_uint("count")
			if tscount[1] >= 2:
				tsfilename = "segment%05d.ts" % (tscount[1] - 2)
				d = defer.Deferred()
				d.callback(self.push_ts(tsfilename))
				d.addCallback(self.push_pl)
		return Gst.PadProbeReturn.PASS
	
	def push_ts(self,tsfilename):
		tsfile = FilePath(tsfilename).asBytesMode()
		tscontent = tsfile.getContent()
		if not self.paused:
			if len(self.ts_pool) > 0:
				tscontent,tsfilename = self.ts_pool.pop(0)
				self.proto.sendMessage(tsfilename)
				self.proto.sendMessage(tscontent,isBinary=True)
				print "---> segment pushed from buffer"
			else:
				self.proto.sendMessage(tsfilename)
				self.proto.sendMessage(tscontent,isBinary=True)
				print "---> segment pushed directly"
		else:
			self.ts_pool.append((tscontent,tsfilename))
		
		return tsfilename
		
	def push_pl(self,tsfilename):
		plfile = FilePath("playlist.m3u8").asBytesMode()
		if plfile.exists():
			plcontent = plfile.getContent()
			if not self.paused:
				self.proto.sendMessage("playlist.m3u8")
				self.proto.sendMessage(plcontent,isBinary=True)
				print "---> playlist.m3u8 pushed directly"
			else:
				print "---> buffer not free"
		
		return True

	def make_pipeline(self):
		CLI = [
		'v4l2src ! video/x-raw,format=RGB,width=320,height=240,framerate=30/1 ! ',
		'videoconvert ! x264enc bitrate=64 ! mpegtsmux name="mux" ! hlssink name="sink"',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		self.hlssink = self.pipeline.get_by_name("sink")
		self.hlssink.set_property("target-duration",2)
		self.hlssink_pad = self.hlssink.get_static_pad("sink")
		probe_id = self.hlssink_pad.add_probe(Gst.PadProbeType.EVENT_UPSTREAM,self.probe_callback,"dummy")
		
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
			
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

class MyControlProtocol(WebSocketClientProtocol):
	
	producer = None
	
	def onOpen(self):
		print "Websocket control channel open"
		
	def onMessage(self,payload,isBinary):
		if not isBinary:
			command = payload.decode('utf-8')
			if command == 'play':
				print command
				#self.producer.resumeProducing()
			elif command == 'pause':
				print command
				#self.producer.stopProducing()
				#self.producer.stopHLS()
			print command
	
	def onClose(self,wasClean,code,reason):
		self.producer.stopProducing()
		#self.producer.stopHLS()
		print("WebSocket control channel closed: {0}".format(reason))
		
class MyClientProtocol(WebSocketClientProtocol):
	
    producer = None

    def openControl(self):
		factoryControl = MyClientFactory(wsurl+"/control",headers=headers)
		factoryControl.protocol = MyControlProtocol
		factoryControl.protocol.producer = self.producer
		connectWS(factoryControl)
    
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        self.producer = HLSProducer(self)
        self.registerProducer(self.producer,True)
        print("WebSocket connection open.")
	self.openControl()
        #self.producer.resumeProducing()

    def onMessage(self, payload, isBinary):
		if not isBinary:
			cmd_received = payload.decode('utf-8')
			if cmd_received == 'play':
				print "starting to play"
				#self.producer.resumeProducing()
			elif cmd_received == 'stop':
				self.producer.stopProducing()
				print "stopping to play"
			else:
				print("Command received: {0}".format(cmd_received))	
		
    def onClose(self, wasClean, code, reason):
		if self.producer:
			self.producer.stopProducing()
			#self.producer.stopHLS()
		print("WebSocket connection closed: {0}".format(reason))
		
		
class MyClientFactory(WebSocketClientFactory, ReconnectingClientFactory):

    maxDelay = 10
		
    def clientConnectionFailed(self, connector, reason):
        print("Client connection failed .. retrying ..")
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        print("Client connection lost .. retrying ..")
        self.retry(connector)

def GetToken():
	user=camid
	success = False
	password='mushak'
	auth=HTTPDigestAuth(user,password)
	
	headers = {'user-agent':'PSClient'}
	payload = {'name':'mushak','id':camid}
	
	r = requests.post(tokenURL,data=json.dumps(payload),headers=headers,auth=auth)
	cookies = Cookie.SimpleCookie()
	cookies.load(r.cookies)
	if (r.status_code == 200) and ('wsid' in cookies):
		headers['cookie'] = cookies['wsid']
		success = True
	
	return headers, success
			
if __name__ == '__main__':
	from twisted.python import log
	log.startLogging(sys.stdout)
	
	success= False
	while not success:
		headers, success = GetToken()
	
	factory = MyClientFactory(wsurl,headers=headers)
	factory.protocol = MyClientProtocol
	connectWS(factory)
	
	#factory = MyClientFactory("ws://localhost:8080/"+camid)
	
	reactor.run()

		
