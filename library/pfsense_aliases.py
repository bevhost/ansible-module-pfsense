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
module: pfsense_alias

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
vars:
  alias:
    descr: "YYYY myalias.domain.com"
    public:  "{{ lookup('file', '/etc/pki/tls/aliass/myalias.bundle.crt' ) | b64encode }}"
    private: "{{ lookup('file', '/etc/pki/tls/private/myalias.key' ) | b64encode }}"

tasks:
  - name: Load SSL Certificate
    pfsense_alias:
      refid: "{{ alias['public'] | hash('sha1') }}"
      descr: "{{ alias['descr'] }}"
      crt: "{{ alias['public'] }}"
      prv: "{{ alias['private'] }}"
'''

RETURN = '''
section:
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
        state=dict(required=False, default='present', choices=['present', 'absent']),
        name=dict(required=True),
        address=dict(required=False),
        descr=dict(required=False, default=''),
        type=dict(required=True, choices=['host', 'network', 'port', 'url', 'url_ports', 'urltable', 'urltable_ports']),
        detail=dict(required=False),
    )

    args = ['name','address','descr','type','detail']

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    configuration = ""
    params = module.params
    section = 'aliases'

    # Make sure we're actually targeting a pfSense firewall
    if not os.path.isfile(cmd):
        module.fail_json(msg='pfSense shell not found at '+cmd)
    if platform.system() != "FreeBSD":
        module.fail_json(msg='pfSense platform expected: FreeBSD found: '+platform.system())

    # get config and find our alias
    cfg = read_config(module,section)
    try:
        index = search(cfg['alias'],'name',params['name'])
    except:
        configuration = "if (empty($config['aliases'])) $config['aliases'] = [];\n"
        index = ''

    base = "$config['aliases']['alias'][" + str(index) + "]"
    if params['state'] == 'present':
        for p in args:
            if type(params[p]) in [str,unicode]:
                if index=='':
                    configuration += "$alias['"+p+"']='" + params[p] + "';\n"
                elif not p in cfg['alias'][index] or cfg['alias'][index][p] != params[p]:
                    configuration += base + "['"+p+"']='" + params[p] + "';\n"
        if index=='':
            configuration += base + "=$alias;\n"
    elif params['state'] == 'absent':
        if index != '':
            configuration += "unset("+base+");\n"
    else:
        module.fail_json(msg='Incorrect state value, possible choices: absent, present(default)')

    result['phpcode'] = configuration

    if module.check_mode:
        module.exit_json(**result)

    if configuration != '':
        write_config(module,configuration)
        result['changed'] = True

    result[section] = read_config(module,section)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




