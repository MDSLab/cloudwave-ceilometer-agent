# CloudWave Ceilometer Agent 
Openstack Ceilometer Agent for the EU project CloudWave.

During Y3, UNIME replaced the CloudWave Ceilometer pollster (cw-pollster) used since Y1 with a new Ceilometer Polling Agent, named CloudWave Ceilometer Agent (cw-agent). This new agent, installed in each Openstack compute node, that coexists with the standard Ceilometer Agent, collects all the CloudWave metrics sent by CW applications and by CW Probe from inside the virtual machines and redirects them to the Openstack Ceilometer Collector.
In particular cw-agent launches an AMQP broker whose queues are filled with messages coming from the CW Probes and in realtime empties the queues and sends messages to the Openstack Ceilometer Collector.


CloudWave Ceilometer Agent (cw-agent) has been tested to work on:

* Openstack Liberty
* CentOS 7.2 OS


##Installation guide


