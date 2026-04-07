from __future__ import annotations

from dataclasses import dataclass

from domaintoolbelt.core.types import PlanStep


@dataclass
class ExecutionCluster:
    cluster_id: int
    steps: list[PlanStep]


class DependencyResolver:
    """Resolve a plan into dependency-safe execution clusters."""

    def resolve(self, steps: list[PlanStep]) -> list[ExecutionCluster]:
        step_map = {step.step_id: step for step in steps}
        dependents: dict[str, set[str]] = {step.step_id: set() for step in steps}
        in_degree: dict[str, int] = {step.step_id: 0 for step in steps}

        for step in steps:
            for dependency in step.depends_on:
                if dependency not in step_map:
                    raise ValueError(f"Unknown dependency '{dependency}' for step '{step.step_id}'.")
                dependents[dependency].add(step.step_id)
                in_degree[step.step_id] += 1

        ready = {step_id for step_id, degree in in_degree.items() if degree == 0}
        clusters: list[ExecutionCluster] = []
        cluster_id = 0

        while ready:
            cluster_steps = [step_map[step_id] for step_id in sorted(ready)]
            clusters.append(ExecutionCluster(cluster_id=cluster_id, steps=cluster_steps))
            cluster_id += 1

            next_ready: set[str] = set()
            for step in cluster_steps:
                for dependent_id in dependents[step.step_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_ready.add(dependent_id)
            ready = next_ready

        resolved_count = sum(len(cluster.steps) for cluster in clusters)
        if resolved_count != len(steps):
            raise ValueError("Dependency graph has a cycle; cannot resolve execution order.")
        return clusters
