# CloudWave Ceilometer Agent 
Openstack Ceilometer Agent for the EU project CloudWave.

During Y3, UNIME replaced the CloudWave Ceilometer pollster (cw-pollster) used since Y1 with a new Ceilometer Polling Agent, named CloudWave Ceilometer Agent (cw-agent). This new agent, installed in each Openstack compute node, that coexists with the standard Ceilometer Agent, collects all the CloudWave metrics sent by CW applications and by CW Probe from inside the virtual machines and redirects them to the Openstack Ceilometer Collector.
In particular cw-agent launches an AMQP broker whose queues are filled with messages coming from the CW Probes and in realtime empties the queues and sends messages to the Openstack Ceilometer Collector.


CloudWave Ceilometer Agent (cw-agent) has been tested to work on:

* Openstack Liberty
* CentOS 7.2 OS



##Installation guide
0. Requirements:
  * Disable Epel repositories and use centos-openstack-liberty
  * Install RabbitMQ server:
    * yum install rabbitmq-server
    * systemctl start rabbitmq-server.service
    * [OPTIONAL] rabbitmqctl change_password guest guest
    * [OPTIONAL] rabbitmq-plugins enable rabbitmq_management
    * [OPTIONAL] systemctl restart rabbitmq-server.service

1. log in Openstack Compute Node (the machine where Openstack Nova Compute and Ceilometer Agent are installed)
2. log in as root: 
  * sudo su
3. Download the RPM package
  * wget https://github.com/MDSLab/cloudwave-ceilometer-agent/raw/master/packages/cw-agent-2.0.0-35.x86_64.rpm
4. Install the package:
  * rpm -Uvh cw-agent-2.0.0-35.x86_64.rpm

##Configuration guide
Edit the "cloudwave" section in /etc/ceilometer/ceilometer.conf on the Openstack Compute Node where the cw-agent was installed:
```
[cloudwave]
amqp_compute_ip = localhost
amqp_compute_port = 5672
timeout_recon = 1
heartbeat = 0
monitoring_interval = 4
rabbitmq_user = guest
rabbitmq_password = guest
cw_exchange = CloudWave
```

##Service management
* systemctl [start | stop | status | restart] cw-agent
* Log file: /var/log/ceilometer/cw-agent-[compute-hostname].log
