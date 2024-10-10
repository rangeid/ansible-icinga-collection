from ansible.module_utils.urls import fetch_url, basic_auth_header
import datetime
import time
import requests
import os
import json


class IcingaMiniClass():
    def __init__(self, module, url, username, password, validate_certs=True):
        self.url = url
        self.username = username
        self.password = password
        self.module = module
        self.last_service_status = 3
        self.validate_certs = validate_certs

        self.headers = {
            'Authorization': basic_auth_header(self.username, self.password),
            'Accept': 'application/json'
        }

        if self.url.endswith("/"):
            self.url = self.url[:-1]

    def get_last_service_status(self):
        return self.last_service_status

    # def get_services(self, host):
    #   response, info = fetch_url(module, f"{icinga_server}/v1/actions/schedule-downtime", headers=headers, method='POST',
    #                     data=json.dumps(data), timeout=30)

    def _check_all_services(self, host, timeout: int = 10, retries: int = 0, except_on_failure: bool = False):
        """Check status of all services for a host.

        Checks the status of all active services associated with the given host. 
        Waits up to the timeout for all services to be OK, retrying failed checks
        up to the specified number of retries.

        Args:
            host (str): The name of the host to check services for.
            timeout (int, optional): Timeout in seconds to wait for all checks. Default 10.
            retries (int, optional): Number of retries for failed service checks. Default 0.
            except_on_failure (bool, optional): Whether to raise an exception if any
                service check fails. Default False.

        Returns:
            dict: Dictionary containing lists of failed and successful service checks.

        Raises:
            IcingaFailedService: If any service check fails and except_on_failure is True.

        """
        _ret = dict(
            failed=[],
            success=[]
        )

        _data = {
            "type": "Host",
            "filter": f"host.name==\"{host}\"",
        }
        _response = self._send_request(
            url="/v1/objects/services",
            method="GET",
            data=_data,
        )
        for _service in _response['results']:
            if _service["attrs"]["active"] is True:
                if _service["attrs"]["last_state"] == 0:
                    pass
                else:
                    result = self.check_service(host=host,
                                                service=_service["attrs"]["name"],
                                                timeout=timeout, retries=retries, except_on_failure=except_on_failure)
                    if result == False:
                        _ret["failed"].append(_service["attrs"]["name"])
                    else:
                        _ret["success"].append(_service["attrs"]["name"])
        return _ret


    def _get_service_status(self, host: str, service: str):  
        """
        Get the status of a specific service on a host.

        This method sends a request to the Icinga API to retrieve the status of a specific service on a host.
        The status is stored in the `last_service_status` attribute and also returned by the method.

        Args:
            host (str): The name of the host where the service is running.
            service (str): The name of the service whose status is to be retrieved.

        Returns:
            int: The status of the service. The status is an integer where 0 indicates an OK state, 
                 1 indicates a WARNING state, 2 indicates a CRITICAL state, and 3 indicates an UNKNOWN state.
        """
        self.last_service_status = 3
        _data = {
            "type": "Service",
            "filter": f"host.name==\"{host}\" && service.name==\"{service}\"",
        }
        _response = self._send_request(
            url="/v1/objects/services",
            method="GET",
            data=_data,
        )
        self.last_service_status = _response['results'][0]["attrs"]["last_state"]
        return _response['results'][0]["attrs"]["last_state"]

    def _get_service_list(self, host: str, service_pattern: str = "*"):
        """
        Get list of services for a host matching a pattern.
        
        Fetches all services for the given host that match the provided glob pattern.
        Sends a request to the Icinga API to retrieve services filtered by the host 
        name and pattern. Returns a list of matching service names.
        
        Args:
            host (str): The Icinga host name
            service_pattern (str): Glob pattern to match services. Defaults to "*" to match all. 
        
        Returns:
            list: List of service names matching the pattern for the given host.
        """

        _data = {
            "type": "Service",
            "filter": f"\"{host}\"==host.name && match (pattern,service.name)",
            "filter_vars": {"pattern": service_pattern}
        }
        _response = self._send_request(
            url="/v1/objects/services",
            method="GET",
            data=_data,
        )
        _ret = []

        for _service in _response['results']:
            _ret.append(_service["attrs"]["name"])
        return _ret

    def get_host_status(self, host: str = "", service: str = None):
        """
        Get the current status of an Icinga host, including maintenance state and service states if provided.
        
        Retrieves the host object from the Icinga API to determine the current state, downtime, and acknowledgement status.
        Can also retrieve status information for specific services if provided.
        
        Args:
            host (str): The name of the Icinga host to check status for
            service (str|list): Optional name or list of service names to retrieve status for
        
        Returns:
            dict: Dictionary containing status information with the following keys:
                host_status: The current state of the host (0=Up, 1=Down, etc)
                host_maintenance: True if the host is in maintenance/downtime
                status: The worst state of all checked services (0=Ok, 1=Warning, etc)
                changes: Count of status changes detected
                changes_details: String of all status details
        """
        
        _ret = {
            "host_status": False,
            "status": 3,
            "changes": 0,
            "changes_details": ""
        }

        _results = self._send_request(
            url=f"/v1/objects/hosts/{host}?attrs=acknowledgement&attrs=downtime_depth&attrs=state",
            method="GET",
            data={}
        )

        # _results = json.loads(_response.read())
        if len(_results["results"]) == 0:
            raise IcingaNoSuchObjectException()

        _ret["host_status"] = _results["results"][0]['attrs']['state']
        _ret["host_maintenance"] = _results["results"][0]['attrs']['downtime_depth'] > 0
        _ret["changes_details"] = json.dumps(_results["results"][0]['attrs'])

        if service:
            if isinstance(service, str):
                pass
            elif isinstance(service, list):
                pass

        return _ret

    def check_service(self, host: str, service: str, timeout: int = 10, retries: int = 0, except_on_failure: bool = True):
        """
        Check the status of an Icinga service on a host. 
        
        Forces a fresh check of the service and polls the status until timeout.
        Retries checks if the service fails and retries are configured.
        Returns a message string on success, raises an exception or returns False on failure.
        
        Parameters:
          host (str): Hostname
          service (str): Service name
          timeout (int): Timeout in seconds to poll status after check
          retries (int): Number of times to retry check if service fails
          except_on_failure (bool): Raise exception if service fails after retries instead of returning bool
        
        Returns:
          str: Success message if service ok
          bool: False if service failed after retries and except_on_failure is False
          Raises IcingaFailedService exception if service fails after retries and except_on_failure is True 
        """
        _retries = 0
        while (True):
            _data = {
                "type": "Service",
                "filter": f"host.name==\"{host}\" && service.name==\"{service}\"",
            }
            _response = self._send_request(
                url="/v1/actions/reschedule-check",
                method="POST",
                data=_data,
            )

            if timeout == 0:
                # Set and forget it
                return _response["status"]

            # Start to poll service status until timeout
            for _second in range(timeout):
                _service_status = self._get_service_status(host=host,
                                                           service=service)
                if _service_status == 0:
                    return "Service is up"
                time.sleep(1)

            if _retries < retries:
                # One more time
                _retries = _retries + 1
            else:
                if except_on_failure:
                    raise IcingaFailedService(
                        f"Service {service} state is {IcingaStatus.serviceStateToString(_service_status)} after timeout of {timeout} seconds")
                else:
                    return False

    def _get_maintenance_host_mode(self, host: str = ""):
        """
        Gets the maintenance mode status of a host in Icinga2.

        Args:
            host (str): The name of the host to get the maintenance mode status of.

        Returns:
            bool: True if the host is in maintenance mode, False otherwise.
        """
        _data = {
            "type": "Host",
            "filter": f"host.name==\"{host}\"",
            "attrs": ["end_time"],
            "pretty": True
        }
        _response = self._send_request(
            url="/v1/objects/downtimes",
            method="GET",
            data=_data,
        )

        return _response["results"]

    def _get_invalid_services(self, services: list = [], check_against: list = []):
        """
        Returns a list of services that are not present in the given list of services.

        Args:
            services (list): A list of services to check against.
            check_against (list): A list of services to check for.

        Returns:
            list: A list of services that are not present in the given list of services.
        """

        _ret = []

        for _in_service in check_against:
            if not _in_service in services:
                _ret.append(_in_service)

        return _ret
    
    def get_hosts_by_group(self, 
                           hostgroup: str = ""
                           ) -> list:
        """
        Get a list of hosts in a hostgroup.

        Args:
            hostgroup (str): The name of the hostgroup to get the list of hosts for.

        Returns:
            list: A list of hosts in the hostgroup.
        """
        _ret = []

        _data = {
            "type": "Host",
            "filter": f"\"{hostgroup}\" in host.groups",
            "attrs": ["name"],
            "pretty": True
        }
        _response = self._send_request(
            url="/v1/objects/hosts",
            method="GET",
            data=_data,
        )

        for _host in _response["results"]:
            _ret.append(_host["attrs"]["name"])

        return _ret

    def clear_maintenance_mode(self, host: str,
                               services: str = "all",
                               check_before: bool = False,
                               stop_on_failed_service: bool = False,
                               check_retries: int = 1,
                               check_timeout: int = 10
                               ) -> bool:
        _ret = {
            "status": "",
            "changes": 0,
            "changes_details": [],
            "services": []
        }

        if check_before:
            _results = self._check_all_services(
                host=host, retries=check_retries, timeout=check_timeout)
            if len(_results["failed"]) > 0 and stop_on_failed_service:
                failed_services = ", ".join(_results["failed"])
                raise IcingaFailedService(
                    f"One or more services are still failed: {failed_services}")

        _downtimes = self._get_maintenance_host_mode(host=host)
        _ret['changes'] = len(_downtimes)

        if len(_downtimes) > 0:
            for _downtime in _downtimes:
                _data = {
                    "downtime": _downtime["name"],
                    "type": "Downtime",
                    # "filter": f"host.name==\"{host}\"",
                }

                _results = self._send_request(
                    url="/v1/actions/remove-downtime",
                    method='POST',
                    data=_data
                )
                _ret['status'] = " ".join(
                    [_ret['status'], _results["results"][0]['status']]).strip()

        return _ret

    def set_service_maintenance_mode(self, host: str,
                                     duration_seconds: int = 0,
                                     service: str = "all",
                                     author="Ansible",
                                     comment="Downtime",
                                     check_before: bool = False,
                                     check_retries: int = 1,
                                     check_timeout: int = 10
                                     ):

        if check_before:
            self.check_service(host=host,
                               service=service,
                               timeout=check_timeout, retries=check_retries, except_on_failure=True)

        _ret = {
            "status": "",
            "changes": 0,
            "changes_details": []
        }
        _data = {
            "type": "Service",
            "filter": f"host.name==\"{host}\" && service.name==\"{service}\"",
            "start_time": datetime.datetime.now().timestamp(),
            "end_time": (datetime.datetime.now() + datetime.timedelta(
                seconds=duration_seconds)).timestamp(),
            "comment": f"{comment}", "author": f"{author}",
            "duration": duration_seconds, "child_hosts": 0
        }

        _results = self._send_request(
            url="/v1/actions/schedule-downtime",
            method='POST',
            data=_data
        )

        # _results = json.loads(_response.read())
        if len(_results["results"]) == 0:
            raise IcingaNoSuchObjectException()

        _ret["status"] = _results["results"][0]["status"]
        return _ret

    def set_maintenance_mode(self, host: str,
                             duration_seconds: int = 0,
                             services: str = "all",
                             author: str = "Ansible",
                             comment: str = "Downtime",
                             check_before: bool = False,
                             stop_on_failed_service: bool = False,
                             check_retries: int = 1,
                             check_timeout: int = 10):
        """
        Sets a host or service into maintenance mode in Icinga2.

        Args:
            host (str): The name of the host to set into maintenance mode.
            duration_seconds (int, optional): The duration of the maintenance window in seconds. Defaults to 0 (indefinite).
            services (str, optional): The name of the service(s) to set into maintenance mode. Defaults to "all".
            author (str, optional): The name of the user who initiated the maintenance window. Defaults to "Ansible".
            comment (str, optional): A comment to describe the reason for the maintenance window. Defaults to "Downtime".
            check_before (bool, optional): Whether to check the status of all services before setting them into maintenance mode. Defaults to False.
            stop_on_failed_service (bool, optional): Whether to stop setting services into maintenance mode if any of them fail the check. Defaults to False.
            check_retries (int, optional): The number of times to retry the service check before giving up. Defaults to 1.
            check_timeout (int, optional): The timeout for the service check in seconds. Defaults to 10.

        Raises:
            IcingaNoSuchObjectException: If the specified host or service does not exist in Icinga2.
            IcingaFailedService: If one or more services are still failed and stop_on_failed_service is True.

        Returns:
            dict: A dictionary containing the status of the operation, the number of changes made, and any additional details.
        """

        if check_before:
            _results = self._check_all_services(
                host=host, retries=check_retries, timeout=check_timeout)
            if len(_results["failed"]) > 0 and stop_on_failed_service:
                failed_services = ", ".join(_results["failed"])
                raise IcingaFailedService(
                    f"One or more services are still failed: {failed_services}")

        _ret = {
            "status": "",
            "changes": 0,
            "changes_details": [],
            "statuses": [],
            "services": []
        }
        _data = {
            "type": "Host",
            "filter": f"host.name==\"{host}\"",
            "all_services": "1" if (services == "all" or services == "*") else "0",
            "start_time": datetime.datetime.now().timestamp(),
            "end_time": (datetime.datetime.now() + datetime.timedelta(
                seconds=duration_seconds)).timestamp(),
            "comment": f"{comment}", "author": f"{author}",
            "duration": duration_seconds, "child_hosts": 0
        }

        # If service list were specified, check if all services exists
        if _data["all_services"] != "1":
            if isinstance(services, list):
                _services = self._get_service_list(host=host)
            else:
                _services = self._get_service_list(
                    host=host, service_pattern=services)

            if isinstance(services, list):
                _invalid_services = self._get_invalid_services(
                    services=_services, check_against=services)
                if len(_invalid_services) > 0:
                    _invalid_services_list = ", ".join(_invalid_services)
                    _valid_services_list = ", ".join(_services)
                    raise IcingaNoSuchObjectException(
                        message=f"Unable to find one or more services: {_invalid_services_list}, valid services are {_valid_services_list}")

        _results = self._send_request(
            url="/v1/actions/schedule-downtime",
            method='POST',
            data=_data
        )
        # _results = json.loads(_response.read())
        if len(_results["results"]) == 0:
            raise IcingaNoSuchObjectException()

        _services = self._get_service_list(host=host, service_pattern=services)
        if "service_downtimes" in _results["results"][0]:
            _ret["changes"] = len(_results["results"][0]["service_downtimes"])
            _ret["statuses"].append(
                _results["results"][0]["service_downtimes"])

        _ret["statuses"] = []
        _ret["statuses"].append(_results["results"][0]["status"])

        if _data["all_services"] == "1":
            _ret["services"] = _services
        else:
            # Select services
            if isinstance(services, str):

                for _service in _services:
                    # Set service maintenance mode
                    _result = self.set_service_maintenance_mode(host=host, service=_service, author=author,
                                                                comment=comment,
                                                                duration_seconds=duration_seconds,
                                                                check_before=False)

                    _ret["changes"] = _ret["changes"] + 1
                    _ret["statuses"].append(_result["status"])
                    _ret["services"].append(_service)

            elif isinstance(services, list):
                for _service in services:
                    # Set service maintenance mode
                    _result = self.set_service_maintenance_mode(host=host, service=_service, author=author,
                                                                comment=comment,
                                                                duration_seconds=duration_seconds,
                                                                check_before=False)
                    _ret["changes"] = _ret["changes"] + 1
                    _ret["statuses"].append(_result["status"])
                    _ret["services"].append(_service)

        _ret["changes_details"] = ", ".join(_ret["statuses"])
        return _ret

    def _send_request(self, url: str, method: str, data: str = ""):
        _headers = self.headers
        _headers.update({'X-HTTP-Method-Override': method})
        
        try:
            if not self.validate_certs:
                _response = requests.post(
                    url=f"{self.url}{url}",
                    data=self.module.jsonify(data),
                    headers=_headers,
                    verify=self.validate_certs
                )
            else:
                _response = requests.post(
                    url=f"{self.url}{url}",
                    data=self.module.jsonify(data),
                    headers=_headers)

        except requests.exceptions.ConnectionError as e:
            raise IcingaConnectionException(f"Could not connect to Icinga server: {e}")
        except OSError as e:
            raise IcingaConnectionException(f"Could not connect to Icinga server: {e}")

        if _response.status_code in [401, 403]:
            raise IcingaAuthenticationException

        if _response.status_code in [404]:
            _details = _response.json()
            raise IcingaNoSuchObjectException(_details['status'])

        if _response.status_code in [500]:
            raise IcingaNoSuchObjectException()

        return _response.json()

