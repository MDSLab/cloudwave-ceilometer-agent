# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

#
# Author: Nicola Peditto <npeditto@unime.it> - University of Messina (UniMe) - 2014
#

import pytz
import pika
#import inspect
import json
import socket
#import threading
import multiprocessing
import os
import signal
import datetime
import time

from time import sleep
from oslo_config import cfg
from ceilometer import service
from oslo_log import log
from ceilometer import pipeline
from ceilometer.compute.pollsters import util
from ceilometer import nova_client
from ceilometer import sample
from ceilometer import pipeline as publish_pipeline
from oslo_context import context
from pika.exceptions import AMQPConnectionError



LOG = log.getLogger(__name__)


opt_group = cfg.OptGroup(name='cloudwave', title='Options for CLOUDWAVE')


cwagent_opts = [

    cfg.StrOpt('amqp_compute_ip',
               default='localhost',
               help='AMQP compute IP address'),

    cfg.StrOpt('amqp_compute_port',
               default=5672,
               help='AMQP compute PORT address'),

    cfg.StrOpt('timeout_recon',
               default=1,
               help='Timeout [sec] before reconnection to RabbitMQ local broker.'),

    cfg.StrOpt('heartbeat',
               default=4,
               help='Timeout [sec] before checking for new/old instances.'),

    cfg.StrOpt('monitoring_interval',
               default=4,
               help='Timeout [sec] before reconnection to RabbitMQ local broker.'),

    cfg.StrOpt('rabbitmq_user',
               default='guest',
               help='RabbitMQ user.'),

    cfg.StrOpt('rabbitmq_password',
               default='guest',
               help='RabbitMQ password.'),

    cfg.StrOpt('cw_exchange',
               default='CloudWave',
               help='CloudWave exchange for RabbitMQ topic.'),

]



cfg.CONF.register_group(opt_group)

cfg.CONF.register_opts(cwagent_opts, group=opt_group)



#Ceilometer sample variables
METER_name = ""
METER_volume = ""
METER_metadata = ""
METER_resource_metadata = ""
METER_unit = ""
METER_type = ""
METER_timestamp = ""
inst = ""
instance_uuid = ""

# Create a global channel variable
channel = None
instsmon = None
connection = None
refresh = False
amqp_compute_ip = None
exchange = None
timeout_recon = None
heartbeat = None
rabbitmq_user = None
rabbitmq_password = None
monitoring_interval = None


UTC_OFFSET_TIMEDELTA = datetime.datetime.now() - datetime.datetime.utcnow()

def main():

	service.prepare_service()

        print "I'm CW-AGENT!"
        
	LOG.info("###########################################################################################")
	LOG.info("\n")
	LOG.info("CW -> I'm CW-AGENT!")
	LOG.info("\n")
	LOG.info("###########################################################################################\n")

	global amqp_compute_ip
	amqp_compute_ip = cfg.CONF.cloudwave.amqp_compute_ip
	global exchange
	exchange = cfg.CONF.cloudwave.cw_exchange #"CloudWave"
	global timeout_recon
	timeout_recon = float(cfg.CONF.cloudwave.timeout_recon)
	global heartbeat
	heartbeat = int(cfg.CONF.cloudwave.heartbeat)
	global rabbitmq_user
	rabbitmq_user = cfg.CONF.cloudwave.rabbitmq_user
	global rabbitmq_password
	rabbitmq_password = cfg.CONF.cloudwave.rabbitmq_password
	global monitoring_interval
	monitoring_interval = float(cfg.CONF.cloudwave.monitoring_interval)





        #PIPELINE INIT
	LOG.info("###########################################################################################")
	LOG.info("CW -> Ceilometer's pipelines initialization....")
	LOG.info("###########################################################################################")
	global pipeline_manager
	global meter_pipe
	global metering_context
        pipeline_manager = publish_pipeline.setup_pipeline()
        meter_pipe = pipeline_manager.pipelines[0] #meter_source:meter_sink
        metering_context = context.RequestContext('admin', 'admin', is_admin=True)
	LOG.info("###########################################################################################\n")

        LOG.info("CW -> CW-AGENT PARAMETERS:")
        LOG.info('\tRabbitMQ broker: %s', amqp_compute_ip)
        LOG.info('\tRabbitMQ CloudWave Topic Exchange: %s', exchange)
        LOG.info('\tRabbitMQ user: %s', rabbitmq_user)
        LOG.info('\tRabbitMQ password: %s', rabbitmq_password)
        LOG.info('\tRabbitMQ Heartbeat time interval: %s seconds', float(heartbeat))
        LOG.info('\tInstances Monitoring time interval: %s seconds', monitoring_interval)
        LOG.info('\tReconnection to RabbitMQ broker time intenterval: %s seconds', timeout_recon)
	LOG.info('\tCeilometer pipeline: %s', meter_pipe)

	
	"""
        print "CW -> CW-AGENT PARAMETERS:"
        print '\tRabbitMQ broker: %s', amqp_compute_ip
        print '\tRabbitMQ CloudWave Topic Exchange: %s', exchange
        print '\tRabbitMQ user: %s', rabbitmq_user
        print '\tRabbitMQ password: %s', rabbitmq_password
        print '\tRabbitMQ Heartbeat time interval: %s seconds', float(heartbeat)
        print '\tInstances Monitoring time interval: %s seconds', monitoring_interval
        print '\tReconnection to RabbitMQ broker time intenterval: %s seconds', timeout_recon
	"""

	global connection	
	connection = ioloop_connect()
	
	try:
	    	# Loop so we can communicate with RabbitMQ
    		connection.ioloop.start()

	except KeyboardInterrupt:
    		# Gracefully close the connection
    		connection.close()
    		# Loop until we're fully closed, will stop on its own
    		connection.ioloop.start()


