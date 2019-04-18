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

short_description: sets new password for a user and optionally loads sshkey


version_added: "2.7"

options:
  username:
    description: existing user on pfsense server
    required: true
  password:
    description: clear text password, you may want to use var_prompt for this
    required: true
  authorizedkeys:  
    description: can contain more than one key, don't forget to base64 encode 
    required: false

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

- name: Set Password & SSH Key
  pfsense_password:
    username: admin
    password: "{{ password }}"
    authorizedkeys: "{{ lookup('file', '~/.ssh/authorized_keys' ) | b64encode }}"

'''

RETURN = '''
user:
    description: dict containing data structure for webgui users
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
import json
import platform
import os

cmd = "/usr/local/sbin/pfSsh.php"

def write_config(module,configuration,post=""):

    php = 'require("auth.inc");\n'+configuration+'\nwrite_config();\n'+post+'\nexec\nexit\n'

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
        username=dict(required=True, default=None),
        password=dict(required=True, default=None),
        authorizedkeys=dict(required=False, default='')
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False       # Password is always a change since it's supplied in clear text and saved in bcrypt
    )

    params = module.params

    configuration = ""
    system = read_config(module,'system')
    index = search(system['user'],'name',params['username'])

    if index == '':
        module.fail_json(msg='username: ' + params['username'] + ' not found' )

    base = "$config['system']['user'][" + str(index) + "]"
    for p in ['password','authorizedkeys']:
        if type(params[p]) in [str,unicode]:
            if p not in system['user'][index] or system['user'][index][p] != params[p]:
                configuration += base + "['"+p+"']='" + params[p] + "';\n"

    result['phpcode'] = configuration
    if module.check_mode:
        module.exit_json(**result)

    if configuration != '':
        configuration += "local_user_set_password($config['system']['user']["+str(index)+"], '"+params['password']+"');\n"
        write_config(module,configuration,post="local_user_set($config['system']['user']["+str(index)+"]);")
        result['changed'] = True

    system = read_config(module,'system')
    result['user'] = system['user']

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




