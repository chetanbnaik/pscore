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


@implementer(interfaces.IPushProducer)
class WebMProducer:
	def __init__(self,proto):
		self.count = 0
		self.l = LoopingCall(self.send_event)
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
			print "--> resumed"
			self.started = True
	
	def send_event(self):
		self.count = self.count+1
		#if self.count > 2147483640:
			#self.count = 0	
		pushed = self.appsink_pad.push_event(GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE,True,self.count))
		print "key unit event sent... {0}".format(pushed)
	
	def make_pipeline(self):
		CLI = [
		'rpicamsrc bitrate=3000000 rotation=180 ! ',
		'video/x-h264,width=640,height=480,framerate=30/1 ! h264parse ! mpegtsmux ! ',
		#'avdec_h264 ! vp8enc target-bitrate=256000 ! webmmux ! ',
		#'mp4mux faststart=true streamable=true ! ',
		#'mp4mux fragment-duration=500 faststart=true streamable=true ! ',
		'appsink name="sink"',
		]
		CLI2 = [
		'v4l2src ! video/x-raw,format=RGB,width=640,height=480,framerate=30/1 ! ',
		#'clockoverlay text="PacketServo" shaded-background=true ! ',
		'videoconvert ! x264enc bitrate=128 ! mpegtsmux name="mux" ! appsink name="sink"',
		]
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
	
	def push(self,appsink):
		gstsample = appsink.emit('pull-sample')
		gstbuffer = gstsample.get_buffer()
		frame_data = gstbuffer.extract_dup(0,gstbuffer.get_size())
		#print "--> {0}".format(len(frame_data))
		
		gstcaps = gstsample.get_caps()
		gst_caps_struct = gstcaps.get_structure(0)
		gst_caps_string = gst_caps_struct.to_string()
		#print "--> {0}".format(gst_caps_string)
		
		if not self.paused:
			#print "here1..."
			if len(self.buffer_pool) > 0:
				#print "here2..."
				gst_caps_string, frame_data = self.buffer_pool.pop(0)
				self.proto.sendMessage(gst_caps_string)
				self.proto.sendMessage(frame_data,isBinary=True)
				#print "buffer sent from pool --> {0}".format(len(frame_data))
			else:
				#print "here3..."
				self.proto.sendMessage(gst_caps_string)
				self.proto.sendMessage(frame_data,isBinary=True)
				#print "buffer sent directly --> {0}".format(len(frame_data))
		else:
			#print "here4..."
			self.buffer_pool.append((gst_caps_string,frame_data))
			#print "--> buffer of length {0} appended".format(len(frame_data))

		#print "returning..."
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
        #self.producer.resumeProducing()

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
	
	#factory = MyClientFactory(wsurl,headers=headers)
	factory = MyClientFactory("ws://localhost:8080/live")
	connectWS(factory)
	
	reactor.run()
