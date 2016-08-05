import gi
gi.require_version('Gst','1.0')
from gi.repository import GObject, Gst, GstVideo
GObject.threads_init()

#from twisted.internet import gireactor # for non-GUI apps
#gireactor.install()
Gst.init(None)

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.internet import reactor, threads, interfaces

from zope.interface import implementer
from autobahn.twisted.websocket import WebSocketClientProtocol, \
     WebSocketClientFactory, connectWS

import requests, json, Cookie, sys
from requests.auth import HTTPDigestAuth
from twisted.python.filepath import FilePath

import RPi.GPIO as GPIO

def shutdown():
	GPIO.cleanup()

class MotorControl(object):
	def __init__(self):
		GPIO.setmode(GPIO.BOARD)
		GPIO.setwarnings(False)
		
		self.RM_dir_pin = [8,10]
		self.RM_pwm_pin = 12
		self.RM_dir_fwd = [GPIO.LOW,GPIO.HIGH]
		self.RM_dir_rev = [GPIO.HIGH,GPIO.LOW]

		self.LM_dir_pin = [29,31]
		self.LM_pwm_pin = 33
		self.LM_dir_fwd = [GPIO.HIGH,GPIO.LOW]
		self.LM_dir_rev = [GPIO.LOW,GPIO.HIGH]

		GPIO.setup(self.LM_dir_pin,GPIO.OUT)
		GPIO.setup(self.LM_pwm_pin,GPIO.OUT)
		GPIO.setup(self.RM_dir_pin,GPIO.OUT)
		GPIO.setup(self.RM_pwm_pin,GPIO.OUT)

		self.pL = GPIO.PWM(self.LM_pwm_pin,50)
		self.pR = GPIO.PWM(self.RM_pwm_pin,50)
		self.pL.start(0)
		self.pR.start(0)
	
	def left(self):
		self.pL.ChangeDutyCycle(10)
		self.pR.ChangeDutyCycle(100)

	def right(self):
		self.pR.ChangeDutyCycle(10)
		self.pL.ChangeDutyCycle(100)
		
	def forward(self):
		GPIO.output(self.RM_dir_pin,self.RM_dir_fwd)
		GPIO.output(self.LM_dir_pin,self.LM_dir_fwd)
		self.pL.ChangeDutyCycle(100)
		self.pR.ChangeDutyCycle(100)
	
	def reverse(self):
		GPIO.output(self.RM_dir_pin,self.RM_dir_rev)
		GPIO.output(self.LM_dir_pin,self.LM_dir_rev)
		self.pL.ChangeDutyCycle(100)
		self.pR.ChangeDutyCycle(100)
		
	def stop(self):
		self.pL.ChangeDutyCycle(0)
		self.pR.ChangeDutyCycle(0)
		
	def reset(self):
		self.stop()
		GPIO.cleanup()


camid = 'mushak0001'
camname = 'Chetan Home'
tokenURL = b"http://www.packetservo.com/ps/register"
wsurl = "ws://www.packetservo.com/hls/live/"+camid


@implementer(interfaces.IPushProducer)	
class HLSProducer:
	def __init__(self,proto):
		self.proto = proto
		self.count = 0
		self.started = False
		self.paused = False
		self.buffer_pool = []
		self.make_pipeline()

	def pauseProducing(self):
		self.paused = True
		
	def resumeProducing(self):
		self.paused = False
		
		if not self.started:
			self.play_pipeline()
			print "--> resumed"
			self.started = True
		
	def send_event(self):
		self.count = self.count + 1
		pushed = self.appsink_pad.push_event(GstVideo.video_event_new_upstream_force_key_unit(Gst.CLOCK_TIME_NONE,True,self.count))
		print "key unit event sent... {0}".format(pushed)
		
	def make_pipeline(self):
		CLI = [
		'rpicamsrc bitrate=800000 rotation=180 name="rpisrc" ! ',
		'video/x-h264,width=640,height=480,framerate=30/1 ! ',
		'h264parse ! mpegtsmux name="mux" ! appsink name="sink"',
		]
		gcmd = ''.join(CLI)
		self.pipeline = Gst.parse_launch(gcmd)
		self.rpisrc = self.pipeline.get_by_name("rpisrc")
		self.rpisrc.set_property("annotation-mode",0x1 + 0x4 + 0x8)
		self.rpisrc.set_property("annotation-text","PacketServo Live: "+camname+" ")
		self.rpisrc.set_property("annotation-text-size",15)
		self.appsink = self.pipeline.get_by_name("sink")
		self.appsink_pad = self.appsink.get_static_pad("sink")
		self.appsink.set_property("emit-signals",True)
		self.appsink.connect('new-sample', self.push)
	
	def play_pipeline(self):
		self.pipeline.set_state(Gst.State.PLAYING)
		
			
	def stop_pipeline(self):
		self.pipeline.set_state(Gst.State.READY)
	
	def push(self,appsink):
		gstsample = appsink.emit('pull-sample')
		gstbuffer = gstsample.get_buffer()
		frame_data = gstbuffer.extract_dup(0,gstbuffer.get_size())

		gstcaps = gstsample.get_caps()
		gst_caps_struct = gstcaps.get_structure(0)
		gst_caps_string = gst_caps_struct.to_string()
		
		if not self.paused:
			if len(self.buffer_pool) > 0:
				gst_caps_string, frame_data = self.buffer_pool.pop(0)
				self.proto.sendMessage(gst_caps_string)
				self.proto.sendMessage(frame_data,isBinary=True)
				#print "buffer sent from pool --> {0}".format(len(frame_data))
			else:
				self.proto.sendMessage(gst_caps_string)
				self.proto.sendMessage(frame_data,isBinary=True)
				#print "buffer sent directly --> {0}".format(len(frame_data))
		else:
			self.buffer_pool.append((gst_caps_string,frame_data))
			#print "--> buffer of length {0} appended".format(len(frame_data))

		return False
	
	def stopProducing(self):
		self.buffer_pool = []
		self.stop_pipeline()
		self.started = False

