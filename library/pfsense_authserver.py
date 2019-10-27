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
module: pfsense_authserver

short_description: Creates an authentication server

description:
  - Creates a definition for a RADIUS or LDAP authentication server for pfSense.

version_added: "2.7"

options:
  refid: 
    description: Reference ID as a key to this record, used later for edits & delete
    required: true
  type: 
    description: Server Type
    choices: ldap or radius
    required: true
  name:
    description: Used to identify this server in the GUI
    required: true
  host:
    description: IP address or DNS Name of the external server
    required: true
  ldap_*:
    description: LDAP Parameters
    required: when type above is ldap
  radius_*:
    description: RADIUS Parameters
    required: when type above is radius

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
   - name: LDAP Auth Server Config
     pfsense_authserver:
       refid: db34caf67ef128
       type: ldap
       name: "My Auth Server"
       host: "ldap.acmecorp.local"
       ldap_port: 389
       ldap_urltype: "TCP - Standard"
       ldap_protver: 3
       ldap_scope: subtree
       ldap_basedn: "dc=auth,dc=acmecorp,dc=com"
       ldap_authcn: "CN=Users,DC=auth,DC=acmecorp,DC=com"
       ldap_extended_enabled: ""
       ldap_extended_query: "memberOf=cn=MyTeam"
       ldap_attr_user: samAccountName
       ldap_attr_group: cn
       ldap_attr_member: memberOf
       ldap_attr_groupobj: group
       ldap_timeout: 25
       ldap_binddn: "cn=bind user,cn=Users,dc=auth,dc=acmecorp,dc=com"
       ldap_bindpw: jhys9ok3kgst1klq6lmls8

'''

RETURN = '''
authserver:
    description: dict containing data structure for all auth servers
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pfsense import write_config, read_config, search, pfsense_check, validate


def run_module():

    module_args = dict(
        state=dict(required=False, default='present', choices=['present', 'absent']),

        refid=dict(required=True),  # 10 digit (e.g. timestamp)
        name=dict(required=True),
        host=dict(required=True),

        type=dict(required=False, default='ldap', choices=['ldap','radius']),

        radius_protocol=dict(required=False, default='MS-CHAPv2', choices=['PAP,','MD5-CHAP','MS-CHAPv1','MS-CHAPv2']),
        radius_nasip_attribute=dict(required=False),
        radius_secret=dict(required=False,),
        radius_timeout=dict(required=False, default="10"),
        radius_auth_port=dict(required=False, default="1812"),
        radius_acct_port=dict(required=False, default="1813"),

        ldap_port=dict(required=False, default="389"),
        ldap_urltype=dict(required=False, default="TCP - Standard", choices=['TCP - Standard','TCP - STARTTLS','SSL - Encrypted']),
        ldap_protver=dict(required=False, default="3", choices=['2','3']),
        ldap_scope=dict(required=False, default="one", choices=['one','subtree']),
        ldap_basedn=dict(required=False ),
        ldap_authcn=dict(required=False ),
        ldap_extended_enabled=dict(required=False, default=""),
        ldap_extended_query=dict(required=False, default=""),
        ldap_attr_user=dict(required=False, default="samAccountName"),
        ldap_attr_group=dict(required=False, default="cn"),
        ldap_attr_member=dict(required=False, default="memberOf"),
        ldap_attr_groupobj=dict(required=False, default="group"),
        ldap_timeout=dict(required=False, default="25"),
        ldap_binddn=dict(required=False),
        ldap_bindpw=dict(required=False)
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

    pfsense_check(module)

    # get config and find our authserver
    cfg = read_config(module,'system')
    try:
        index = search(cfg['authserver'],'refid',params['refid'])
    except:
        index = ''
        configuration = "$config['system']['authserver']=[];\n"

    base = "$config['system']['authserver'][" + str(index) + "]"

    if params['state'] == 'present':

        for p in ['type','refid','name','host']:
            validate(module,p,params[p])
            if index=='':
                configuration += "$auth['" + p + "'] = '" + params[p] + "';\n"
            elif params[p] != cfg['authserver'][index][p]:
                configuration += base + "['" + p + "'] = '" + params[p] + "';\n"

        for p in params:
            if type(params[p]) is str and p.split('_')[0]==params['type']:
                validate(module,p,params[p])
                if index=='':
                    configuration += "$auth['" + p + "'] = '" + params[p] + "';\n"
                elif  params[p] != cfg['authserver'][index][p]:
                    configuration += base + "['" + p + "'] = '" + params[p] + "';\n"
        if index=='':
            configuration += base + "=$auth;\n"

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

    cfg = read_config(module,'system')
    result['authserver'] = cfg['authserver']

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




