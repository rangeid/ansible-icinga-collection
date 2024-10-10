#!/usr/bin/python

from __future__ import absolute_import, division, print_function
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, basic_auth_header
from ansible_collections.rangeid.icinga.plugins.module_utils.minicinga2 import IcingaMiniClass, \
    IcingaAuthenticationException, IcingaNoSuchObjectException, IcingaFailedService, IcingaConnectionException

__metaclass__ = type


def main():
    argument_spec = dict(
        icinga_server=dict(type='str', required=True),
        icinga_username=dict(type='str', required=True),
        icinga_password=dict(type='str', required=True, no_log=True),
        hostgroup=dict(type='str', required=True),
        validate_certs=dict(type='bool', default=True),
    )

    result = dict(
        changed=False,
        hosts=[]
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False
    )

    icinga_server = module.params.get("icinga_server")
    icinga_username = module.params.get("icinga_username")
    icinga_password = module.params.get("icinga_password")
    hostgroup = module.params.get("hostgroup")
    validate_certs = module.params.get("validate_certs")

    try:
        icinga_client = IcingaMiniClass(module=module,
                                        url=icinga_server,
                                        username=icinga_username,
                                        password=icinga_password,
                                        validate_certs=validate_certs)

        result['hosts'] = icinga_client.get_hosts_by_group(hostgroup)

    except IcingaConnectionException as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=("Unable to connect to or find the Icinga URL "
                     f"{icinga_server}")
            )
            
    except IcingaAuthenticationException:
        module.fail_json(
            msg=("Authentication error, please double check "
                 "the '{icinga_username}' user"))

    except IcingaNoSuchObjectException as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=f"Unable to find the host {hostgroup}")

    except IcingaFailedService as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=f"One or more services are down ({e.message})")

    module.exit_json(**result)


if __name__ == '__main__':
    main()