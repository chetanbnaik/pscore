import googledatastore as datastore
import time

datastore.set_options(dataset='packetservo')

#req = datastore.RunQueryRequest()
#gql_query = req.gql_query

#gql_query.query_string = 'SELECT * FROM PSUsers'
#resp = datastore.run_query(req)

#results = [entity_result.entity for entity_result in resp.batch.entity_result]
#for prop in results[0].property:
	#print prop.name
	#print prop.value

#req = datastore.BeginTransactionRequest()
#resp = datastore.begin_transaction(req)
#tx = resp.transaction
		
#req = datastore.LookupRequest()
#key = datastore.Key()
#path = key.path_element.add()
#path.kind = 'PSCams'
#path.name = 'mushak0001'

#req.key.extend([key])

#req.read_options.transaction = tx

#resp = datastore.lookup(req)
#req = datastore.CommitRequest()
#req.transaction = tx

#pscam = resp.found[0].entity
#print pscam.property[0].value.string_value
#print pscam.property[1].value.string_value
#print pscam.property[2].value.string_value
#print pscam.property[3].value.string_value

##print resp
#if resp.found:
	#user = resp.found[0].entity
	
	#last_login_property = datastore.Property()
	#last_login_property.name = 'last_login'
	
	#for prop in user.property:
		#print prop.name
		#if prop.name == 'last_login':
			#prop.value.timestamp_microseconds_value = long(time.time() * 1e6)
			#print 'last login updated'
					
	#req.mutation.update.extend([user])
	#resp = datastore.commit(req)
	#print resp
	

req = datastore.CommitRequest()
req.mode = datastore.CommitRequest.NON_TRANSACTIONAL

cams = req.mutation.insert.add()

path = cams.key.path_element.add()
path.kind = 'PSCams'
path.name = 'mushak0001'

camid_property = cams.property.add()
camid_property.name = 'camid'
camid_property.value.string_value = 'mushak0001'

name_property = cams.property.add()
name_property.name = 'name'
name_property.value.string_value = 'mushak'

master_property = cams.property.add()
master_property.name = 'master'
master_property.value.string_value = '03086347034341246126'

password_property = cams.property.add()
password_property.name = 'password'
password_property.value.string_value = '0253fcafdd931e2e2ae915499ed77c1c'

resp = datastore.commit(req)
print resp