class MyControlProtocol(WebSocketClientProtocol):
	
	producer = None
	control = MotorControl()
	
	def onOpen(self):
		print "Websocket control channel open"
		
	def onMessage(self,payload,isBinary):
		if not isBinary:
			command = payload.decode('utf-8')
			if command == 'play':
				print command
				self.producer.resumeProducing()
			elif command == 'pause':
				print command
				self.producer.stopProducing()
				self.control.stop()
				#self.producer.stopHLS()
			elif command == 'fwd':
				self.control.forward()
			elif command == 'back':
				self.control.reverse()
			elif command == 'stop':
				self.control.stop()
			elif command == 'left':
				self.control.left()
			elif command == 'right':
				self.control.right()
	
	def onClose(self,wasClean,code,reason):
		self.producer.stopProducing()
		self.control.stop()
		print("WebSocket control channel closed: {0}".format(reason))

		
class MyClientProtocol(WebSocketClientProtocol):
	
    producer = None

    def openControl(self):
		factoryControl = MyClientFactory(wsurl+"/control",headers=headers)
		factoryControl.protocol = MyControlProtocol
		factoryControl.protocol.producer = self.producer
		connectWS(factoryControl)
    
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
		self.producer = HLSProducer(self)
		self.registerProducer(self.producer,True)
		print("WebSocket connection open.")
		self.openControl()
        #self.producer.resumeProducing()

    def onMessage(self, payload, isBinary):
		if not isBinary:
			cmd_received = payload.decode('utf-8')
			if cmd_received == 'force_key_unit':
				self.producer.send_event()	
		
    def onClose(self, wasClean, code, reason):
		#if self.producer:
			#self.producer.stopProducing()
		print("WebSocket connection closed: {0}".format(reason))		

class MyClientFactory(WebSocketClientFactory, ReconnectingClientFactory):

    protocol = MyClientProtocol
    maxDelay = 60
		
    def clientConnectionFailed(self, connector, reason):
        print("Client connection failed .. retrying ..")
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        print("Client connection lost .. retrying ..")
        self.retry(connector)
		
def GetToken():
	user=camid
	success = False
	password='mushak'
	auth=HTTPDigestAuth(user,password)
	
	headers = {'user-agent':'PSClient'}
	payload = {'name':'mushak','id':camid}
	
	r = requests.post(tokenURL,data=json.dumps(payload),headers=headers,auth=auth)
	cookies = Cookie.SimpleCookie()
	cookies.load(r.cookies)
	if (r.status_code == 200) and ('wsid' in cookies):
		headers['cookie'] = cookies['wsid']
		success = True
	
	return headers, success
			
if __name__ == '__main__':	
	success= False
	while not success:
		headers, success = GetToken()
	
	factory = MyClientFactory(wsurl,headers=headers)
	factory.protocol = MyClientProtocol
	connectWS(factory)
	
	#factory = MyClientFactory("ws://localhost:8080/"+camid)
	reactor.addSystemEventTrigger("before", "shutdown", shutdown)
	
	reactor.run()
