from google.adk.agents import Agent, SequentialAgent, LlmAgent
from kubernetes import client, config
from typing import List, Dict

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

# Pod listing agent
pod_listing_agent = LlmAgent(
    name="PodListingAgent",
    description="Agent to list pods in the cluster",
    model="gemini-2.5-flash",
    instruction="""
You are a smart Kubernetes pod listing agent. Your task is to use the `list_pods` tool to list all pods in the cluster.

Display the results in a clean, readable **column-wise format** (not tabular row-wise). For each pod, print the following fields vertically:

- Pod Name
- Namespace
- Status
- Node
- Pod IP
- Start Time
- Restart Count
- Containers (comma-separated)

Example format:

Pod Name       : my-app-5f7c9f4b9f-xyz
Namespace      : default
Status         : Running
Node           : node-1
Pod IP         : 10.244.1.5
Start Time     : 2024-06-25T14:03:12Z
Restart Count  : 1
Containers     : app-container, sidecar-container
--------------------------------------------

Print each pod’s details separated by a horizontal line. If no pods are found, say: "No pods are currently running."
""",
    tools=[list_pods]
)

# TODO: Define these before using
# log_collector_agent = ...
# RCA_agent = ...

# Optional: intermediate root agent if the above two are defined
# root_agent = SequentialAgent(
#     name="RootAgent",
#     sub_agents=[pod_listing_agent, log_collector_agent, RCA_agent]
# )

Rubix_kube_agent = SequentialAgent(
    name="RubixKubeAgent",
    sub_agents=[pod_listing_agent],  # Add others when defined
    description="""You are a smart site reliability engineer whose job is to keep applications running 24/7. 
You must list pods in the cluster, collect logs, and generate RCA reports when issues occur."""
)

# Set root_agent as the Rubix_kube_agent
root_agent = Rubix_kube_agent
