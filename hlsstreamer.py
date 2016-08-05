# http://www.packetservo.com/cam/rpi_stream/mushak0004

import sys, json, Cookie, os, fcntl, time, collections, re
from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.static import File, Data
from twisted.web.resource import Resource, NoResource
from twisted.internet import defer, reactor, threads

from PacketAES import AESCipher
from persona import CamCheck
from twisted.python import failure
from twisted.python.filepath import FilePath
from identitytoolkit import gitkitclient

from autobahn.twisted.websocket import WebSocketServerFactory, \
     WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource

p12_file = FilePath('/home/chetan/pscore/protected/PacketServo-267cefd0c2d6.p12')
key_file = p12_file.open('r')
key = key_file.read()
key_file.close()

from jinja2 import Environment, FileSystemLoader
PSjinja_env = Environment(loader=FileSystemLoader('/home/chetan/pscore/templates'))

gitkit_instance = gitkitclient.GitkitClient(
	client_id="912263063433-i8se3d23v29chlnocovc4umi8cuqdbmd.apps.googleusercontent.com",
	service_account_email="912263063433-mf2pq0ap6cb7rsuiot6126dn1c87c29s@developer.gserviceaccount.com",
	service_account_key=key,
	widget_url="http://www.packetservo.com/auth/login"
	)

class CommandChannel(WebSocketServerProtocol):
	
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
					self.temp_location = self.factory.temp_path.child(cambot['id'])
					if not self.temp_location.exists():
						self.temp_location.makedirs()
					
					f = self.temp_location.child(u'index.html')
					g = FilePath("/home/chetan/pscore/templates/live_hls.html").asTextMode()
					content = g.getContent()
					new = content.replace("++camid++",cambot['id'])
					f.setContent(new)
					return None
				else:
					self.sendClose(1000,"Not authorised")
			elif ('wsid' in cookie) and ('gtoken' in cookie):
				wsid = cookie['wsid'].value
				gtoken = cookie['gtoken'].value
				user_data = json.loads(myAES.decrypt(wsid))
				gitkit_user = gitkit_instance.VerifyGitkitToken(gtoken)
				mycams = CamCheck().cbquery(gitkit_user.user_id)
				camid = request.path.split("/")[3]
				self.temp_location = self.factory.temp_path.child(camid)
				if any(camid in x for x in mycams):
					return None
				else:
					self.sendClose(1000,"Not authorised")
			else:
				self.sendClose(1000,"Not authorised")
		else:
			self.sendClose(1000,"Not authorised")

	def onOpen(self):
		self.factory.register(self)

	def deleteSegments(self):
		f = self.temp_location.globChildren("segment*")
		for segments in f:
			segments.remove()
		
	def deletePlaylist(self):
		f = self.temp_location.child("playlist.m3u8")
		if f.exists() and f.isfile():
			f.remove()

	def onMessage(self,payload,isBinary):
		self.factory.sendCommand(payload,isBinary,self)
			
	def onClose(self, wasClean, code, reason):
		self.factory.sendCommand("pause",False,self)
		self.deletePlaylist()
		self.deleteSegments()
		self.factory.unregister(self)
		
	def connectionLost(self,reason):
		#self.factory.sendCommand("pause",False,self)
		self.deletePlaylist()
		self.deleteSegments()
		WebSocketServerProtocol.connectionLost(self,reason)
		self.factory.unregister(self)
		
		
