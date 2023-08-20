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
description: Force check icinga services
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
  service:
    description:
    - regexp or name of involved services. If omitted, only the host will be configured
    type: str
    required: true
  timeout:
    description:
    - wait time after the forced check. If zero the service check will be issued without checking the real service status, if set the service will be checked during this time and the module fails if the service is failed
    type: int
    required: false
"""


def main():
    argument_spec = dict(
        icinga_server=dict(required=True, type="str"),
        icinga_username=dict(required=True, type="str"),
        icinga_password=dict(required=True, type="str", no_log=True),
        service=dict(required=True, type="str"),
        hostname=dict(required=True, aliases=["name"]),
        timeout=dict(default=0, type="int", aliases=["timeout_seconds"]),
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

    icinga_server = module.params.get("icinga_server")
    icinga_username = module.params.get("icinga_username")
    icinga_password = module.params.get("icinga_password")
    service = module.params.get("service")
    timeout = module.params.get("timeout")

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
        status = icinga_client.check_service(
            host=hostname,
            service=service,
            timeout=timeout
        )
        result = dict(
            changed=False,
            original_message='',
            message=status
        )

    except IcingaAuthenticationException:
        module.fail_json(
            msg=f"Authentication error, please double check the '{icinga_username}' user")

    except IcingaNoSuchObjectException:
        module.fail_json(
            msg=f"Unable to find the host {hostname} or service {service}")
        
    except IcingaFailedService as e:
        module.fail_json(
            msg=f"One or more services are down ({e.message})")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
