Name            : cw-agent
Summary         : CloudWave Ceilometer Agent (cw-agent) - Y3
Version         : 2.0.0
Release 	: %{?BUILD_NUMBER}
License         : GPL
BuildArch       : x86_64
BuildRoot       : %{_tmppath}/%{name}-%{version}-root





# Use "Requires" for any dependencies, for example:
#Requires        : rabbitmq-server, openstack-utils, cw-env-conf

# Description gives information about the rpm package. This can be expanded up to multiple lines.
%description
CloudWave Ceilometer Agent for the Nova Compute node that collects the metrics from each CW VM and sends them to Ceilometer Collector. - Compliant with Openstack Liberty - Cloudwave Y3


# Prep is used to set up the environment for building the rpm package
%prep

# Used to compile and to build the source
%build

# The installation steps. 
%install
rm -rf $RPM_BUILD_ROOT
install -d -m 755 $RPM_BUILD_ROOT/usr/lib/python2.7/site-packages/ceilometer/cmd/
cp ../SOURCES/cwagent.py $RPM_BUILD_ROOT/usr/lib/python2.7/site-packages/ceilometer/cmd/.

install -d -m 755 $RPM_BUILD_ROOT/usr/bin/
cp ../SOURCES/cw-agent $RPM_BUILD_ROOT/usr/bin/.

install -d -m 755 $RPM_BUILD_ROOT/lib/systemd/system/
cp ../SOURCES/cw-agent.service $RPM_BUILD_ROOT/lib/systemd/system/.


# Post installation steps
%post

echo -e "  Configuring:"

#
# Add CloudWave Agent configuration to /etc/ceilometer/ceilometer.conf
#
cwstr="[cloudwave]"
cwvar=`cat /etc/ceilometer/ceilometer.conf | awk '{print $1}'| grep cloudwave`

if [[ $cwvar == "$cwstr" ]]; then

        echo -e "\t\t CW Agent configurations just imported!"
else	

	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave amqp_compute_ip localhost
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave amqp_compute_port 5672
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave timeout_recon 1
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave heartbeat 0
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave monitoring_interval 4
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave rabbitmq_user guest
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave rabbitmq_password guest
	openstack-config --set /etc/ceilometer/ceilometer.conf cloudwave cw_exchange CloudWave
	
	echo -e "\t\t CW Agent configurations added!"
fi


#
# Pika installation
#
status_str="pika"
status=`pip list | grep pika | awk '{print $1}'`

if [[ $status == "$status_str" ]]; then
        echo -e "\t\t Pika module already installed!"
else
	pip install pika
	echo -e "\t\t Pika module installed!"
fi


#
# RabbitMQ configuration
#
#mkdir -p /var/log/rabbitmq
#chown rabbitmq:rabbitmq /var/log/rabbitmq
#rm -rf /var/log/rabbitmq/rabbit@`hostname`.log


status_str="not-found"
status=`systemctl status cw-agent | grep Loaded: | awk '{print $2}'`

if [[ $status == "$status_str" ]]; then

	echo -e "\t\t Enabling RabbitMQ server..."
	systemctl enable rabbitmq-server.service
	systemctl start rabbitmq-server.service
	sleep 3
	rabbitmqctl change_password guest guest
	
        echo -e "\t\t RabbitMQ server enabled at boot!"
else
	echo -e "\t\t Restarting RabbitMQ server..."
	systemctl restart rabbitmq-server.service
	sleep 3
	echo -e "\t\t RabbitMQ server already configured!"
fi


#
# cw-agent.log creation 
#
touch /var/log/ceilometer/cw-agent-`hostname`.log
chown ceilometer:ceilometer /var/log/ceilometer/cw-agent-`hostname`.log
sed -i "s/cw-agent-XXX.log/cw-agent-`hostname`.log/g" /lib/systemd/system/cw-agent.service




#
# systemd init script reload: /lib/systemd/system/cw-agent.service
#
systemctl daemon-reload


#
# Enable cw-agent
#
status_str="not-found"
status=`systemctl status cw-agent | grep Loaded: | awk '{print $2}'`

if [[ $status == "$status_str" ]]; then
	systemctl enable cw-agent
	rabbitmqctl change_password guest guest
        echo -e "\t\t CW Agent enabled at boot!"
else
	echo -e "\t\t CW Agent already enabled at boot!"
fi

#
# Re/Start cw-agent
#
systemctl restart cw-agent





%postun
systemctl stop cw-agent
systemctl daemon-reload




# Contains a list of the files that are part of the package
%files
%attr(755, root, -) /usr/lib/python2.7/site-packages/ceilometer/cmd/cwagent.py
/usr/lib/python2.7/site-packages/ceilometer/cmd/cwagent.py

%attr(755, root, -) /usr/bin/cw-agent
/usr/bin/cw-agent

%attr(755, root, -) /lib/systemd/system/cw-agent.service
/lib/systemd/system/cw-agent.service


# Used to store any changes between versions
%changelog


