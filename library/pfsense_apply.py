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
module: pfsense_apply

short_description: Creates a usergroup

description:

version_added: "2.7"

options:
  option:
    services:
    required: true
  value: 
    description: list if services to reconfigure 
e.g.
        all
 or some of these
        interfaces
        hostname
        hosts
        resolv
        timezone
        ntp
        reload_dns
        snmp
        filter
        hasync
        dnsmasq
        unbound
        restart_webgui
        frr
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
- name: Apply Firewall Filter Configuration
  pfsense_apply:
    services:
      - filter

- name: Bulk configure the whole box, based on new config
  pfsense_apply:
    services:
      - all

'''

RETURN = '''
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pfsense import write_config, read_config, pfsense_check
import os


def run_module():

    module_args = dict(
        services=dict(required=True, default=None),
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params
    services = params['services']

    configuration = ""

    pfsense_check(module)

    cfg = read_config(module);

    if 'all' in services:
        DoAll = True
    else:
        DoAll = False

    if 'interfaces' in services or DoAll:
        configuration += "interfaces_configure();\n"
   
    if 'hostname' in services or DoAll:
        configuration += "system_hostname_configure();\n"

    if 'hosts' in services or DoAll:
        configuration += "system_hosts_generate();\n"
   
    if 'resolv' in services or DoAll:
        configuration += "system_resolvconf_generate();\n"
   
    if 'timezone' in services or DoAll:
        configuration += "system_timezone_configure();\n"
   
    if 'ntp' in services or DoAll:
        configuration += "system_ntp_configure();\n"
   
    if 'reload_dns' in services or DoAll:
        configuration += "send_event('service reload dns');\n"
   
    if 'snmp' in services or DoAll:
        configuration += "services_snmpd_configure();\n"
    
    if 'filter' in services or DoAll:
        configuration += "require_once('filter.inc');filter_configure();clear_subsystem_dirty('filter');\n"

    if 'hasync' in services or DoAll:
        configuration += "interfaces_sync_setup();\n"

    if 'dnsmasq' in services or DoAll:
        try: 
            if cfg['dnsmasq']['enable']:
                configuration += "services_dnsmasq_configure();\n" 
        except:
            pass

    if 'unbound' in services or DoAll:
        try: 
            if cfg['unbound']['enable']:
                configuration += "services_unbound_configure();\n" 
        except:
            pass
   
    if 'restart_webgui' in services or DoAll:
        configuration += "system_webgui_start();\n"

  #  if '' in services or DoAll:
  #      configuration += 
   
    if 'frr' in services or DoAll:
        if os.path.isfile('/usr/local/pkg/frr.inc'):   # Check frr installed.
            configuration += "include('/usr/local/pkg/frr.inc');frr_generate_config();\n"

    result['phpcode'] = configuration

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




