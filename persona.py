from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import threads, reactor, defer

from twisted.python.filepath import FilePath
from identitytoolkit import gitkitclient
import time, json

import googledatastore as datastore
datastore.set_options(dataset='packetservo')

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

class CamCheck:
	def cbquery(self,master):
		req = datastore.RunQueryRequest()
		query = req.query
		query.kind.add().name = 'PSCams'
		master_filter = query.filter.property_filter
		master_filter.property.name = 'master'
		master_filter.operator = datastore.PropertyFilter.EQUAL
		master_filter.value.string_value = master
		
		resp = datastore.run_query(req)
		mycams = []
		for entity_result in resp.batch.entity_result:
			entity = entity_result.entity
			for prop in entity.property:
				if prop.name == 'camid':
					camid = prop.value.string_value
				elif prop.name == 'name':
					camname = prop.value.string_value
			mycams.append([camid, camname])
		
		return mycams
		
	def query(self,master):
		d = defer.Deferred()
		d.callback(self.cbquery(master))
		return d

class Persona(Resource):		
		
	def checkDB(self,gitkit_user):
		req = datastore.BeginTransactionRequest()
		resp = datastore.begin_transaction(req)
		tx = resp.transaction
		
		req = datastore.LookupRequest()
		key = datastore.Key()
		path = key.path_element.add()
		path.kind = 'PSUsers'
		path.name = gitkit_user.user_id
		req.key.extend([key])
		
		req.read_options.transaction = tx
		
		resp = datastore.lookup(req)
		req = datastore.CommitRequest()
		
		req.transaction = tx
		
		if resp.missing:
			user = req.mutation.insert.add()
			user.key.CopyFrom(key)
			
			userid_property = user.property.add()
			userid_property.name = 'userid'
			userid_property.value.string_value = gitkit_user.user_id
			
			display_name_property = user.property.add()
			display_name_property.name = 'display_name'
			display_name_property.value.string_value = gitkit_user.name
			
			photo_url_property = user.property.add()
			photo_url_property.name = 'photo_url'
			if gitkit_user.photo_url:
				photo_url_property.value.string_value = gitkit_user.photo_url
			else:
				photo_url_property.value.string_value = "/images/home/slider/slide1/cloud1.png"
			
			email_property = user.property.add()
			email_property.name = 'email'
			email_property.value.string_value = gitkit_user.email
			
			last_login_property = user.property.add()
			last_login_property.name = 'last_login'
			last_login_property.value.timestamp_microseconds_value = long(time.time() * 1e6)
		
		elif resp.found:
			user = resp.found[0].entity
			last_login_property = datastore.Property()
			last_login_property.name = 'last_login'
			
			for prop in user.property:
				if prop.name == 'last_login':
					prop.value.timestamp_microseconds_value = long(time.time() * 1e6)
			
			req.mutation.update.extend([user])
			
		resp = datastore.commit(req)
		
		return None
	
	def loginuser(self,request):
		cookie = request.getCookie('gtoken')
		if cookie:
			gitkit_user = gitkit_instance.VerifyGitkitToken(cookie)
			if gitkit_user:
				self.checkDB(gitkit_user)
		
		return request
	
	def loginuserCallback(self,request):
		request.redirect("/cam/watch")
		request.finish()
	
	def render_GET(self,request):
		d = threads.deferToThread(lambda: self.loginuser(request))
		d.addCallback(self.loginuserCallback)
		
		return NOT_DONE_YET
	
	def cbwhichuser(self,request):
		try:
			action = request.args['action'][0]
		except KeyError:
			action = None
		
		if action == 'check':
			cookie = request.getCookie('gtoken')
			if cookie:
				user = gitkit_instance.VerifyGitkitToken(cookie)
			else:
				user = None
				
		elif action == 'logout':
			expiry = time.strftime("%a, %d-%b-%Y %T GMT", time.gmtime(time.time()))
			request.addCookie("gtoken","deleted",expires=expiry,path="/")
			request.addCookie("wsid","deleted",expires=expiry,path="/")
			user = None
			
		else:
			user = None
		
		request.setHeader("Content-Type", "application/json; charset=utf-8")
		
		if user is None:
			nouser = PSjinja_env.get_template('nouser.html')
			carousel = PSjinja_env.get_template('carousel.html')
			sendbody = {'user-nav':nouser.render().encode('utf-8'),
			     'welcome':carousel.render().encode('utf-8')}
			request.write(json.dumps(sendbody))
		else:
			userdetails = {'display_name': user.name, 
				'photo_url':user.photo_url}
			if user.photo_url is None:
				userdetails['photo_url']='/images/home/slider/slide1/cloud1.png'
			mycams = CamCheck().cbquery(user.user_id)
			online = PSjinja_env.get_template('online.html')
			cams = PSjinja_env.get_template('online-cams.html')
			sendbody = {'user-nav':online.render(user=userdetails).encode('utf-8'),
			      'welcome':cams.render(mycams=mycams).encode('utf-8')}
			request.write(json.dumps(sendbody))	
		
		request.finish()
		
	def whichuser(self,request):
		d = defer.Deferred()
		d.callback(self.cbwhichuser(request))
		return d
	
	def render_POST(self,request):
		d = self.whichuser(request)
		
		return NOT_DONE_YET