def getInstance(instance_name):
	#SEARCH AN INSTANCE ON THIS COMPUTE NODE
	try:
		instances=nova_client.Client().instance_get_all_by_host(socket.gethostname())
        	for instance in instances:
        		#LOG.info("CW -> Instance analysed: %s", instance.id)
          		if instance.id == instance_name:
                		return instance
	
	except Exception as ex:
		LOG.info('CW -> NOVA CLIENT ERROR during getting instances list:\n\t%s', ex)


def getAllInstances():
        #GOT THE INSTANCES LIST
	try:
        	return nova_client.Client().instance_get_all_by_host(socket.gethostname())
	except Exception as ex:
        	LOG.info('CW -> NOVA CLIENT ERROR during getting instances list:\n\t%s', ex)

def ioloop_connect():
	# Connect to RabbitMQ using the default parameters
	credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
	parameters = pika.ConnectionParameters(host=amqp_compute_ip, credentials=credentials, heartbeat_interval=heartbeat)
	global connection
	connection = pika.SelectConnection(parameters, on_connected)
	return connection



def on_connected(connection):
	"""Called when we are fully connected to RabbitMQ"""
	# Open a channel
    	connection.channel(on_channel_open)
    	# Add connection_closed event callback management
	connection.add_on_close_callback(on_connection_closed)


def on_channel_open(new_channel):
    	"""Called when our channel has opened"""
    	global channel
	channel = new_channel

        #GET the instances list of this compute node
	global instances
	
        instances = getAllInstances()

	channel.exchange_declare(exchange=exchange, type='topic')
		
       	for instance in instances:

		LOG.info('CW -> INSTANCE OBJ:  %s', instance)

               	instance_uuid = getattr(instance, 'id', None) #util.instance_name(instance)i

               	LOG.info('CW -> INSTANCE:  %s', instance_uuid)

       		queue = "CloudWave."+instance_uuid
       		channel.queue_declare(queue=queue, durable=False, exclusive=False, auto_delete=False, callback=on_queue_declared)

	# CREATE MONITORING INSTANCES PROCESS
        global instsmon 
        instsmon = multiprocessing.Process(target=monitoring, args=(instances,))
        instsmon.start()
        LOG.info('CW -> MONITORING INSTANCES PROCESS STATUS: %s - %s - pid: %s - exitcode: %s', instsmon, instsmon.is_alive(), instsmon.pid, instsmon.exitcode)

	LOG.info('CW -> CW-AGENT is LISTENING on the queues:')



