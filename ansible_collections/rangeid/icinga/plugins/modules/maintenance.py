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
module: branch
author:
    - "Angelo Conforti (@angeloxx)"
description: Perform Maintenance Operations
module: branch
options:
  icinga_server:
    description:
    - The Icinga URL in the format https://<server> or
      https://<server>/<context>
    type: url
    required: true
  icinga_username:
    description:
    - The Bitbucket user with branch creation and deletion rights
    type: str
    required: true
  icinga_password:
    description:
    - The Bitbucket user's password
    type: str
    required: true
  maintenance:
    description:
    - The state of the maintenance mode
    type: choices
    choices:
    - enabled
    - disabled
    default: enabled
    required: false
  service:
    description:
    - regexp or name of involved services. If omitted, only the host will be configured
    type: str
    required: false
  message:
    description:
    - the maintenance message
    type: str
    required: false
  duration:
    description:
    - the maintenance window in 
    type: str
    required: false
"""


def main():
    argument_spec = dict(
        icinga_server=dict(required=True, type="str"),
        icinga_username=dict(required=True, type="str"),
        icinga_password=dict(required=True, type="str", no_log=True),
        maintenance=dict(default="enabled", type="str",
                         choices=['enabled', 'disabled']),
        author=dict(default="Ansible", required=False, type="str"),
        service=dict(required=False, type="str", aliases=["services"]),
        message=dict(required=False, type="str"),
        duration=dict(required=False, type="str"),
        hostname=dict(required=False, aliases=["name"]),
        hostgroup=dict(required=False),
        check_before=dict(default=False, type="bool"),
        # validate_certs=dict(default=True, type="bool"),

    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False
    )

    hostname = module.params.get("hostname")
    hostgroup = module.params.get("hostgroup")

    icinga_server = module.params.get("icinga_server")
    icinga_username = module.params.get("icinga_username")
    icinga_password = module.params.get("icinga_password")
    maintenance = module.params.get("maintenance")
    author = module.params.get("author")
    service = module.params.get("service")
    message = module.params.get("message")
    duration = module.params.get("duration")
    check_before = module.params.get("check_before")

    # validate_certs = module.params.get("validate_certs")
    if hostname and hostgroup:
        module.fail_json(
            "Specify hostname/name or hostgroup")

    module.run_command_environ_update = dict(
        LANG="C.UTF-8", LC_ALL="C.UTF-8",
        LC_MESSAGES="C.UTF-8", LC_CTYPE="C.UTF-8"
    )
    if maintenance == "enabled":
        if not duration:
            module.fail_json(
                f"Duration is needed if maintainance={maintenance}")

    if duration:
        duration_seconds = time_utils.convert_duration(duration)
        if duration_seconds == 0:
            module.fail_json(f"Can't convert duration='{duration}'")



    if not icinga_server.startswith("https://"):
        module.fail_json('Server must be https://<servername>')

    icinga_client = IcingaMiniClass(module=module,
                               url=icinga_server,
                               username=icinga_username,
                               password=icinga_password)

    try:
        if maintenance == "enabled":
            status = icinga_client.set_maintenance_mode(
                host=hostname,
                duration_seconds=duration_seconds,
                services=service,
                author=author,
                comment=message,
                check_before=check_before
            )

            if status["changes"] > 0:
                result['changed'] = True
            result["message"] = status["status"]

        if maintenance == "disabled":
            status = icinga_client.clear_maintenance_mode(
                host=hostname,
                services=service,
                check_before=check_before
            )

            if status["changes"] > 0:
                result['changed'] = True
            result["message"] = status["status"]

    except IcingaAuthenticationException:
        module.fail_json(
            msg=f"Authentication error, please double check the '{icinga_username}' user")

    except IcingaNoSuchObjectException:
        module.fail_json(
            msg=f"Unable to find the host {hostname}")
        
    except IcingaFailedService as e:
        module.fail_json(
            msg=f"One or more services are down ({e.message})")


    module.exit_json(**result)


if __name__ == "__main__":
    main()
