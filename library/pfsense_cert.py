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
module: pfsense_cert

short_description: Load SSL Cert & Key

description:
  - Loads SSL Certificate into the configuration. can be used for WebGui, or Load balancers and other services.

version_added: "2.7"

options:
  refid:
    description:
      - Reference ID. Key to this cert. I normally use a SHA1 hash of the cert
    required: true
  descr:
    description:
      - Description Name of the certifcate to identify it in the GUI
     required: true
  crt:
    description:
      - base64 encoded public certificate with any intermediates follwoing on in the file
    required: true
  prv:
    description:
      - base64 encoded private key 
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
  cert:
    descr: "YYYY mycert.domain.com"
    public:  "{{ lookup('file', '/etc/pki/tls/certs/mycert.bundle.crt' ) | b64encode }}"
    private: "{{ lookup('file', '/etc/pki/tls/private/mycert.key' ) | b64encode }}"

tasks:
  - name: Load SSL Certificate
    pfsense_cert:
      refid: "{{ cert['public'] | hash('sha1') }}"
      descr: "{{ cert['descr'] }}"
      crt: "{{ cert['public'] }}"
      prv: "{{ cert['private'] }}"
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
from ansible.module_utils.pfsense import write_config, read_config, search, pfsense_check, validate, isstr


def run_module():

    module_args = dict(
        state=dict(required=False, default='present', choices=['present', 'absent']),
        type=dict(required=False, default='server'),
        refid=dict(required=True),  # 13 hex digit
        crt=dict(required=True),
        prv=dict(required=True),
        descr=dict(required=True)
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    configuration = ""
    params = module.params

    pfsense_check(module)

    # get config and find our cert
    cfg = read_config(module,'cert')
    index = search(cfg,'refid',params['refid'])

    base = "$config['cert'][" + str(index) + "]"
    if params['state'] == 'present':
        for p in ['refid','descr','crt','prv']:
            if isstr(params[p]):
                validate(module,p,params[p])
                if index=='':
                    configuration += "$cert['"+p+"']='" + params[p] + "';\n"
                elif cfg[index][p] != params[p]:
                    configuration += base + "['"+p+"']='" + params[p] + "';\n"
        if index=='':
            configuration += base + "=$cert;\n"
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

    for section in params:
        if type(params[section]) is dict:
            result[section] = read_config(module,section)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




