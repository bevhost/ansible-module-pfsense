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
module: pfsense_interface

short_description: Loads interface configuration into pfsense

description:
    - Since I only used static IPv4 config, that's pretty much all I've tested
      Additional config fields could be added without too much trouble.
    - Also includes a 'gateway' parameter which can create a Default_GW

version_added: "2.7"


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
- name: Setup Internet(wan) Interface
  pfsense_interfaces:
    name: wan
    descr: INTERNET
    ipaddr: "192.0.2.40"
    gateway: "192.0.2.41"
    subnet: 31
'''

RETURN = '''
interfaces:
    description: dictionary of interfaces
gateways:
    description: dictionary of gateways
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
import json
import platform
import os

cmd = "/usr/local/sbin/pfSsh.php"

def write_config(module,configuration):

    php = configuration+'\nwrite_config();\nexec\nexit\n'

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

def search(elements,key,val):

    if type(elements) in [dict,list]:   
        for k,v in enumerate(elements):
            if v[key] == val:
                return k
    return ""


def run_module():

    module_args = dict(
        name=dict(required=True,choices=['wan','lan','opt1','opt2']),
        enable=dict(required=False,default=True,type=str),
        ipaddr=dict(required=False),
        ipprotocol=dict(required=False,default='inet'),
        subnet=dict(required=False),
        gateway=dict(required=False),
        gateway_name=dict(required=False,default='Default_GW'),
        gateway_weight=dict(required=False,default='1'),
        descr=dict(required=False,default='')
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params

    section = 'interfaces'
    configuration = ""

    # Make sure we're actually targeting a pfSense firewall
    if not os.path.isfile(cmd):
        module.fail_json(msg='pfSense shell not found at '+cmd)
    if platform.system() != "FreeBSD":
        module.fail_json(msg='pfSense platform expected: FreeBSD found: '+platform.system())

    name = params['name']
    cfg = read_config(module,section)

    try:
        if cfg[name]:
            pass
    except:
        module.fail_json(msg='interface ' + name + ' not found')

    interface = "$config['"+section+"']['" + name + "']"

    # Interface Params
    for key in ['ipaddr','subnet','descr']:
        if params[key]:
            if not key in cfg[name] or params[key] != cfg[name][key]:
                configuration += interface + "['"+key+"']='" + params[key] + "';\n"

    # Handle enable param
    if params['enable'] and 'enable' not in cfg[name]:
        configuration += interface + "['enable']='';\n"
    if not params['enable'] and 'enable' in cfg[name]:
        configuration += "unset(" + interface + "['enable']);\n"

    # Setup Gateway if provided, (should really be in its own pfsense_gateways module)
    section = 'gateways'
    gw_diff = False
    gw_params = {'name':'interface','gateway':'gateway','gateway_name':'name','gateway_weight':'weight'}
    if params['gateway']:
        gateways = read_config(module,section)
        gw = search(gateways['gateway_item'],'name',params['gateway_name'])
        if gw=='':
            gw_diff = True
        else:
            for p, key in gw_params.iteritems():
                if p in params:
                    if (key not in gateways['gateway_item'][gw]) or (params[p] != gateways['gateway_item'][gw][key]):
                        gw_diff = True

    if gw_diff:
        configuration += interface + "['gateway']='" + params['gateway_name'] + "';\n"
        configuration += "$config['gateways']['gateway_item'][" + gw + "]=[\n";
        configuration += "'interface'=>'" + params['name'] + "',\n"
        configuration += "'gateway'=>'" + params['gateway'] + "',\n"
        configuration += "'name'=>'" + params['gateway_name'] + "',\n"
        configuration += "'weight'=>'" + params['gateway_weight'] + "'];"

    result['phpcode'] = configuration

    if module.check_mode:
        module.exit_json(**result)

    if configuration != '':
        write_config(module,configuration)
        result['changed'] = True

    for section in ['interfaces','gateways']:
        result[section] = read_config(module,section)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




