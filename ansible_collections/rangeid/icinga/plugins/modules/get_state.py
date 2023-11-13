#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2023, Angelo Conforti (angeloxx@angeloxx.it)

from __future__ import absolute_import, division, print_function
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, basic_auth_header
from ansible_collections.rangeid.icinga.plugins.module_utils.time_utils import time_utils
from ansible_collections.rangeid.icinga.plugins.module_utils.minicinga2 import IcingaMiniClass, IcingaAuthenticationException, IcingaNoSuchObjectException, IcingaFailedService

__metaclass__ = type


DOCUMENTATION = """
---
module: get_state
author:
    - "Angelo Conforti (@angeloxx)"
description: Check host and service status
options:
  icinga_server:
    description:
    - The Icinga URL in the format https://<server> or
      https://<server>:<port>/<context>
    type: url
    required: true
  icinga_username:
    description:
    - The Icinga username
    type: str
    required: true
  icinga_password:
    description:
    - The Icinga user's password
    type: str
    required: true
  service:
    description:
    - regexp or name of involved services. If omitted, only the host will be checked. If all or "*", all services 
      statues will be returned
      be 
    type: str
    required: false

"""


def main():
    argument_spec = dict(
        icinga_server=dict(required=True, type="str"),
        icinga_username=dict(required=True, type="str"),
        icinga_password=dict(required=True, type="str", no_log=True),
        hostname=dict(required=False, aliases=["name"]),
        hostgroup=dict(required=False),
        service=dict(required=False, type="str"),
        services=dict(required=False, type="list", elements="str"),
    )

    result = dict(
        changed=False,
        original_message='',
        message='',
        host_maintenance=False,
        host_status=3
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False
    )

    icinga_server = module.params.get("icinga_server")
    icinga_username = module.params.get("icinga_username")
    icinga_password = module.params.get("icinga_password")
    hostname = module.params.get("hostname")
    hostgroup = module.params.get("hostgroup")
    service = module.params.get("service")
    services = module.params.get("services")

    # validate_certs = module.params.get("validate_certs")
    if hostname and hostgroup:
        module.fail_json(
            "Specify hostname/name or hostgroup")

    if service and services:
        module.fail_json(
            "Specify service or services, both are not supported")

    if services is not None:
        service = services

    module.run_command_environ_update = dict(
        LANG="C.UTF-8", LC_ALL="C.UTF-8",
        LC_MESSAGES="C.UTF-8", LC_CTYPE="C.UTF-8"
    )

    if not icinga_server.startswith("https://"):
        module.fail_json('Server must be https://<servername>')

    icinga_client = IcingaMiniClass(module=module,
                                    url=icinga_server,
                                    username=icinga_username,
                                    password=icinga_password)

    try:
        status = icinga_client.get_host_status(
            host=hostname,
            service=service,
        )

        if status["changes"] > 0:
            result['changed'] = True
        result["message"] = status["changes_details"]
        result["host_maintenance"] = status["host_maintenance"]
        result["host_status"] = status["host_status"]
        # result["services"] = status["services"]

    except IcingaAuthenticationException:
        module.fail_json(
            msg=f"Authentication error, please double check the '{icinga_username}' user")

    except IcingaNoSuchObjectException as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=f"Unable to find the host {hostname}")
        
    except IcingaFailedService as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=f"One or more services are down ({e.message})")


    module.exit_json(**result)


if __name__ == "__main__":
    main()