def monitoring(lastest_instances):

	while(True):

                # GET the instances list of this compute node
                instances = getAllInstances()

		if instances == None:
			LOG.info('CW -> CW-AGENT can not communicate with Nova client or DB!')
			sleep(3)
			pass

		else:

   	        	if instances == lastest_instances :
                		LOG.debug('CW -> NO NEW INSTANCES!')
                        	pass
                	else:

                        	for instance in instances:

					instance_uuid = getattr(instance, 'id', None) #util.instance_name(instance)
				
					if instance in lastest_instances:
						#LOG.info('CW -> INSTANCE:  %s', instance_uuid)
						pass
					else:
						LOG.info("###########################################################################################")
						LOG.info("LIST OF INSTANCES CHANGED!")
                                		LOG.info('CW -> NEW INSTANCE:  %s', instance_uuid)
						LOG.info("###########################################################################################")
				
						global refresh	
						#LOG.info('CW -> REFRESH STATUS BEFORE NEW INSTANCE:  %s', refresh)
						refresh = True
						#LOG.info('CW -> REFRESH STATUS SET BY MONITORING PROCESS:  %s', refresh)

						# We are going to close the connection and reconnecting to refresh the consumers and to start to monitor the new instance
						connection.close(reply_code=200, reply_text='Normal shutdown')
						# The on_connection_closed callback will be triggered	
			
				for oldinstance in lastest_instances:

					instance_uuid = getattr(oldinstance, 'id', None) #util.instance_name(instance)				
				
					if oldinstance in instances:
						pass
					else:
						LOG.info("###########################################################################################")
						LOG.info("LIST OF INSTANCES CHANGED!")
						LOG.info('CW -> DELETED INSTANCE:  %s', instance_uuid)
						queue = "CloudWave."+instance_uuid
						try:
							channel.queue_delete(queue=queue)
						except Exception:
							pass

						LOG.info('\tdeleted QUEUE:  %s', queue)
						LOG.info("###########################################################################################")	

				lastest_instances = instances
			
			sleep(monitoring_interval)
	



def on_queue_declared(frame):
    	"""Called when RabbitMQ has told us our Queue has been declared, frame is the response from RabbitMQ"""
	queue_name = frame.method.queue
	routing_key=queue_name
	channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key, callback=on_bindok)
	
	try:
		LOG.debug('\tFRAME: %s',frame)
		queue_name = frame.method.queue
		LOG.info('\t%s queue declared!', queue_name)
		LOG.info('\t%s queue binding on %s exchange OK!', queue_name, exchange)
	except Exception as ex:
                LOG.info('CW -> GETTING FRAME FAILED:\n\t%s', ex)
	
	# Start consuming on the new queue
        channel.basic_consume(handle_delivery, queue=queue_name, no_ack=True)
	

def on_bindok(frame):
        """Invoked by pika when the Queue.Bind method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.

        :param pika.frame.Method unused_frame: The Queue.BindOk response frame

        """
        try:
                LOG.debug('\tBINDING FRAME: %s',frame)
        except Exception as ex:
                LOG.info('CW -> GETTING BINDING FRAME FAILED:\n\t%s', ex)
        


