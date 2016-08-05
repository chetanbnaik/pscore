from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, threads, interfaces
from zope.interface import implementer
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory, connectWS

import requests, json, Cookie, sys
from requests.auth import HTTPDigestAuth

import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst
GObject.threads_init()
Gst.init(None)

camid = 'mushak0001'
tokenURL = b"http://www.packetservo.com/ps/register"
wsurl = "ws://www.packetservo.com/cam/view/"+camid

@implementer(interfaces.IPushProducer)
class WebMProducer:
	def __init__(self,proto):
		self.proto = proto
		self.started = False
		self.paused = False
		self.buffer_pool = []
		self.make_pipeline()
		
	def pauseProducing(self):
		self.paused = True
		
	def resumeProducing(self):
		self.paused = False
		
		if not self.started:
			self.play_pipeline()
			self.started = True
	
	def make_pipeline(self):
		CLI = [
		'webmmux name="mux" ! appsink name="sink" v4l2src device=/dev/video0 ',
		#'! video/x-raw,format=RGB,width=640,height=480,framerate=30/1 !',
		'! video/x-raw,format=RGB,width=320,height=240,framerate=30/1 !',
		' clockoverlay text="PacketServo" shaded-background=true ! ',
		'videoconvert ! vp8enc target-bitrate=256000 ! mux.video_0',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		appsink = self.pipeline.get_by_name("sink")
		appsink.set_property("max-buffers",30)
		appsink.set_property("emit-signals",True)
		appsink.set_property("sync",True)
		appsink.set_property("async",True)
		appsink.connect('new-sample', self.push)
		
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
		
	def stop_pipeline(self):
		self.pipeline.set_state(Gst.State.READY)
	
	def push(self,appsink):
		gstsample = appsink.emit('pull-sample')
		gstbuffer = gstsample.get_buffer()
		frame_data = gstbuffer.extract_dup(0,gstbuffer.get_size())
		
		if not self.paused:
			if len(self.buffer_pool) > 0:
				self.proto.sendMessage(self.buffer_pool.pop(0),isBinary=True)
			else:
				self.proto.sendMessage(frame_data,isBinary=True)
		else:
			self.buffer_pool.append(frame_data)
			
		return False
		
	def stopProducing(self):
		self.buffer_pool = []
		self.stop_pipeline()
		self.started = False

class MyClientProtocol(WebSocketClientProtocol):
	
    producer = None
    
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        self.producer = WebMProducer(self)
        self.registerProducer(self.producer,True)
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
		if not isBinary:
			cmd_received = payload.decode('utf-8')
			if cmd_received == 'play':
				self.producer.resumeProducing()
			elif cmd_received == 'stop':
				self.producer.stopProducing()
			else:
				print("Command received: {0}".format(cmd_received))	
		
    def onClose(self, wasClean, code, reason):
		if self.producer:
			self.producer.stopProducing()
		print("WebSocket connection closed: {0}".format(reason))
		
		
class MyClientFactory(WebSocketClientFactory, ReconnectingClientFactory):

    protocol = MyClientProtocol
    maxDelay = 60
		
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
	
	success= False
	while not success:
		headers, success = GetToken()
	
	factory = MyClientFactory(wsurl,headers=headers)
	connectWS(factory)
	
	reactor.run()
