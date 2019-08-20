#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile
import time
import json
from datetime import datetime

from jinja2 import Template


class HealthError(Exception):
    """ This gets thrown if there is something wrong with the health of a service."""


def get_options():
    options = {}
    on_flag = ""
    for arg in sys.argv:
        if on_flag:
            options[on_flag] = arg
            on_flag = ""
            continue
        if arg.startswith('--'):
            on_flag = arg.lstrip('-')
            continue
        if arg == '-f':
            on_flag = '-filename-'

    return options


def get_yaml(options):
    filename = options.pop('-filename-', 'k8s-deployment.yaml')
    with open(filename, 'r') as f:
        s = f.read()
    template = Template(s)
    final = template.render(**options)
    return final


def check_health_of_first_pod(deployment):
    results = subprocess.check_output(['kubectl', 'get', 'deployment', deployment, '-o', 'json'])
    deployment_json = json.loads(results.decode())

    status = deployment_json.get('status', {})

    if (status.get('updatedReplicas') == status.get('availableReplicas')
            and status.get('unavailableReplicas') is None):
        return

    labels = [f'{k}={v}' for k, v in
              deployment_json.get('spec', {}).get('selector', {}).get('matchLabels', {}).items()]

    count = 0
    for i in range(24):  # 24 times is 2 minutes (5 second sleep below)
        command = ['kubectl', 'get', 'pods', '-o', 'json']
        for label in labels:
            command.append(f'-l{label}')
        pod_command = subprocess.check_output(command)
        pods = json.loads(pod_command.decode())

        pods = sorted(pods.get('items'),
                      key=lambda p: p.get('metadata', {}).get('creationTimestamp'))
        new_pod = pods[-1]  # the newest one is the one we care about

        pod_details_command = subprocess.check_output(['kubectl', 'get', 'pod', '-o', 'json',
                                                       new_pod.get('metadata').get('name')])
        new_pod = json.loads(pod_details_command.decode())

        if new_pod.get('status').get('phase') == 'Running':
            for cond in new_pod.get('status').get('conditions'):
                if cond.get('type') == 'Ready':
                    if cond.get('status') == 'True':
                        # All is good, continue deployment
                        return
        for c in new_pod.get('status').get('containerStatuses'):
            if c.get('state').get('waiting'):
                if c.get('state').get('waiting').get('reason') in ('ImagePullBackOff', 'ErrImagePull'):
                    print(
                        'Having trouble pulling the image (ImagePullBackOff)')
                    if count > 1:
                        print('Rolling Back deploy')
                        raise HealthError('Cant get container. Image must be bad.')
                elif c['state']['waiting']['reason'] == 'CrashLoopBackOff':
                    print('-- Logs of bad container --')
                    pod_logs = subprocess.check_output(
                        ['kubectl', 'logs', new_pod['metadata']['name']])
                    print(pod_logs.encode())
                    raise HealthError('Container not starting up correctly. Rolling back.')

        print('Waiting for 1st container to become healthy...')
        time.sleep(5)
        count += 1
    try:
        pod_logs = subprocess.check_output(
            ['kubectl', 'logs', new_pod['metadata']['name']])
        print(pod_logs.encode())
    except subprocess.CalledProcessError:
        print('-no pod logs-')
    raise HealthError('Container never went healthy, rolling back.')


def continue_deployment(deployment):
    subprocess.run(['kubectl', 'rollout', 'resume', f'deployment/{deployment}'])


def rollback_deployment(deployment):
    print('-- Rolling back deployment --')

    continue_deployment(deployment)
    time.sleep(1)
    subprocess.run(['kubectl', 'rollout', 'undo', f'deployment/{deployment}'])

    print(f'-- Rolled Back Deployment @ {datetime.utcnow()} -- ')


def wait_till_complete(deployment):
    subprocess.run(['kubectl', 'rollout', 'status', f'deployment/{deployment}'])


def deploy(filename):
    out = subprocess.check_output(['kubectl', 'apply', '-f', filename])
    print(out.decode())
    deployment = ''
    for line in out.decode().split('\n'):
        if line.startswith('deployment.apps/'):
            deployment = line[16:].split(' ')[0]
    if deployment:
        time.sleep(2)
        subprocess.run(['kubectl', 'rollout', 'pause', f'deployment/{deployment}'])
        try:
            check_health_of_first_pod(deployment)
        except HealthError as e:
            rollback_deployment(deployment)
            raise SystemExit(str(e))
        else:
            continue_deployment(deployment)
            wait_till_complete(deployment)


def run():
    if os.getenv('KUBECTL_CONFIG'):
        os.makedirs('/root/.kube', exist_ok=True)
        with open('/root/.kube/config', 'w') as f:
            f.write(os.getenv('KUBECTL_CONFIG'))

    options = get_options()
    s = get_yaml(options)

    with tempfile.NamedTemporaryFile('w') as f:
        f.write(s)
        f.flush()

        deploy(f.name)


if __name__ == '__main__':
    run()