def handle_delivery(channel, method, header, body):
	"""Called when we receive a message from RabbitMQ"""
    	
	print body
	LOG.info('CW -> Meter dequeued:\n%s', body)

	try:
		# JSON MESSAGE PARSING
		j = json.loads(body)

		METER_name = j['name']
		METER_volume = j['volume']
		METER_metadata = j['additional_metadata']    #e.g.: {'geo_meter':'coord' }
		METER_unit = j['unit']
		METER_type = j['type']
		METER_timestamp = j['timestamp']
		#METER_timestamp_format = datetime.datetime.fromtimestamp(METER_timestamp/1000.0).strftime('%Y-%m-%dT%H:%M:%SZ') # Y2 - NO UTC format
		#METER_timestamp_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(METER_timestamp/1000.0)) # Y2 - UTC format
		
		#Y3 UTC TIMESTAMP CONVERSION
		METER_timestamp_utc = (datetime.datetime.fromtimestamp(METER_timestamp/1000.0) - UTC_OFFSET_TIMEDELTA).strftime('%Y-%m-%dT%H:%M:%S.%f')
		LOG.info("CW -> TIMESTAMP: %s -> %s", str(METER_timestamp), str(METER_timestamp_utc))
	
		instance_uuid = j['probe_inst']

		if j['probe_inst']:
			LOG.info("CW -> Getting instance information...")
		
			#Y2	
			#inst=getInstance(j['probe_inst'])
			#LOG.info("GET FROM getInstance: %s", inst);

			#Y3
			inst = filter(lambda x: x.id == j['probe_inst'], instances)[0]
			LOG.info("CW ----> INSTANCE got from list: %s", inst);

			METER_resource_metadata = util._get_metadata_from_object(inst)
        		METER_resource_metadata.update(METER_metadata)


        		#LOG.info("CW -> INSTANCE SELECTED: %s with UUID %s", inst, instance_uuid)
        		LOG.info('CW -> METER FROM %s : %s %s %s', instance_uuid, METER_name, METER_volume, METER_unit)	

			# CEILOMETER SAMPLE CREATION
        		new_sample = sample.Sample(
				name=METER_name,
				type=METER_type,
				unit=METER_unit,
				volume=METER_volume,
				user_id=inst.user_id,
				project_id=inst.tenant_id,
				resource_id=inst.id,
				timestamp=METER_timestamp_utc,
				resource_metadata=METER_resource_metadata,
			)


			meter_pipe.publish_data(metering_context,[new_sample])
       			LOG.info("CW -> SAMPLE PUBLISHED!\n")
		else:
			LOG.info("CW -> SAMPLE NO PUBLISHED: Nova client ERROR communication!\n")


	except Exception as ex:
		LOG.info("CW -> WARNING IN SAMPLE PUBLISHING: NO INSTANCE FOR THE SAMPLE!!!!!!!!!!!!")
		LOG.info("\t\tWARNING: %s", ex)




def on_connection_closed(connection, reply_code, reply_text):
        """
        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given
        """

	LOG.info('CW -> CONNECTION LOST TO RABBITMQ SERVER!')
	# Terminate the instance monitoring process 
	os.kill(instsmon.pid, signal.SIGKILL)
	sleep(0.5)
        LOG.info('CW -> MONITORING INSTANCES PROCESS STOPPED!')

	LOG.info("CW -> RECONNECTING TO RABBITMQ SERVER...")
	reconnect(connection, reply_code, reply_text)	



	try:
		# Clear the RabbitMQ channel
		global channel
        	channel = None

		global refresh
		#LOG.info('CW -> REFRESH STATUS:  %s', refresh)
		if refresh == False:	
                	LOG.info('CW -> Connection closed, reopening in %s seconds: (%s) %s', timeout_recon, reply_code, reply_text)
                	sleep(timeout_recon)
		else:
			refresh = False		

        	# This is the old connection IOLoop instance, stop its ioloop
        	connection.ioloop.stop()

        	# Create a new connection
        	connection = ioloop_connect()

        	# There is now a new connection, needs a new ioloop to run
        	connection.ioloop.start()



	except Exception as ex:
		LOG.info('CW -> RECONNECTION FAILED:\n\t%s', ex)
		LOG.info('CW -> RETRY...')
		reconnect(connection, reply_code, reply_text)




def reconnect(connection, reply_code=None, reply_text=None):
        """
        Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.
        """

        try:
                # Clear the RabbitMQ channel
                global channel
                channel = None

                global refresh
                LOG.info('CW -> REFRESH STATUS:  %s', refresh)
                if refresh == False:
                        LOG.info('CW -> Connection closed, reopening in %s seconds: (%s) %s', timeout_recon, reply_code, reply_text)
                        sleep(timeout_recon)
                else:
                        refresh = False

                # This is the old connection IOLoop instance, stop its ioloop
                connection.ioloop.stop()

                # Create a new connection
                connection = ioloop_connect()

                # There is now a new connection, needs a new ioloop to run
                connection.ioloop.start()



        except Exception as ex:
                LOG.info('CW -> RECONNECTION FAILED:\n\t%s', ex)
                LOG.info('CW -> RETRY...')
                reconnect(connection, reply_code, reply_text)
