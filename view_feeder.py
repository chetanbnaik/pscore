import sys, json, Cookie
from twisted.web.server import Site
from twisted.web.static import File, Data
from twisted.web.resource import Resource
from zope.interface import implementer

from twisted.internet import interfaces
from PacketAES import AESCipher
from persona import CamCheck
from twisted.python.filepath import FilePath

import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst
GObject.threads_init()
Gst.init(None)

from autobahn.twisted.websocket import WebSocketServerFactory, \
     WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource

p12_file = FilePath('/home/chetan/pscore/protected/PacketServo-267cefd0c2d6.p12')
f = p12_file.open('r')
key = f.read()
f.close()	

@implementer(interfaces.IPushProducer)
class WebMProducer(object):
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
		'webmmux name="mux" ! appsink name="sink" videotestsrc ',
		'! video/x-raw,format=RGB,width=640,height=480,framerate=30/1 !',
		' clockoverlay text="PacketServo" shaded-background=true ! ',
		'videoconvert ! vp8enc target-bitrate=256000 ! mux.video_0',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		
	def play_pipeline(self):
		appsink = self.pipeline.get_by_name("sink")
		appsink.set_property("max-buffers",30)
		appsink.set_property("emit-signals",True)
		appsink.set_property("sync",False)
		appsink.set_property("async",False)
		appsink.connect('new-sample', self.push)
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
		self.stop_pipeline()

@implementer(interfaces.IPushProducer)
class WebMTransmit:
	def __init__(self,proto):
		self.proto = proto
		self.started = False
		self.paused = False
		self.buffer_pool = []
	
	def pauseProducing(self):
		self.paused = True

	def resumeProducing(self):
		self.paused = False
		
	def stopProducing(self):
		pass
		
	def push(self,message,isBinary):
		if not self.paused:
			if len(self.buffer_pool) > 0:
				self.proto.sendMessage(self.buffer_pool.pop(0),isBinary)
			else:
				self.proto.sendMessage(message,isBinary)
		else:
			self.buffer_pool.append(message)

class PSProto(WebSocketServerProtocol):
	def onConnect(self,request):
		myAES = AESCipher(key)
		if 'cookie' in request.headers:
			try:
				cookie = Cookie.SimpleCookie()
				cookie.load(str(request.headers['cookie']))
			except Cookie.CookieError:
				pass
		
			if ('gtoken' in cookie) and ('wsid' in cookie):
				gtoken = cookie['gtoken'].value
				wsid = cookie['wsid'].value
				user_data = json.loads(myAES.decrypt(wsid))
				mycams = CamCheck().cbquery(user_data['user_id'])
				if mycams == user_data['cams']:
					return None
				else:
					self.sendClose()
			elif ('wsid' in cookie) and (request.headers['user-agent'] == 'PSClient':
				wsid = cookie['wsid'].value
				cambot = json.loads(myAES.decrypt(wsid))
				if cambot['id'] in request.path:
					return None
				else:
					self.sendClose()
			else:
				self.sendClose()
		else:
			self.sendClose()
	
	def onOpen(self):
		self.factory.register(self)
		self.producer = WebMProducer(self)
		#self.producer = WebMTransmit(self)
		self.registerProducer(self.producer,True)
		
	def onMessage(self,payload,isBinary):
		if not isBinary:
			cmd_received = payload.decode('utf-8')
			if cmd_received == 'play':
				self.producer.resumeProducing()
			elif cmd_received == 'stop':
				self.producer.stopProducing()
		
		#if not isBinary:
			#msg = payload.decode('utf8')
		#else:
			#msg = payload
		#self.factory.forward(payload,isBinary,self)
		
	def onClose(self, wasClean, code, reason):
		self.producer.stopProducing()
		self.factory.unregister(self)
		
	def connectionLost(self,reason):
		self.producer.stopProducing()
		WebSocketServerProtocol.connectionLost(self,reason)
		self.factory.unregister(self)

class PSFactory(WebSocketServerFactory):
	#def __init__(self, wsuri, debug=False):
		#self.clients = []
		#WebSocketServerFactory.__init__(self, wsuri, debug=debug, debugCodePaths=debug)
	
	def __init__(self):
		self.clients = []
		WebSocketServerFactory.__init__(self)
				
	def register(self,client):
		if client not in self.clients:
			self.clients.append(client)

	def unregister(self,client):
		if client in self.clients:
			self.clients.remove(client)
			
	def forward(self,msg,isBinary,fromclient):
		for c in self.clients:
			if c != fromclient:
				if isBinary:
					c.producer.push(msg,isBinary)
				else:
					c.producer.push(msg.encode('utf-8'),isBinary)
	
	
class View(Resource):
	WSmap = {}
		
	def getChild(self,name,request):
		if name in self.WSmap:
			return self.WSmap[name]
		else:
			factory = PSFactory()
			factory.protocol = PSProto
			factory.startFactory()
			self.WSmap[name] = WebSocketResource(factory)
			return self.WSmap[name]
