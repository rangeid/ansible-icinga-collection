# ansible-icinga-collection

icinga is an Ansible collection to manage maintenance and checks in Icinga. The module will interact with the Icinga2 Server to:
* set maintenance mode for an host or a host and its services
* check the status of a host's service

### rangeid.icinga.maintenance: set host and services maintenance

#### Node maintenance
    - name: "test-playbook | Set node maintenance"
      rangeid.icinga.maintenance:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        maintenance: enabled
        duration: "10m 30s"
        hostname: "EQS-CA"
        message: "Patching started"
    - name: "Sleep"
      ansible.builtin.pause:
        seconds: 5
    - name: "test-playbook | Remove node maintenance"
      rangeid.icinga.maintenance:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        maintenance: disabled
        hostname: "EQS-CA"

If host doesn't exist:

    TASK [Set node maintenance] *********************
    fatal: [localhost]: FAILED! => changed=false
      msg: Unable to find the host EQS-CA

#### Node and all services maintenance

    - name: "test-playbook | Set Maintenance"
      hosts: localhost
      tasks:
        - name: "Set Maintenance for the node"
          rangeid.icinga.maintenance:
            icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
            icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
            icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
            maintenance: enabled
            service: "all"
            duration: "10m 30s"
            hostname: "EQS-CA"


#### Node and some services maintenance

You can use "service" and put in maintenance one or more services using wildcard:

    - name: "test-playbook | Set Maintenance for the node and services by wildcard"
      rangeid.icinga.maintenance:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        maintenance: enabled
        service: "LO*"
        duration: "1m 30s"
        hostname: "EQS-CA"
        message: "Partial maintenance"

this task returns a message like:

    TASK [debug] ************************************
    ok: [localhost] =>
      msg:
        changed: true
        failed: false
        message: Successfully scheduled downtime 'EQS-CA!80277054-57af-47e0-9350-d65593b312da' for object 'EQS-CA'., Successfully scheduled downtime 'EQS-CA!LOAD!97110cc3-632b-4470-b004-fef16d761ce3' for object 'EQS-CA!LOAD'., Successfully scheduled downtime 'EQS-CA!LOCAL-SSL-OPENXPKI!0943d16d-90b2-4782-894c-4ae277ce5522' for object 'EQS-CA!LOCAL-SSL-OPENXPKI'.
        original_message: ''
        services:
        - LOAD
        - LOCAL-SSL-OPENXPKI

or you can use "services" and put in maintenance one or more services listing it:

    - name: "test-playbook | Set Maintenance for the node and services by list"
      rangeid.icinga.maintenance:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        maintenance: enabled
        services:
          - LOAD
          - PING
        duration: "1m 30s"
        hostname: "EQS-CA"
        message: "Partial maintenance"

this task returns a message like:

    TASK [debug] ************************************
    ok: [localhost] =>
      msg:
        changed: true
        failed: false
        message: Successfully scheduled downtime 'EQS-CA!1f84f892-b5d0-483e-9e02-022cff55acec' for object 'EQS-CA'., Successfully scheduled downtime 'EQS-CA!LOAD!d2104177-b4f5-42e7-8690-d95560f6cd60' for object 'EQS-CA!LOAD'., Successfully scheduled downtime 'EQS-CA!PING!143639bc-6728-49f8-a1a1-f0245e305839' for object 'EQS-CA!PING'.
        original_message: ''
        services:
        - LOAD
        - PING


### rangeid.icinga.check_service: Force host service check with a timeout

    - name: "Check Service"
      rangeid.icinga.check_service:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        hostname: "EQS-CA"
        service: "TEST-OPENXPKI"
        timeout: 10
      register: service_status

and if the check fails:

    TASK [Check Service] ****************************
    fatal: [localhost]: FAILED! => changed=false
      msg: One or more services are down (Service TEST-OPENXPKI state is CRITICAL after timeout of 10 seconds)
      service_status: 2.0

or, when failed_when is set to false:

    TASK [Check Service: Registered variable] *******
    ok: [localhost] =>
      msg:
        changed: false
        failed: false
        failed_when_result: false
        message: One or more services are down (Service TEST-OPENXPKI state is CRITICAL after timeout of 10 seconds)
        service_status: 2.0