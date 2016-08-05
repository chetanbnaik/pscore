from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import threads, defer
import json

captcha_secret = "6LesARsTAAAAAO58vm5l45oxwCmZ1GGesD7eISSy"

class SubmitDetails(Resource):
	def save_details(self,request):
		print request.args
		request.setResponseCode(200)
		request.write("Hello")
		request.finish()
	
	def render_POST(self,request):
		d = defer.Deferred()
		d.callback(self.save_details(request))
		
		return NOT_DONE_YET
