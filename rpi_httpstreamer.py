# http://www.packetservo.com/cam/rpi_stream/mushak0004

import sys, json, Cookie, os, fcntl, time, collections
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.static import File, Data
from twisted.web.resource import Resource, NoResource
from twisted.internet import defer, reactor

from PacketAES import AESCipher
from persona import CamCheck
from twisted.python.filepath import FilePath
from identitytoolkit import gitkitclient

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

gitkit_instance = gitkitclient.GitkitClient(
#gitkit_instance = gitkitclient.FromConfigFile(config_json)(
	client_id="912263063433-i8se3d23v29chlnocovc4umi8cuqdbmd.apps.googleusercontent.com",
	service_account_email="912263063433-mf2pq0ap6cb7rsuiot6126dn1c87c29s@developer.gserviceaccount.com",
	service_account_key=key,
	widget_url="http://www.packetservo.com/auth/login"
	)

class WebMStream(object):
	def __init__(self):
		self.make_pipeline()
		self.stopProducing()
		
	def removeClient(self,fdsink,fd):
		print "6--> client removed"
		self.factory.sendCommand("stop",isBinary=False)
		self.resource._removeClient(fd)
		
	def feed(self,capstring,frame):
		if not self.playing:
			self.startProducing()
		#gstcaps = Gst.Caps().from_string(capstring)
		#capstring = "video/x-h264, width=(int)640, height=(int)480, framerate=(fraction)30/1, stream-format=(string)byte-stream, alignment=(string)au, profile=(string)baseline, parsed=(boolean)true;"
		#print "5.1 --> capstring {0}".format(capstring)
		gstcaps = Gst.Caps.from_string(capstring)
		gstbuff = Gst.Buffer.new_wrapped(frame)
		print "5.1 --> gstbuff {0}".format(gstbuff)
		self.appsource.set_property("caps",gstcaps)
		#gstsample = Gst.Sample(gstbuff,gstcaps,None,None)
		#gstsample = Gst.Sample.new(gstbuff,gstcaps,None,None)
		#ret = self.appsource.emit("push-sample",gstsample)
		ret = self.appsource.emit("push-buffer",gstbuff)
		if (ret != Gst.FlowReturn.OK):
			print "5.2 --> frames not pushed"
			return False
		print "5.2 --> frames pushed"
		return True
	
	def make_pipeline(self):
		CLI = [
		'appsrc name="source" ! ',
		'mp4mux faststart=true streamable=true ! ',
		#'mp4mux fragment-duration=500 faststart=true streamable=true ! ',
		'multifdsink name="sink"',
		]
		CLI2 = 'appsrc name="source" ! multifdsink name="sink"'
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		#self.pipeline = Gst.parse_launch(CLI2)
		self.appsource = self.pipeline.get_by_name("source")
		self.appsource.set_property("is-live",True)
		#self.appsource.connect("need-data",self.need_data)
		#self.appsource.connect("enough-data",self.enough_data)
		self.fdsink = self.pipeline.get_by_name("sink")
		self.fdsink.connect("client-fd-removed",self.removeClient)
		self.fdsink.set_property("sync-method",2)
		self.fdsink.set_property('buffers-soft-max', 50)
		self.fdsink.set_property('buffers-max', 100)
		
	def add_client(self,fd):
		print "5--> adding client"
		self.factory.sendCommand("play",isBinary=False)
		self.fdsink.emit("add",fd)
			
	def startProducing(self):
		self.playing = True
		self.stopped = False
		self.pipeline.set_state(Gst.State.PLAYING)
	
	def stopProducing(self):
		self.playing = False
		self.stopped = True
		#self.appsource.end_of_stream()
		#self.appsource.emit('end-of-stream')
		self.pipeline.set_state(Gst.State.READY)

class PSProto(WebSocketServerProtocol):
	producer = None
	
	def onConnect(self,request):
		myAES = AESCipher(key)
		if 'cookie' in request.headers:
			try:
				cookie = Cookie.SimpleCookie()
				cookie.load(str(request.headers['cookie']))
			except Cookie.CookieError:
				pass
			
			if ('wsid' in cookie) and ('PSClient' in request.headers['user-agent']):
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
		self.do_feed = False
		self.factory.register(self)
		
	def onMessage(self,payload,isBinary):
		if not isBinary:
			self.do_feed = False
			self.capstring = payload.decode('utf-8')
		else:
			self.do_feed = True
			frame = payload		
		if self.do_feed:
			self.factory.streamer.feed(self.capstring,frame)
		
	def onClose(self, wasClean, code, reason):
		self.do_feed = False
		self.factory.streamer.stopProducing()
		self.factory.unregister(self)
		
	def connectionLost(self,reason):
		self.do_feed = False
		self.factory.streamer.stopProducing()
		WebSocketServerProtocol.connectionLost(self,reason)
		self.factory.unregister(self)

