from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import threads, reactor, defer

from twisted.python.filepath import FilePath
from identitytoolkit import gitkitclient
import time, json

import googledatastore as datastore
datastore.set_options(dataset='packetservo')

from persona import CamCheck
from PacketAES import AESCipher

from jinja2 import Environment, FileSystemLoader
PSjinja_env = Environment(loader=FileSystemLoader('/home/chetan/pscore/templates'))

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

class Watch(Resource):
	maxAge = 86400
			
	def dispPage(self,request):
		cookie = request.getCookie('gtoken')
		if cookie:
			gitkit_user = gitkit_instance.VerifyGitkitToken(cookie)
			if gitkit_user:
				userdetails = {'display_name': gitkit_user.name, 
				               'photo_url':gitkit_user.photo_url}
				if gitkit_user.photo_url is None:
					userdetails['photo_url']='/images/home/slider/slide1/cloud1.png'
				
				mycams = CamCheck().cbquery(gitkit_user.user_id)
				if len(mycams) > 0:
					myAES = AESCipher(key)
					cookie_data = {'user_id':gitkit_user.user_id,'cams':mycams,'time':long(time.time())}
					expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()+self.maxAge))
					request.addCookie('wsid',myAES.encrypt(json.dumps(cookie_data)),expires=expiry,path=b"/")
				
				welcome = PSjinja_env.get_template('user_cam_details.html')
				request.write(welcome.render(user=userdetails,mycams=mycams).encode('utf-8'))
			else:
				request.setResponseCode(401)
				noauth = PSjinja_env.get_template('not_authorized.html')
				request.write(noauth.render().encode('utf-8'))
		else:
			request.setResponseCode(401)
			noauth = PSjinja_env.get_template('not_authorized.html')
			request.write(noauth.render().encode('utf-8'))
		
		return request
	
	def makePage(self,request):
		d = defer.Deferred()
		d.callback(self.dispPage(request))
		return d
	
	def cbmakePage(self,request):
		request.finish()
			
	def render_GET(self,request):
		d = self.makePage(request)
		d.addCallback(self.cbmakePage)
		
		return NOT_DONE_YET
