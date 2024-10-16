#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2023, Angelo Conforti (angeloxx@angeloxx.it)

from __future__ import absolute_import, division, print_function
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, basic_auth_header
from ansible_collections.rangeid.icinga.plugins.module_utils.time_utils import time_utils
from ansible_collections.rangeid.icinga.plugins.module_utils.minicinga2 import IcingaMiniClass, \
    IcingaAuthenticationException, IcingaNoSuchObjectException, IcingaFailedService, IcingaConnectionException

__metaclass__ = type

DOCUMENTATION = """
---
module: maintenance
author:
- "Angelo Conforti (@angeloxx)"
description: Perform Maintenance Operations
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
    validate_certs:
        description:
        - If set to False, SSL certificates will not be validated
        type: bool
        required: false
        default: true
    hostname:
        description:
        - Icinga host object name
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
        - regexp or name of involved services. If omitted, only the host will be configured. If all or '*', all services will 
          be set in maintenance mode
        type: str
        required: false
    services:
        description:
        - list of involved services
        type: list
        required: false
    message:
        description:
        - the maintenance message
        type: str
        required: false
    duration:
        description:
        - the maintenance window in dhms format, eg. 1d, 30m 40s, 1h 30m
        type: str
        required: false
    check_before:
        description:
        - all about checking the services before operations
        suboptions:
            enabled:
                description:
                - check before set or unset maintenance
                type: bool
                default: false
                required: false
            stop_on_failed_service:
                description:
                - if check_before is enabled, do not perform changes if one or more checks fails
                type: bool
                default: false
                required: false
            retries:
                description:
                - retry checks on failure
                type: int
                default: 0
                required: false
            timeout:
                description:
                - check timeout
                type: int
                default: 10
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
        service=dict(required=False, type="str"),
        services=dict(required=False, type="list", elements="str"),
        message=dict(required=False, type="str"),
        duration=dict(required=False, type="str"),
        hostname=dict(required=False, aliases=["name"]),
        validate_certs=dict(default=True, type="bool"),
        # hostgroup=dict(required=False),
        check_before=dict(required=False, type="dict", options=dict(
            enabled=dict(required=False, default=False, type="bool"),
            stop_on_failed_service=dict(required=False, default=False, type="bool"),
            retries=dict(required=False, default=0, type="int"),
            timeout=dict(required=False, default=10, type="int"),
        ))

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
    # hostgroup = module.params.get("hostgroup")

    icinga_server = module.params.get("icinga_server")
    icinga_username = module.params.get("icinga_username")
    icinga_password = module.params.get("icinga_password")
    validate_certs = module.params.get("validate_certs")
    maintenance = module.params.get("maintenance")
    author = module.params.get("author")
    service = module.params.get("service")
    services = module.params.get("services")
    message = module.params.get("message")
    duration = module.params.get("duration")
    check_before_root = module.params.get("check_before", {})
    if check_before_root:
        check_before = check_before_root.get("enabled")
        stop_on_failed_service = check_before_root.get("stop_on_failed_service")
        check_retries = check_before_root.get("retries")
        check_timeout = check_before_root.get("timeout")
    else:
        check_before = False
        stop_on_failed_service = False
        check_retries = 0
        check_timeout = 10

    # validate_certs = module.params.get("validate_certs")
    # if hostname and hostgroup:
    #     module.fail_json(
    #         "Specify hostname/name or hostgroup")
        
    if service and services:
        module.fail_json(
            "Specify service or services, both are not supported")

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
                                    password=icinga_password,
                                    validate_certs=validate_certs)

    if services is not None:
        service = services
    try:
        params = {
            'host': hostname,
            'duration_seconds': duration_seconds,
            'services': service,
            'author': author,
            'comment': message,
            'check_before': check_before,
            'stop_on_failed_service': stop_on_failed_service,
            'check_retries': check_retries
        }

        if maintenance == "enabled":
            status = icinga_client.set_maintenance_mode(**params)

            if status["changes"] > 0:
                result['changed'] = True
            result["message"] = status["changes_details"]
            result["services"] = status["services"]

        if maintenance == "disabled":
            # Currently services are not supported, all services will be disabled
            if service is not None:
                module.fail_json('The module currently doesn\'t support services disabling maintenance')

            status = icinga_client.clear_maintenance_mode(
                host=hostname,
                services=service,
                check_before=check_before,
                check_timeout=check_timeout,
                check_retries=check_retries
            )

            if status["changes"] > 0:
                result['changed'] = True
            result["message"] = status["changes_details"]
            result["services"] = status["services"]


    except IcingaConnectionException as e:
        if e.customMessage:
            module.fail_json(msg=e.message)
        else:
            module.fail_json(
                msg=f"Unable to connect to or find the Icinga URL {icinga_server}")
            
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
