from ansible.module_utils.urls import fetch_url, basic_auth_header
import datetime
import time
import requests
import os
import json


class IcingaMiniClass():
    def __init__(self, module, url, username, password):
        self.url = url
        self.username = username
        self.password = password
        self.module = module
        self.last_service_status = 3

        self.headers = {
            'Authorization': basic_auth_header(self.username, self.password),
            'Accept': 'application/json'
        }

        self.certpath = "/etc/ssl/certs/ca-certificates.crt"
        if os.path.isfile("/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"):
            self.certpath = "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"

    def get_last_service_status(self):
        return self.last_service_status

    # def get_services(self, host):
    #   response, info = fetch_url(module, f"{icinga_server}/v1/actions/schedule-downtime", headers=headers, method='POST',
    #                     data=json.dumps(data), timeout=30)

    def _check_all_services(self, host, timeout: int = 10, retries: int = 0, except_on_failure: bool = False):
        """
        Check all host's services and return only on timeout (with error) or when
        all services are green
        """
        _ret = dict(
            failed = [],
            success = []
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
        Get list ov services based on hots and provided pattern
        :param host: Icinga hostname
        :param service_pattern: pattern in glob format
        :return: list of services
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
        Get current host status
        :param host: Icinga hostnane
        :param service: Icinga service or services
        :return: status response
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
        Check a single service
        :param host: Icinga hostnane
        :param service: Icinga service
        :param timeout: Check timeout, if timeout == 0, service status will not be checked
        :param retries: Check retries. If a service is failed, after the timeout, a new check will be issued
        :param except_on_failure: generate an exception if the service is failed after timeout and retries, otherwise
                                  return boolean return boolean status
        :return: true if the service is green, false if warning, critical or unknown
        """
        _retries = 0
        while(True):
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

    def _get_invalid_services(self, services : list = [],check_against : list = []):
        """
        Compare real service list with list provided by the user in order to check if all services exist
        :param services: real service list
        :param check_against: user provide service list
        :return: list of invalid services
        """
        _ret = []

        for _in_service in check_against:
            if not _in_service in services:
                _ret.append(_in_service)

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
            _results = self._check_all_services(host=host, retries=check_retries, timeout=check_timeout)
            if len(_results["failed"]) > 0 and stop_on_failed_service:
                failed_services = ", ".join(_results["failed"])
                raise IcingaFailedService(f"One or more services are still failed: {failed_services}")


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
                _ret['status'] = " ".join([_ret['status'], _results["results"][0]['status']]).strip()

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
                             author: str ="Ansible",
                             comment: str ="Downtime",
                             check_before: bool = False,
                             stop_on_failed_service: bool = False,
                             check_retries: int = 1,
                             check_timeout: int = 10):

        if check_before:
            _results = self._check_all_services(host=host, retries=check_retries, timeout=check_timeout)
            if len(_results["failed"]) > 0 and stop_on_failed_service:
                failed_services = ", ".join(_results["failed"])
                raise IcingaFailedService(f"One or more services are still failed: {failed_services}")

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
                _services = self._get_service_list(host=host, service_pattern=services)

            if isinstance(services, list):
                _invalid_services = self._get_invalid_services(services=_services,check_against=services)
                if len(_invalid_services) > 0:
                    _invalid_services_list = ", ".join(_invalid_services)
                    _valid_services_list = ", ".join(_services)
                    raise IcingaNoSuchObjectException(message=f"Unable to find one or more services: {_invalid_services_list}, valid services are {_valid_services_list}")

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
            _ret["statuses"].append(_results["results"][0]["service_downtimes"])

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

        _response = requests.post(
            url=f"{self.url}{url}",
            data=self.module.jsonify(data),
            headers=_headers,
            verify=self.certpath
        )

        if _response.status_code in [401, 403]:
            raise IcingaAuthenticationException

        if _response.status_code in [404]:
            _details = _response.json()
            raise IcingaNoSuchObjectException(_details['status'])

        if _response.status_code in [500]:
            raise IcingaNoSuchObjectException()

        return _response.json()


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