class IcingaConnectionException(Exception):
    customMessage = False
    defaultMessage = "Unable to connect to icinga server"

    def __init__(self, message=None):
        if message == None:
            self.message = self.defaultMessage
        else:
            self.message = message
            self.customMessage = True
        super().__init__(self.message)


class IcingaAuthenticationException(Exception):
    customMessage = False
    defaultMessage = "Unable to authenticate"

    def __init__(self, message=None):
        if message == None:
            self.message = self.defaultMessage
        else:
            self.message = message
            self.customMessage = True
        super().__init__(self.message)


class IcingaFailedService(Exception):
    customMessage = False
    defaultMessage = "One or more services are down"

    def __init__(self, message=None):
        if message == None:
            self.message = self.defaultMessage
        else:
            self.message = message
            self.customMessage = True
        super().__init__(self.message)


class IcingaNoSuchObjectException(Exception):
    customMessage = False
    defaultMessage = "Unable to find the object"

    def __init__(self, message=None):
        if message == None:
            self.message = self.defaultMessage
        else:
            self.message = message
            self.customMessage = True
        super().__init__(self.message)


class IcingaStatus():
    def serviceStateToString(status: int = 0):
        if status == 0:
            return "OK"
        if status == 1:
            return "WARNING"
        if status == 2:
            return "CRITICAL"
        if status == 3:
            return "UNKNOWN"
