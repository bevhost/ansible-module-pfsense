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
module: pfsense_filter_rules

short_description: Loads a firewall filter rule into pfSense

description:
It's expected it would normally be used with a list of rules 
exported as xml from a source firewall then converted to yaml
See list and single useage examples below

However, it could be used in singularly with a rule provided manually.

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
# example_firewall.yml playbook
  vars_files:
    - roles/example_firewall/vars/rules.yml
  tasks:
    - pfsense_filter_rules:
        state: "{{ item.state | default('present') }}"
        tracker: "{{ item.tracker }}"
        type: "{{ item.type | default('pass') }}"
        interface: "{{ item.interface | default('lan') }}"
        ipprotocol: "{{ item.ipprototcol | default('inet') }}"
        direction: "{{ item.direction | default('any') }}"
        floating: "{{ item.floating | default(omit) }}"
        statetype: "{{ item.statetype | default('keep state') }}"
        protocol: "{{ item.protocol | default(omit) }}"
        source: "{{ item.source | default(dict(any='')) }}"
        destination: "{{ item.destination | default(dict(any='')) }}"
      with_items: "{{ fw_filter }}"

# roles/example_firewall/tasks/main.yml
- pfsense_filter_rules:
    type: pass
    tracker: 1542170888
    ipprotocol: inet
    protocol: tcp
    interface: lan
    direction: any
    statetype: "keep state"
    source:
      any: ""
    destination:
      network: "(self)"
      port: 443

'''

RETURN = '''
filter_rules:
    description: dict containing current filter rules
debug:
    description: Any debug messages for unexpected input types
    type: str
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pfsense import write_config, read_config, search, pfsense_check, validate


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
        floating=dict(required=False, choices=[None, True]),
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
    updated = ""

    pfsense_check(module)

    # get config and find our rule
    cfg = read_config(module,'filter')
    index = search(cfg['rule'],'tracker',params['tracker'])

    base = "$config['filter']['rule'][" + str(index) + "]"

    if params['state'] == 'present':

        if type(params['protocol']) in [str,unicode]:
            if params['protocol']!='icmp':
                params['icmptype'] = None

        for p in ['source','destination']:
            for el in params[p]:
                if index=='' or (el not in cfg['rule'][index][p]) or (str(cfg['rule'][index][p][el]) != str(params[p][el])):
                    diff = True
                    updated += ":"+p+"."+el
            for (k,v) in params[p].iteritems():
                validate(module,p+":"+el+":"+k,v)

        for p in ['type','tracker','ipprotocol','interface','direction','statetype']:
            validate(module,p,params[p])
            configuration += "$rule['" + p + "'] = '" + params[p] + "';\n"
            if index=='' or (str(params[p]) != str(cfg['rule'][index][p])):
                diff = True
                updated += ":"+p

        for p in ['descr','log','disabled','quick','protocol','icmptype']:
            if type(params[p]) in [str,unicode]:
                validate(module,p,params[p])
                configuration += "$rule['" + p + "'] = '" + params[p] + "';\n"
                if index=='' or (p not in cfg['rule'][index]) or (str(params[p]) != str(cfg['rule'][index][p])):
                    diff = True
                    updated += ":"+p

        for p in ['floating']:
            if type(params[p]) in [bool]:
                configuration += "$rule['" + p + "'] = " + str(params[p]) + ";\n"
                if index=='' or (p not in cfg['rule'][index]):
                    diff = True
                    updated += ":"+p
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
    result['updated'] = updated

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