class PSFactory(WebSocketServerFactory):
	
	def __init__(self,streamer):
		self.clients = []
		self.streamer = streamer
		self.streamer.factory = self
		WebSocketServerFactory.__init__(self)
		
	def register(self,client):
		if client not in self.clients:
			self.clients.append(client)

	def unregister(self,client):
		if client in self.clients:
			self.clients.remove(client)
	
	def sendCommand(self,msg,isBinary):
		for c in self.clients:
			c.sendMessage(msg.encode('utf-8'),isBinary)
	
class Live(Resource):
	isLeaf = True
	def __init__(self,streamer):
		self._request = {}
		self.streamer = streamer
		self.streamer.resource = self
		Resource.__init__(self)
	
	def _removeClient(self,fd):
		self._request[fd].transport.loseConnection()
		print "7--> lose connection successfull"
		self.streamer.stopProducing()
		del self._request[fd]
	
	def _formatHeaders(self, request):
		headers = []
		for name, value in request.headers.items():
			headers.append('%s: %s\r\n' % (name, value))
		for cookie in request.cookies:
			headers.append('%s: %s\r\n' % ("Set-Cookie", cookie))
		return headers
	
	def _writeHeaders(self,request):
		fd = request.transport.fileno()
		fdi = request.fdIncoming
		
		if (fd == -1) or (fd != fdi):
			print "fd not matching error"
			return False
		
		request.setHeader('Server','PacketServo Streaming')
		request.setHeader('Date',time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time())))
		request.setHeader('Cache-Control', 'no-cache')
		#request.setHeader('Content-type', 'video/webm')
		request.setHeader('Content-type', 'video/mp4')
		request.setHeader('Connection', 'close, keep-alive')
		headers = self._formatHeaders(request)
		try:
			os.write(fd, 'HTTP/1.0 200 OK\r\n%s\r\n' % ''.join(headers))
			request.startedWriting = True
			print "3--> headers sent"
			return True
		except OSError:
			print "header write error"
			return False
		
		return False
	
	def startFeed(self,request):
		fdi = request.fdIncoming
		fd = request.transport.fileno()
		self._request[fd] = request
		print("2--> reached startFeed {0}".format(fd))
		
		if self._writeHeaders(request):
			print "4--> removing reader"
			reactor.removeReader(request.transport)
		else:
			print "removeReader error"
			return 
		
		try:
			fcntl.fcntl(fd,fcntl.F_GETFL)
		except IOError:
			print "fcntl error"
			return
		
		self.streamer.add_client(fd)
	
	def checkAuth(self,request):
		myAES = AESCipher(key)
		gtoken = request.getCookie('gtoken')
		wsid = request.getCookie('wsid')
		user_data = json.loads(myAES.decrypt(wsid))
		gitkit_user = gitkit_instance.VerifyGitkitToken(gtoken)
		
		mycams = CamCheck().cbquery(gitkit_user.user_id)
		if mycams == user_data['cams']:
			print "1--> {0} authenticated".format(gitkit_user.user_id)
			return request
		else:
			return failure.Failure()
			
	
	def startAuth(self,request):
		d = defer.Deferred()
		d.callback(self.checkAuth(request))
		return d
		
	def errorPage(self,request):
		request.setResponseCode(401)
		request.write("Not authorized")
		return request
		
	def render_GET(self,request):
		fd = request.transport.fileno()
		request.fdIncoming = fd
		
		d = self.startAuth(request)
		d.addCallback(self.startFeed)
		d.addErrback(self.errorPage)
		return NOT_DONE_YET
	
class Stream(Resource):
	WSmap = collections.defaultdict(list)
		
	def getChild(self,name,request):
		protoType = request.getHeader('upgrade')
		if not protoType:
			if name in self.WSmap:
				return self.WSmap[name][1]
			else:
				return NoResource()
		elif protoType.lower() == 'websocket':
			if name in self.WSmap:
				return self.WSmap[name][0]
			else:
				streamer = WebMStream()
				factory = PSFactory(streamer)
				factory.protocol = PSProto
				factory.setProtocolOptions(maxConnections=2)
				factory.startFactory()
				self.WSmap[name].append(WebSocketResource(factory))
				self.WSmap[name].append(Live(streamer))
				return self.WSmap[name][0]

