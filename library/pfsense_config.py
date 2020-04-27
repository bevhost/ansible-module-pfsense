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
  section: (see examples below)
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
        authmode: "My Auth Server"      
        ssl-certref: "{{ cert['public'] | hash('sha1') }}"
        protocol: https
    safe_mode: no

# for authmode see pfsense_authserver (must match name)
# for ssl-certref see pfsense_cert (must match refid)

- name: SNMP Configuration
  pfsense_config:
    snmpd:
      syslocation: "{{ business_unit }} Firewall {{ net[site].street }}"
      syscontact: "{{ contact_email }}"
      rocommunity: public
      pollport: "161"
      enable: ""
      trapenable: ""
      trapserver: 10.98.76.54
      trapstring: myrwcomstr
      bindip: all
    safe_mode: no

# safe_mode: no is require for some parameters that don't yet exist in config
# turn if off on a new firewall to find out which ones

- name: SysLog Configuration
  pfsense_config:
    syslog:
      filterdescriptions: "1"
      nentries: "50"
      remoteserver: "10.1.1.1"
      remoteserver2: ""
      remoteserver3: ""
      sourceip: ""
      ipproto: ipv4
      logall: ""
    safe_mode: no

- name: NAT Config
  pfsense_config:
    nat:
      outbound:
        mode: hybrid
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
from ansible.module_utils.pfsense import write_config, read_config, pfsense_check, validate, isstr


def run_module():

    module_args = dict(
        safe_mode=dict(default='yes', choices=['yes','no']),
        snmpd=dict(type=dict),
        syslog=dict(type=dict),
        system=dict(type=dict),
        widgets=dict(type=dict),
        hasync=dict(type=dict),
        nat=dict(type=dict),
        installedpackages=dict(type=dict),
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params

    DoNotCreate = ['rule','cert','user','group','authserver','alias','item','monitor_type','gateway_item','package'];  # Arrays of Dict
    AllowCreateKeys = False
    if params['safe_mode'] == 'no':
        AllowCreateKeys = True
    del params['safe_mode']

    configuration = ""

    pfsense_check(module)

    # Loop through all possible params
    for section in params:

        # Process provided sections 
        if type(params[section]) is dict:

            # Read existing configuration
            result[section] = read_config(module,section)
            if not type(result[section]) is dict:
                result[section] = dict()

            # Loop through provided keys in the section
            for key in params[section]:

                # Check for keys we can't handle here
                if key in DoNotCreate:
                    module.fail_json(msg='Cannot create array type, try pfsense_'+key+' module')

                # Check that key exists in config (unless we are allowing key create "safe: no")
                if (key in result[section]) or AllowCreateKeys:

                    validate(module,section+":"+key,params[section][key])
                    # String Type
                    if isstr(params[section][key]):
                        # Validate Data type provided matches existing config
                        if (key in result[section]):
                            if not isstr(result[section][key]):
                                module.fail_json(msg=section + ":" + key + " requires " + str(type(result[section][key])))
                        # Update if changed
                        if not key in result[section] or str(result[section][key]) != params[section][key]:
                            configuration += "$config['" + section + "']['" + key + "']='" + params[section][key] + "';\n"
                            result[section][key] = params[section][key]

                    # List Type
                    elif type(params[section][key]) is list:
                        # Validate Data type provided matches existing config
                        if (key in result[section]):
                            if type(result[section][key]) is not list:
                                module.fail_json(msg=section + ":" + key + " requires " + str(type(result[section][key])))
                        # Update if changed
                        if set(result[section][key]) != set(params[section][key]):
                            configuration += "$config['" + section + "']['" + key + "']=['"+"','".join(params[section][key])+"'];\n"
                            result[section][key] = params[section][key]

                    # Dict Type
                    elif type(params[section][key]) is dict:
                        # Validate Data type provided matches existing config
                        if (key in result[section]):
                            if type(result[section][key]) is not dict:
                                module.fail_json(msg=section + ":" + key + " requires " + str(type(result[section][key])))
                        # Loop thru subkeys k in dict
                        for (k,v) in params[section][key].items():
                            validate(module,section+":"+key+":"+k,v)
                            if (k in result[section][key]) or AllowCreateKeys:
                                # Type validation
                                if (k in result[section][key]):
                                    if not isstr(result[section][key][k]):
                                        module.fail_json(msg="String expected in config at "+section + ":" + key + ":" + k + " " + str(type(result[section][key][k])) + " found")
                                if type(v) is not str:
                                    module.fail_json(msg="String value expected in "+section + ":" + key + ":" + k)
                                # Update if changed
                                if not k in  result[section][key] or result[section][key][k] != params[section][key][k]:
                                    configuration += "$config['" + section + "']['" + key + "']['" + k + "'] = '" + v.replace("'","\\'") + "';\n"
                                    result[section][key][k]=v
                            else:
                                module.fail_json(msg='SubKey: '+k+' not found in '+section+":"+key+'. Cannot create new keys in safe mode')
                    else:
                        module.fail_json(msg= section + ":" + key + " has unexpected type " + str(type(params[section][key])))
                else:
                    module.fail_json(msg='Key: '+key+' not found in section: '+section+'. Cannot create new keys in safe mode')

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




