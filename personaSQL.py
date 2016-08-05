from zope.interface import Interface, Attribute, implements
from twisted.python.components import registerAdapter
from twisted.web.server import Session, NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import threads, reactor

from twisted.python.filepath import FilePath
from identitytoolkit import gitkitclient
import time, json

from twisted.enterprise import adbapi

from jinja2 import Environment, FileSystemLoader
PSjinja_env = Environment(loader=FileSystemLoader('/home/chetan/pscore/templates'))

p12_file = FilePath('/home/chetan/pscore/protected/PacketServo-267cefd0c2d6.p12')
f = p12_file.open('r')
key = f.read()
f.close()

class DBStore(object):
	
	def __init__(self,gitkit_user):
		self.ssl={'ca':'/home/chetan/pscore/protected/server-ca.pem',
				 'cert':'/home/chetan/pscore/protected/client-cert.pem',
				 'key':'/home/chetan/pscore/protected/client-key.pem'}
		self.db = 'userinfo'
		self.host = '173.194.226.77'
		self.dbuser = 'ps'
		self.dbpasswd = 'packets5rvo'
		self.gitkit_user = gitkit_user
		self.pool = adbapi.ConnectionPool('MySQLdb',db=self.db,host=self.host,
					user=self.dbuser,passwd=self.dbpasswd,ssl=self.ssl)

	def storeCallback(self,res):
		try:
			userid = res[0][0]
			query_update = "UPDATE user SET last_login='{0}' WHERE userid='{1}'".format(
				time.strftime("%Y-%m-%d %T", time.gmtime(time.time())),
				userid)
			self.pool.runQuery(query_update)
		except IndexError:
			query_add = "INSERT INTO user VALUES ('{0}','{1}','{2}','{3}','{4}')".format(self.gitkit_user.user_id,
					self.gitkit_user.name, self.gitkit_user.photo_url, self.gitkit_user.email,
					time.strftime("%Y-%m-%d %T", time.gmtime(time.time())))
			self.pool.runQuery(query_add)
		self.pool.close()

	def store(self):
		query_check = "SELECT userid FROM user WHERE userid='{0}'".format(self.gitkit_user.user_id)
		return self.pool.runQuery(query_check)
	

gitkit_instance = gitkitclient.GitkitClient(
#gitkit_instance = gitkitclient.FromConfigFile(config_json)(
	client_id="912263063433-i8se3d23v29chlnocovc4umi8cuqdbmd.apps.googleusercontent.com",
	service_account_email="912263063433-mf2pq0ap6cb7rsuiot6126dn1c87c29s@developer.gserviceaccount.com",
	service_account_key=key,
	widget_url="http://www.packetservo.com/auth/login"
	)

class IUserDetails(Interface):
	online = Attribute("Online?")
	gitkituser = Attribute("GITKIT User")


class UserDetails(object):
	implements(IUserDetails)
	def __init__(self, session):
		self.online = False
		self.gitkituser = None

registerAdapter(UserDetails, Session, IUserDetails)

class Persona(Resource):
	def loginuser(self,request):
		cookie = request.getCookie('gtoken')
		if cookie:
			gitkit_user = gitkit_instance.VerifyGitkitToken(cookie)
			if gitkit_user:
				#print str(vars(gitkit_user))
				session = request.getSession()
				userdetails = IUserDetails(session)
				userdetails.online = True
				userdetails.gitkituser = gitkit_user
				dbstore = DBStore(gitkit_user)
				df1 = dbstore.store()
				df1.addCallback(dbstore.storeCallback)
		
		return request
	
	def loginuserCallback(self,request):
		request.redirect("/")
		request.finish()
	
	def render_GET(self,request):
		d = threads.deferToThread(lambda: self.loginuser(request))
		d.addCallback(self.loginuserCallback)
		
		return NOT_DONE_YET
	
	def whichuser(self,request):
		try:
			action = request.args['action'][0]
		except KeyError:
			action = None
		
		session = request.getSession()
		user_details = IUserDetails(session)
		
		if action == 'check':
			if user_details.online:
				user = user_details.gitkituser
			else:
				user = None
		
		elif action == 'logout':
			if user_details.online:
				user_details.online = False
				user_details.gitkituser = None
				expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()))
				request.addCookie("gtoken","deleted",expires=expiry,path=b"/")
				session.expire()
				user = None
			else:
				expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()))
				request.addCookie("gtoken","deleted",expires=expiry,path=b"/")
				session.expire()
				user = None
				
		else:
			user = None
			
		results = {'response':user,'request':request,'action':action}
		return results
		
	def whichuserCallback(self,results):
		request = results['request']
		response = results['response']
		request.setHeader("Content-Type", "application/json; charset=utf-8")
		
		if response is None:
			nouser = PSjinja_env.get_template('nouser.html')
			carousel = PSjinja_env.get_template('carousel.html')
			sendbody = {'user-nav':nouser.render().encode('utf-8'),
			     'welcome':carousel.render().encode('utf-8')}
			#request.write(template.render().encode('utf-8'))
			request.write(json.dumps(sendbody))			
		else:
			userdetails = {'display_name': response.name, 
				'photo_url':response.photo_url}
			template = PSjinja_env.get_template('online.html')
			sendbody = {'user-nav':template.render(user=userdetails).encode('utf-8')}
			#request.write(template.render(user=userdetails).encode('utf-8'))
			request.write(json.dumps(sendbody))	
			
		request.finish()
	
	def render_POST(self,request):
		d = threads.deferToThread(lambda: self.whichuser(request))
		d.addCallback(self.whichuserCallback)
		
		return NOT_DONE_YET
