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
from twisted.enterprise import adbapi

class DBConnection(object):
	def __init__(self,dbname='caminfo'):
		self.ssl={'ca':'/home/chetan/pscore/protected/server-ca.pem',
			'cert':'/home/chetan/pscore/protected/client-cert.pem',
			'key':'/home/chetan/pscore/protected/client-key.pem'}
		self.dbname = dbname
		self.dbhost = '173.194.226.77'
		self.dbuser = 'ps'
		self.dbpasswd = 'packets5rvo'
		self.pool = adbapi.ConnectionPool('MySQLdb',db=self.dbname,host=self.dbhost,
					user=self.dbuser,passwd=self.dbpasswd,ssl=self.ssl)

class DBCredentialChecker(object):
	implements(checkers.ICredentialsChecker)
	
	def __init__(self,runQuery,
	             query="SELECT camid, password FROM cams WHERE camid='%s'"):
		self.runQuery = runQuery
		self.sql = query
		self.credentialInterfaces = (credentials.IUsernamePassword,credentials.IUsernameDigestHash)
	
	def requestAvatarId(self,credentials):
		dbDeferred = self.runQuery(self.sql % credentials.username)
		deferred = defer.Deferred()
		dbDeferred.addCallbacks(self._cbAuthenticate, self._ebAuthenticate,
		           callbackArgs=(credentials, deferred),
		           errbackArgs=(credentials, deferred))
		return deferred
	
	def _cbAuthenticate(self, result, credentials, deferred):
		if len(result) == 0:
			deferred.errback(credError.UnauthorizedLogin("No such user"))
		else:
			username, password = result[0]
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
			master = result[0][0]
		myAES = AESCipher(key)
		
		cambot['master'] = master
		expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()+self.maxAge))
		cambot['expiry'] = expiry
		request.addCookie('wsid',myAES.encrypt(json.dumps(cambot)),expires=expiry,path=b"/")
		request.finish()
	
	def generateCookie(self,request):
		cambot = json.loads(request.content.read())
		dbc = DBConnection(dbname='caminfo')
		df1 = dbc.pool.runQuery("SELECT master FROM cams WHERE camid='%s'" % cambot['id'])
		df1.addCallbacks(self.cbDBRes, callbackArgs=(cambot,request))
		return df1
	
	def render_POST(self,request):
		d = self.generateCookie(request)
		#d.addCallback(self.cbDBRes, callbackArgs=(cambot,request))
		
		return NOT_DONE_YET

