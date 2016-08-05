from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, threads, interfaces
from twisted.internet.task import LoopingCall
from zope.interface import implementer
from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory, connectWS

import requests, json, Cookie, sys
from requests.auth import HTTPDigestAuth

import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst, GstVideo
GObject.threads_init()
Gst.init(None)

camid = 'mushak0004'
tokenURL = b"http://www.packetservo.com/ps/register"
wsurl = "ws://www.packetservo.com/hls/live/"+camid


class Producer(object):
	def __init__(self):
		self.count = 0
		self.l = LoopingCall(self.send_event)
		self.proto = proto
		self.started = False
		self.paused = False
		self.make_pipeline()
		
	def pauseProducing(self):
		self.paused = True
		
	def resumeProducing(self):
		self.paused = False
		
		if not self.started:
			self.play_pipeline()
			print "--> resumed"
			self.started = True
	
	def send_event(self):
		self.count = self.count+1
		#if self.count > 2147483640:
			#self.count = 0	
		pushed = self.appsink_pad.push_event(GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE,True,self.count))
		print "key unit event sent... {0}".format(pushed)
	
	def make_pipeline(self):
		gcmd = ''.join(CLI2)
		self.pipeline = Gst.parse_launch(gcmd)
		appsink = self.pipeline.get_by_name("sink")
		appsink.set_property("max-buffers",30)
		appsink.set_property("emit-signals",True)
		appsink.set_property("sync",True)
		appsink.set_property("async",True)
		appsink.connect('new-sample', self.push)
		self.appsink_pad = appsink.get_static_pad("sink")
		
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
		self.l.start(5.0,False)
		
	def stop_pipeline(self):
		self.pipeline.set_state(Gst.State.READY)
		self.l.stop()
		
	def stopProducing(self):
		self.stop_pipeline()
		self.started = False

class MyClientProtocol(WebSocketClientProtocol):
	
    producer = Producer()
    
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
		if not isBinary:
			cmd_received = payload.decode('utf-8')
			if cmd_received == 'play':
				print "starting to play"
				self.producer.resumeProducing()
			elif cmd_received == 'stop':
				self.producer.stopProducing()
				print "stopping to play"
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
	#factory = MyClientFactory("ws://localhost:8080/live")
	connectWS(factory)
	
	reactor.run()
