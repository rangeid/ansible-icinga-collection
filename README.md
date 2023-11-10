# ansible-icinga-collection

icinga is an Ansible collection to manage maintenance and checks in Icinga. The module will interact with the Icinga2 Server to:
* set maintenance mode for an host or a host and its services
* check the status of a host's service

### rangeid.icinga.maintenance: set host and node maintenance

#### Node maintenance
    - name: "Set node maintenance"
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
    - name: "Remove node maintenance"
      rangeid.icinga.maintenance:
        icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
        icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
        icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
        maintenance: disabled
        hostname: "EQS-CA"

If host doesn't exist:

    TASK [Set node maintenance] *********************
    fatal: [localhost]: FAILED! => changed=false
      msg: Unable to find the host EQS-DOESNT-EXIST

#### Node and service maintenance

    - name: "test-playbook | Set Maintenance"
      hosts: localhost
      tasks:
        - name: "Set Maintenance for the node"
          rangeid.icinga.maintenance:
            icinga_server: "{{ lookup('ansible.builtin.env', 'ICINGA_SERVER') }}"
            icinga_username: "{{ lookup('ansible.builtin.env', 'ICINGA_USERNAME') }}"
            icinga_password: "{{ lookup('ansible.builtin.env', 'ICINGA_PASSWORD') }}"
            maintenance: enabled
            services: "*"
            duration: "10m 30s"
            hostname: "EQS-CA"


#### Node and all services maintenance


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
        msg: One or more services are down (Service TEST-OPENXPKI state is CRITICAL after timeout of 10 seconds)
        service_status: 2.0