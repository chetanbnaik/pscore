import sys, json

from twisted.web.server import Site
from twisted.web.static import File, Data
from twisted.web.resource import Resource
from zope.interface import implementer
from twisted.python import log

import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
GObject.threads_init()
Gst.init(None)

#from twisted.internet import gireactor
#gireactor.install()

from twisted.internet import reactor

from autobahn.twisted.websocket import WebSocketServerFactory, \
     WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource

class PSProto(WebSocketServerProtocol):
	def onConnect(self,request):
		print(request.peer)
	
	def onOpen(self):
		self.factory.register(self)
		
	def onMessage(self,payload,isBinary):
		if isBinary:
			print("Length: {0}".format(len(payload)))
		else:
			print("Message: {0}".format(payload.decode('utf-8')))
		self.sendMessage(payload, isBinary)
		
	def connectionLost(self,reason):
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
			print("client {0} registered".format(client.peer))

	def unregister(self,client):
		if client in self.clients:
			self.clients.remove(client)
			print("client {0} unregistered".format(client.peer))
	
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

if __name__=='__main__':
	log.startLogging(sys.stdout)
	
	root = View()
	site = Site(root)
	
	reactor.listenTCP(8080,site)
	
	reactor.run()
