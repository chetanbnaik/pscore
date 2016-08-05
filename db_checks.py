import sys
from twisted.enterprise import adbapi
from twisted.internet import reactor

ssl={'ca':'/home/chetan/pscore/protected/server-ca.pem',
     'cert':'/home/chetan/pscore/protected/client-cert.pem',
     'key':'/home/chetan/pscore/protected/client-key.pem'}
     
pool = adbapi.ConnectionPool('MySQLdb',db='userinfo',host='173.194.226.77',
      user='ps',passwd='packets5rvo',ssl=ssl)

query_check = "SELECT userid FROM user WHERE userid='chetan1'"
query_add = "INSERT INTO user VALUES('chetan','chetan','chetan.png','chetan@test.com','2015-08-08 16:08:43')"

def cb(res):
	try: 
		userid = res[0][0]
	except IndexError:
		userid = None
		#pool.runQuery(query_add)
		
	print userid
	pool.close()
	reactor.stop()

pool.runQuery(query_check).addCallback(cb)

reactor.run()