class PSProto(WebSocketServerProtocol):
	
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
					self.temp_location = self.factory.temp_path.child(cambot['id'])
					if not self.temp_location.exists():
						self.temp_location.makedirs()
					
					f = self.temp_location.child(u'index.html')
					g = FilePath("/home/chetan/pscore/templates/live_hls.html").asTextMode()
					content = g.getContent()
					new = content.replace("++camid++",cambot['id'])
					f.setContent(new)
					return None
				else:
					self.sendClose(1000,"Not authorised")
			else:
				self.sendClose(1000,"Not authorised")
		else:
			self.sendClose(1000,"Not authorised")
	
	def onOpen(self):
		self.factory.register(self)

	def startWrite(self,filename,content):
		d = defer.Deferred()
		d.callback(self.write_file(filename,content))
		return d
			
	def write_file(self,filename,content):
		f = self.temp_location.child(filename).asBytesMode()
		f.setContent(content)
		return True

	def deleteOld(self,filename):
		count = re.findall(r'\d+',filename)
		count = int(count[0])
		if count >= 10:
			delete_file = 'segment%05d.ts' % (count - 10)
			f = self.temp_location.child(delete_file)
			if f.exists() and f.isfile():
				f.remove()
	
	def deletePlaylist(self):
		f = self.temp_location.child("playlist.m3u8")
		if f.exists() and f.isfile():
			f.remove()
	
	def deleteIndex(self):
		f = self.temp_location.child("index.html")
		if f.exists() and f.isfile():
			f.remove()
	
	def onMessage(self,payload,isBinary):
		if not isBinary:
			self.filename = payload.decode('utf-8')
			if 'segment' in self.filename:
				d = defer.Deferred()
				d.callback(self.deleteOld(self.filename))
		else:
			content= payload
			d = self.startWrite(self.filename,content)
			
	def onClose(self, wasClean, code, reason):
		self.deletePlaylist()
		self.factory.unregister(self)
		
	def connectionLost(self,reason):
		self.deletePlaylist()
		WebSocketServerProtocol.connectionLost(self,reason)
		self.factory.unregister(self)

class PSFactory(WebSocketServerFactory):
	
	def __init__(self):
		self.clients = []
		self.temp_path = FilePath("/tmp")
		WebSocketServerFactory.__init__(self)
		
	def register(self,client):
		if client not in self.clients:
			self.clients.append(client)

	def unregister(self,client):
		if client in self.clients:
			self.clients.remove(client)
	
	def sendCommand(self,msg,isBinary,sender):
		for c in self.clients:
			if c != sender:
				c.sendMessage(msg.encode('utf-8'),isBinary)
	
class ErrorPage(Resource):
	isLeaf=True
	def render_GET(self,request):
		request.setResponseCode(401)
		noauth = PSjinja_env.get_template('not_authorized.html')
		return noauth.render().encode('utf-8')
		
	
class Stream(Resource):
	WSmap = collections.defaultdict(list)
	WScontrolmap = collections.defaultdict(list)
	
	def __init__(self):
		self.webAuthenticated = False
		Resource.__init__(self)
	
	def checkAuth(self,camid,request):
		myAES = AESCipher(key)
		gtoken = request.getCookie('gtoken')
		wsid = request.getCookie('wsid')
		try:
			user_data = json.loads(myAES.decrypt(wsid))
			gitkit_user = gitkit_instance.VerifyGitkitToken(gtoken)
			mycams = CamCheck().cbquery(gitkit_user.user_id)
			if any(camid in x for x in mycams):
				self.webAuthenticated = True
			else:
				self.webAuthenticated = False
						
		except TypeError:
			self.webAuthenticated = False

		return self.webAuthenticated
		
	def getChild(self,name,request):
		protoType = request.getHeader('upgrade')
		if not protoType:
			if name in self.WSmap:
				if self.webAuthenticated:
					return File("/tmp/"+name)
				else:
					if self.checkAuth(name,request):
						return File("/tmp/"+name)
					else:
						return ErrorPage()
			else:
				return NoResource()
		elif protoType.lower() == 'websocket':
			if len(request.postpath) == 1:
				if (request.postpath[0] == 'control') and (name in self.WScontrolmap):
					return self.WScontrolmap[name][0]
				elif request.postpath[0] == 'control':
					controlFactory = PSFactory()
					controlFactory.protocol = CommandChannel
					controlFactory.setProtocolOptions(maxConnections=2)
					controlFactory.startFactory()
					self.WScontrolmap[name].append(WebSocketResource(controlFactory))
					return self.WScontrolmap[name][0]
			elif name in self.WSmap:
				return self.WSmap[name][0]
			else:
				factory = PSFactory()
				factory.protocol = PSProto
				factory.setProtocolOptions(maxConnections=2)
				factory.startFactory()
				self.WSmap[name].append(WebSocketResource(factory))
				return self.WSmap[name][0]
