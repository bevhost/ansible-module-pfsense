# ansible-module-pfsense
## Ansible Plugin Module Library For Managing pfSense Firewalls

I wrote these modules because I had a lot of firewalls to deploy in a cookie cutter fashion.
To reduce errors I wanted the firewalls to be configured by script.
I use ansible a lot so that was prefect for me, but I could not find any existing modules that could do the job.

I have written just the modules I needed to get the job done for me, 
however extending these and adding more should be fairly straight-forward.

## Compatability

At the time of writing, I was using
 - Ansible 2.7 on CentOS 7
 - pfSense 2.4.4

## pfSense Setup

Since Ansible uses ssh, you must configure at least one interface on the firewall manually and turn on ssh.
The default firewall rules already permit access into the lan interface so that one is recommended.

pfSense runs on top of the FreeBSD operating system, which has python installed in a different place to other OS.
You can create a symlink to the usual location like this from your ansible control host
```
ansible -m raw -a "/bin/ln -s /usr/local/bin/python2.7 /usr/bin/python" -k -u root myhostgrp1
```
Alternatively, you could use an inventory variable
```
[fpsense:vars]
ansible_python_interpreter=/usr/local/bin/python2.7
```

## Modules

The modules completed so far
 - Basic system configuration, DNS, timezone, NTP, snmp, etc
 - Interfaces
 - Aliases
 - Filter Rules
 - Auth Servers
 - Certificates
 - Groups
 - Password & SSH Keys
 - Virtual IPs
 - High Availability Sync
 - FRR RAW with BGP
 - Apply Settings

## Design Goals

One of my design goals was that wherever possible, you should be able to configure a firewall manually,
in the normal way with the WEB GUI, then export the configuration to an XML file, and convert it to YAML.
This .yml file will now be split into the various pieces we need, e.g. aliases, rules, config etc

When I dump and XML file, the first thing I do is to remove all the `<![CDATA[` and `]]>`.

## How it works

These python modules communicate with the pfSense configuration by using the PHP Shell.
The basic structure is:-
 - have PHP Shell dump the existing config section in JSON format for python to use
 - compare the config on the firewall to the configuration parameters supplied
 - work out what changes need to be made, adds, edit, delete etc
 - if in check_mode return the result without perforing any updates
 - otherwise continue on and write the new configuration

## Data Types

There are two main types of data stored in the pfSense configuration.

### Static single data elements

These can be configured using the pfsense_config module and include any kind of configuration item which there is only one of,
or one list of such as name servers, ntp servers, timezone, nat mode,.

### Multiple data elements

Many parts of the confuration consist of many items per data type, such as Aliases, Rules, Certificates.
To enable ansible to operate in an idempotent way, there needs to be a way of indexing these elements.
e.g. It is very important that when the script run, it does not keep adding a new element that already exists.

| Module Name          | Index   | Description / Content
| -------------------- | ------- | ------------------------------------- 
| pfsense_alias        | name    | Firewall Alias Name
| pfsense_authserver   | refid   | Reference ID
| pfsense_cert         | refid   | uniqid or I have used sha1 hash of the cert
| pfsense_filter_rules | tracker | 10 digit number (e.g. unix timestamp)
| pfsense_group        | name    | group name, so renaming a group is not possible
| pfsense_interfaces   | name    | eg: wan, lan, opt1, opt2
| pfsense_nat_rule     | ?       | currently replaces ALL rules with the one new rule
| pfsense_password     | name    | username
| pfsense_virtualip    | uniqid  | if supplied, or subnet

As far as I know, thes index keys are stored in the PHP $config as strings.
I am not aware of any limitations on what they may contain or if sort order has any effect.

Clearly the nat rule module is going to need some work if people want more than one rule.




