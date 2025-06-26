from google.adk.agents import Agent, SequentialAgent, LlmAgent
from kubernetes import client, config
from typing import List, Dict

# --- Tool 1: List Pods ---
def list_pods() -> List[Dict]:
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        pod_list = v1.list_pod_for_all_namespaces()
        pods: List[Dict] = []

        for pod in pod_list.items:
            restart_count = sum([c.restart_count for c in pod.status.container_statuses or []])
            containers = [c.name for c in pod.spec.containers]

            pods.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "node": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip,
                "start_time": str(pod.status.start_time),
                "restart_count": restart_count,
                "containers": containers,
            })

        return pods

    except Exception as e:
        print(f"An error occurred: {e}")
        return []

# --- Tool 2: Collect Logs for Pods ---
def collect_logs_for_pods(pods: List[Dict], num_lines: int = 5) -> List[Dict]:
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        logs_list: List[Dict] = []

        for pod in pods:
            pod_name = pod["name"]
            namespace = pod["namespace"]
            container_names = pod["containers"]

            for container in container_names:
                try:
                    raw_logs = v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container,
                        tail_lines=num_lines
                    )

                    log_lines = raw_logs.strip().split("\n")
                    structured_logs = [{"line_number": i + 1, "log": line} for i, line in enumerate(log_lines)]

                    logs_list.append({
                        "pod_name": pod_name,
                        "namespace": namespace,
                        "container_name": container,
                        "logs": structured_logs
                    })

                except Exception as log_error:
                    logs_list.append({
                        "pod_name": pod_name,
                        "namespace": namespace,
                        "container_name": container,
                        "logs": [{"line_number": 1, "log": f"Error fetching logs: {log_error}"}]
                    })

        return logs_list

    except Exception as e:
        print(f"Failed to collect logs: {e}")
        return []

# --- Agent 1: List Pods ---
pod_listing_agent = LlmAgent(
    name="PodListingAgent",
    description="Agent to list pods in the cluster",
    model="gemini-2.5-flash",
    tools=[list_pods],
    output_key="pods",
    instruction="""
You are a smart Kubernetes pod listing agent. Use the `list_pods` tool to list all pods in the cluster.

Display the results in a clean, readable **column-wise format**. For each pod, print:

- Pod Name
- Namespace
- Status
- Node
- Pod IP
- Start Time
- Restart Count
- Containers (comma-separated)

Example:
Pod Name       : nginx-abc123
Namespace      : default
Status         : Running
Node           : minikube
Pod IP         : 10.244.0.5
Start Time     : 2024-06-25T14:03:12Z
Restart Count  : 1
Containers     : app, metrics
--------------------------------------------
if no pod is found, print a message indicating that no pods are available.
"""
)



# --- Agent 2: Collect Logs from Pods ---
log_collector_agent = LlmAgent(
    name="LogCollectorAgent",
    description="Agent to collect logs from pods in the cluster",
    model="gemini-2.5-flash",
    tools=[collect_logs_for_pods],
    output_key="pod_logs",
    instruction="""
You are a Kubernetes log collection agent.

Use the {pods} (from the output of the PodListingAgent) as input.

For each pod:
- Use `pod['name']`, `pod['namespace']`
- For each container in `pod['containers']`, collect the first 5–10 lines of logs using the `collect_logs_for_pods` tool

Return logs in this format:

Pod Name       : <pod-name>
Namespace      : <namespace>
Container Name : <container-name>
Log Line 1     : ...
Log Line 2     : ...
...
--------------------------------------------

If an error occurs during log collection, include:
Error          : <error message>
"""
)

# --- Sequential Agent to Combine Both ---
Rubix_kube_agent = SequentialAgent(
    name="RubixKubeAgent",
    description="""You are a smart site reliability engineer whose job is to keep applications running 24/7. 
You must list pods in the cluster, collect logs, and generate RCA reports when issues occur.""",
    sub_agents=[
        pod_listing_agent,
        log_collector_agent
    ]
)




# Set this as the root agent to run the flow
root_agent = Rubix_kube_agent
