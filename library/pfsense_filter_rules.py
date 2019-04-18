#!/usr/bin/python
# vim: set expandtab:

# Copyright: (c) 2018, David Beveridge <dave@bevhost.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: pfsense_config

short_description: Loads arbitrarty config items into the pfsense configuration

description:
  - Loads specified configuration values into the pfSense $config
    safe_mode (default) prevents the creation of new keys that do not already exist in the config.
    If safe mode is turned off, new keys can be created, if done incorrectly, could produce strange results.
    To determine what can be loaded, save a prefconfigured pfSense Firewall confuration xml file and convert it to yaml.
  - CAN NOT be used to unset an option such as $config['system']['dnsallowoverride']);

version_added: "2.7"

options:
  option:
    section:
      - Top level section to set. Could be 'system', 'snmpd', 'syslog', 'widgets', etc.
    required: true
  value:
    description:
      - string, simple list or dict values.
        Must only be 1 level deep.
        Must only be used for single items, use other modules for things that have multiple entries.
    required: true

author:
    - David Beveridge (@bevhost)

notes:
Ansible is located in an different place on BSD systems such as pfsense.
You can create a symlink to the usual location like this

ansible -m raw -a "/bin/ln -s /usr/local/bin/python2.7 /usr/bin/python" -k -u root mybsdhost1

Alternatively, you could use an inventory variable

[fpsense:vars]
ansible_python_interpreter=/usr/local/bin/python2.7

'''

EXAMPLES = '''
- name: System Configuration
  pfsense_config:
    system:
      hostname: "{{ inventory_hostname }}"
      domain: "{{domain}}"
      timezone: Australia/Sydney
      timeservers: au.pool.ntp.org
      dnsserver:
        - 1.1.1.1
        - 8.8.8.8
      dnslocalhost: ""
      disablechecksumoffloading: ""
      webgui:
        logincss: "bf7703"
        loginshowhost: ""
        webguihostnamemenu: "hostonly"
        authmode: "Central Auth"
        ssl-certref: "{{ cert['public'] | hash('sha1') }}"
        protocol: https

- name: SNMP Configuration
  pfsense_config:
    snmpd:
      syslocation: "{{ business_unit }} Firewall {{ net[site].street }}"
      syscontact: "{{ contact_email }}"
      rocommunity: public
      pollport: 161
      enable: ""
      trapenable: ""
      trapserver: 10.98.76.54
      trapstring: myrwcomstr
      bindip: all

- name: SysLog Configuration
  pfsense_config:
    syslog:
      filterdescriptions: 1
      nentries: 50
      remoteserver: "10.1.1.1"
      remoteserver2: ""
      remoteserver3: ""
      sourceip: ""
      ipproto: ipv4
      logall: ""

- name: NAT Config
  pfsense_config:
    nat:
      outbound:
        mode: hybrid
'''

RETURN = '''
filter_rules:
    description: dict containing data structure for that section
debug:
    description: Any debug messages for unexpected input types
    type: str
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
import json
import platform
import os

cmd = "/usr/local/sbin/pfSsh.php"

def write_config(module,configuration):

    php = configuration+'\nwrite_config();\nmark_subsystem_dirty("filter");\nexec\nexit\n'

    rc, out, err = module.run_command(cmd,data=php)
    if rc != 0:
        module.fail_json(msg='error writing config',error=err, output=out)


def read_config(module,section):

    php = 'echo "\n".json_encode($config["'+section+'"])."\n";\nexec\nexit\n'

    rc, out, err = module.run_command(cmd,data=php)
    if rc != 0:
        module.fail_json(msg='error reading config',error=err, output=out)

    start = "\npfSense shell: exec\n"
    end = "\npfSense shell: exit\n"
    try:
        s = out.index(start) + len(start)
        e = out.index(end)
        return json.loads(out[s:e])
    except:
        module.fail_json(msg='error converting to JSON', json=out[s:e])


def search(module,elements,key,val):

    if type(elements) in [dict,list]:   
        for k,v in enumerate(elements):
            if v[key] == val:
                return k
    return ""


def run_module():

    module_args = dict(
        state=dict(required=False, default='present', choices=['present', 'absent']),
        tracker=dict(required=True),  # 10 digit (e.g. timestamp)
        type=dict(required=False, default='pass', choices=['pass', 'block', 'reject']),
        disabled=dict(required=False),
        quick=dict(required=False),
        interface=dict(required=False, default='lan'),
        ipprotocol=dict(required=False, default='inet', choices=['inet', 'inet6', 'inet46']),
        icmptype=dict(required=False, default='any'),
        protocol=dict(required=False, default=None, choices=['tcp', 'udp', 'tcp/udp', 'icmp', 'esp', 'ah', 'gre', 'ipv6', 'igmp', 'ospf', 'any', 'carp', 'pfsync', None]),
        direction=dict(required=False, default='any', choices=['any','in','out']),
        statetype=dict(required=False, default='keep state', choices=['keep state','sloppy state','synproxy state','none']),
        floating=dict(required=False),
        source=dict(required=False, type=dict, default=dict(any='') ),
        destination=dict(required=False, type=dict, default=dict(any='') ),
        log=dict(required=False),
        descr=dict(required=False)
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params

    configuration = ""
    diff = False

    # Make sure we're actually targeting a pfSense firewall
    if not os.path.isfile(cmd):
        module.fail_json(msg='pfSense shell not found at '+cmd)
    if platform.system() != "FreeBSD":
        module.fail_json(msg='pfSense platform expected: FreeBSD found: '+platform.system())

    # get config and find our rule
    cfg = read_config(module,'filter')
    index = search(module,cfg['rule'],'tracker',params['tracker'])

    base = "$config['filter']['rule'][" + str(index) + "]"

    if params['state'] == 'present':

        if type(params['protocol']) in [str,unicode]:
            if params['protocol']!='icmp':
                params['icmptype'] = None

        for p in ['source','destination']:
            if index=='' or cmp(params[p],cfg['rule'][index][p]):
                diff = True

        for p in ['type','tracker','ipprotocol','interface','direction','statetype']:
            configuration += "$rule['" + p + "'] = '" + params[p] + "';\n"
            if index=='' or params[p] != cfg['rule'][index][p]:
                diff = True

        for p in ['descr','log','disabled','quick','floating','protocol','icmptype']:
            if type(params[p]) in [str,unicode]:
                if index=='' or params[p] != cfg['rule'][index][p]:
                    configuration += "$rule['" + p + "'] = '" + params[p] + "';\n"
                    diff = True
        if diff:
            configuration += "$rule['source'] = [" + ', '.join("'%s'=>%r" % (key,val) for (key,val) in params['source'].iteritems()) + "];\n"
            configuration += "$rule['destination'] = [" + ', '.join("'%s'=>%r" % (key,val) for (key,val) in params['destination'].iteritems()) + "];\n"
            configuration += base + "=$rule;\n"

    elif params['state'] == 'absent':
        if index != '':
            configuration += "unset("+base+");\n"
    else:
        module.fail_json(msg='Incorrect state value, possible choices: absent, present(default)')


    result['phpcode'] = configuration

    if module.check_mode:
        module.exit_json(**result)

    if diff:
        write_config(module,configuration)
        result['changed'] = True

    cfg = read_config(module,'filter')
    result['filter_rules'] = cfg['rule']

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




