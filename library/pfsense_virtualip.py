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
module: pfsense_virtualip

short_description: Creates a Virtual IP Address on an interface in pfSense

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

- name: Virtual IP Address
  pfsense_virtualip:
    mode: ipalias
    interface: lo0
    uniqid: 5b87389e210d4
    descr: "SomeService"
    type: single
    subnet_bits: 32
    subnet: "10.98.76.54"
    state: present
  check_mode: yes

'''

RETURN = '''
virtualip:
    description: dict containing data structure for all virtual ips
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pfsense import write_config, read_config, search, pfsense_check
import time


def uniqid(prefix = ''):
    return prefix + hex(int(time()))[2:10] + hex(int(time()*1000000) % 0x100000)[2:7]


def run_module():

    module_args = dict(
        state=dict(required=False,default='present',choices=['present','absent']),
        uniqid=dict(required=False),
        interface=dict(required=False,default='lo0',choices=['lo0','wan','lan','opt1','opt2']),
        mode=dict(required=False,default='ipalias',choices=['ipalias','carp','proxyarp','other']),
        subnet=dict(Required=True),
        subnet_bits=dict(required=False,default='32'),
        type=dict(required=False,default='single'),
        descr=dict(required=False,default='')
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    section = 'virtualip'
    configuration = ""
    params = module.params

    pfsense_check(module)

    cfg = read_config(module,section)

    index=''
    if type(cfg) is dict and 'vip' in cfg:
       if type(params['uniqid']) in [str,unicode]:
           index = search(cfg['vip'],'uniqid',params['uniqid'])
       else:
           params['uniqid'] = uniqid()
       if index=='':
           index = search(cfg['vip'],'subnet',params['subnet'])

    base = "$config['virtualip']['vip'][" + str(index) + "]"
    if params['state'] == 'present':
        for p in ['mode','type','uniqid','interface','descr','subnet','subnet_bits']:
            if type(params[p]) in [str,unicode]:
                if index=='':
                    configuration += "$virtualip['"+p+"']='" + params[p] + "';\n"
                elif cfg[index][p] != params[p]:
                    configuration += base + "['"+p+"']='" + params[p] + "';\n"
        if index=='':
            configuration += base + "=$virtualip;\n"
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




