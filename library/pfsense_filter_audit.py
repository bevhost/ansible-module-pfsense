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
module: pfsense_filter_audit

short_description: Checks Firewall for rules that are present in the firewall but not present in provided list

description:
     Can be used to report on extra rules found in the firewall that may have been manually entered or edited.
     Can also be used to remove rules it finds that are not present in the ansible config.

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
- hosts: pfsense

  remote_user: root

  vars_files:
    - roles/example_firewall/vars/aliases.yml
    - roles/example_firewall/vars/rules.yml

  tasks:

    - pfsense_filter_audit:
        rules: "{{ fw_filter }}"
        enforce: yes
      register: result

    - name: Apply Settings
      pfsense_apply:
        services:
          - filter

    - debug:
        var: result

'''

RETURN = '''
audit:
    description: dict containing list of rules from firewall not in our list
trackers:
    description: list of trackers found in provided ruleset when none found in firewall config
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell when enforce is yes
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
        rules=dict(required=True,type=list),
        enforce=dict(required=False,choices=[None,'yes','no']),
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    count = 0
    audit = []
    trackers = []
    configuration = ""
    params = module.params
    enforce = params['enforce']
    rules = params['rules']
    if not type(enforce) is str:
        enforce = 'no'

    if not os.path.isfile(cmd):
        module.fail_json(msg='pfSense shell not found at '+cmd)
    if platform.system() != "FreeBSD":
        module.fail_json(msg='pfSense platform expected: FreeBSD found: '+platform.system())

    for rule in rules:
        try:
            tracker = rule['tracker']
        except:
            module.fail_json(msg='tracker not found in rule',rule=rule)
        try:
            state = rule['state']
        except:
            state = 'present'

        if state == 'present':
            trackers.append(str(rule['tracker']))

    cfg = read_config(module,'filter')

    for key,rule in enumerate(cfg['rule']):
        tracker = rule['tracker']
        if tracker not in trackers:
            audit.append(rule)
            if enforce == 'yes':
                configuration += "unset($config['filter']['rule'][" + str(key) + "]);\n"
        else:
            count += 1

    result['audit'] = audit
    result['phpcode'] = configuration

    if count == 0:
        result['trackers'] = trackers
        module.fail_json(msg='no matched rules: aborting')

    if module.check_mode:
        module.exit_json(**result)

    if configuration != '':
        write_config(module,configuration)
        result['changed'] = True

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




