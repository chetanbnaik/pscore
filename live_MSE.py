from twisted.web.server import Session, NOT_DONE_YET
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

class LiveFeed(Resource):
	
	def errorPage(self,request):
		request.setResponseCode(401)
		noauth = PSjinja_env.get_template('not_authorized.html')
		request.write(noauth.render().encode('utf-8'))
		return request
	
	def makePage(self,request):
		myAES = AESCipher(key)
		gtoken = request.getCookie('gtoken')
		wsid = request.getCookie('wsid')
		
		try:
			vid = int(request.args['vid'][0])
		except (KeyError,ValueError,IndexError):
			vid = None
		
		user_data = json.loads(myAES.decrypt(wsid))
		gitkit_user = gitkit_instance.VerifyGitkitToken(gtoken)
		if gitkit_user and user_data['user_id']:
			userdetails = {'display_name': gitkit_user.name, 
				    'photo_url':gitkit_user.photo_url}
			if gitkit_user.photo_url is None:
				userdetails['photo_url']='/images/home/slider/slide1/cloud1.png'
				
			mycams = CamCheck().cbquery(gitkit_user.user_id) 
			
			if mycams == user_data['cams']:
				try:
					camid, camname = mycams[vid]
				except (TypeError,IndexError):
					camid, camname = mycams[0]
				wsurl = '/cam/view/'+camid
				live = PSjinja_env.get_template('live_MSE.html')
				request.write(live.render(user=userdetails,cam=camname,wsurl=wsurl).encode('utf-8'))
				return request
				
			else:
				self.errorPage(request)
		else:
			self.errorPage(request)
				
	
	def checkCRED(self,request):
		d = defer.Deferred()
		gtoken = request.getCookie('gtoken')
		wsid = request.getCookie('wsid')
		if gtoken and wsid:
			d.callback(self.makePage(request))
		else:
			d.callback(self.errorPage(request))
		return d
		
	def cbcheckCRED(self,request):
		request.finish()
			
	def render_GET(self,request):
		d = self.checkCRED(request)
		d.addCallback(self.cbcheckCRED)
		
		return NOT_DONE_YET
