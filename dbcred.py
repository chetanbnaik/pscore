import sys, re, json, time

from hashlib import md5
from twisted.python.filepath import FilePath
from PacketAES import AESCipher

from twisted.internet import threads, defer
from twisted.web.server import Session, NOT_DONE_YET

from zope.interface import implements
from twisted.cred import portal, checkers, credentials, error as credError
from twisted.web.resource import IResource, Resource, NoResource
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.guard import DigestCredentialFactory
import googledatastore as datastore
datastore.set_options(dataset='packetservo')

class Verify:
	def cbquery(self,camid,field):
		camkey = datastore.Key()
		path = camkey.path_element.add()
		path.kind = 'PSCams'
		path.name = camid
		req = datastore.LookupRequest()
		
		req.key.extend([camkey])
		resp = datastore.lookup(req)
		
		if resp.found:
			pscam = resp.found[0].entity
			password_property = datastore.Property()
			password_property.name = field
			
			for prop in pscam.property:
				if prop.name == field:
					val = prop.value.string_value
			
			result = [camid,val]
		else:
			result = [camid,field]
		
		return result
	
	def query(self,camid,field):
		d = defer.Deferred()
		d.callback(self.cbquery(camid,field))
		return d
	

class DBCredentialChecker:
	implements(checkers.ICredentialsChecker)
	credentialInterfaces = (credentials.IUsernamePassword,credentials.IUsernameDigestHash)
		
	def requestAvatarId(self,credentials):
		verify = Verify()
		dbDeferred = verify.query(credentials.username,field='password')
		deferred = defer.Deferred()
		dbDeferred.addCallbacks(self._cbAuthenticate, self._ebAuthenticate,
		           callbackArgs=(credentials, deferred),
		           errbackArgs=(credentials, deferred))
		return deferred
	
	def _cbAuthenticate(self, result, credentials, deferred):
		if len(result) == 0:
			deferred.errback(credError.UnauthorizedLogin("No such user"))
		else:
			username, password = result
			if credentials.checkHash(password):
				deferred.callback(credentials.username)
			else:
				deferred.errback(credError.UnauthorizedLogin('Password mismatch'))
	
	def _ebAuthenticate(self,message,credentials,deferred):
		deferred.errback(credError.LoginFailed(message))
 
class WSRealm(object):
	implements(portal.IRealm)
   
	def requestAvatar(self,user,mind,*interfaces):
		if IResource in interfaces:
			return(IResource,SendToken(),lambda: None)
	   
		raise NotImplementedError()

p12_file = FilePath('/home/chetan/pscore/protected/PacketServo-267cefd0c2d6.p12')
f = p12_file.open('r')
key = f.read()
f.close()
	
class SendToken(Resource):
	isLeaf = True
	maxAge = 86400
	
	def cbDBRes(self,result,cambot,request):
		if len(result) == 0:
			master = None
		else:
			camid, master = result
		myAES = AESCipher(key)
		
		cambot['master'] = master
		expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()+self.maxAge))
		cambot['expiry'] = expiry
		request.addCookie('wsid',myAES.encrypt(json.dumps(cambot)),expires=expiry,path=b"/")
		request.finish()
	
	def generateCookie(self,request):
		cambot = json.loads(request.content.read())
		verify = Verify()
		ds1 = verify.query(cambot['id'],field='master')
		ds1.addCallbacks(self.cbDBRes, callbackArgs=(cambot,request))
		return ds1
	
	def render_POST(self,request):
		d = self.generateCookie(request)
		#d.addCallback(self.cbDBRes, callbackArgs=(cambot,request))
		
		return NOT_DONE_YET

if __name__ == '__main__':
	from twisted.python import log 
	from twisted.web.static import File
	from twisted.web.server import Site
	from twisted.internet import reactor
	
	log.startLogging(sys.stdout)
	
	checker = DBCredentialChecker()
	          
	realm = WSRealm()
	p = portal.Portal(realm, [checker])
	credentialFactory = DigestCredentialFactory("md5","PacketServo")
	protected_resource = HTTPAuthSessionWrapper(p,[credentialFactory])
	
	root = File(".")
	root.putChild("ws",protected_resource)
	site = Site(root)
	reactor.listenTCP(8888, site)
	reactor.run()
