#! .venv/bin/python

import argparse
import re
import subprocess
import sys


def run_get_pods(namespace):
    stdout = subprocess.run(
        [
            "kubectl",
            "-n",
            namespace,
            "get",
            "pods",
            "--field-selector",
            "status.phase=Running",
            "-o=name",
        ],
        capture_output=True,
        text=True,
    ).stdout
    return [name.lstrip("pod/") for name in stdout.split()]


def get_pod(target_pod, pods):
    """Gets the name of the web, celery worker, or celery beat pod"""
    if target_pod == "web":
        target_pod = None

    pattern = re.compile(r"(atat(-\w.*)?)-[a-z0-9].*-[a-z0-9].*")
    for pod in pods:
        # suffix will be one of ( None | worker | beat)
        _, suffix = re.match(pattern, pod).groups()
        if f"-{target_pod}" == suffix or target_pod is suffix:
            return pod


def tail_pod_logs(pod_name, target, namespace, tail_length=100):
    command = [
        "kubectl",
        "-n",
        namespace,
        "logs",
        "-f",
        pod_name,
        f"--tail={tail_length}",
    ]
    if target == "web":
        command += ["-c", "atat"]
    subprocess.run(command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tail the logs of a pod in a given namespace"
    )
    parser.add_argument(
        "namespace",
        type=str,
        help="the namespace to query",
        choices=["staging", "master"],
    )
    parser.add_argument(
        "pod", type=str, help="the pod to query", choices=["web", "beat", "worker"],
    )
    parser.add_argument(
        "--tail", type=int, help="number of log entries to tail", default=100
    )
    args = parser.parse_args()

    pods = run_get_pods(args.namespace)
    pod_name = get_pod(args.pod, pods)
    if pod_name is None:
        sys.exit(f"Unable to get logs for {args.pod} pod in {args.namespace} namespace")

    try:
        tail_pod_logs(pod_name, args.pod, args.namespace, args.tail)
    except KeyboardInterrupt:
        exit(0)
