from __future__ import annotations

from multi_agent.domain.tasks import RetryPolicy, TaskDependency, TaskSpec


def source_inventory_tasks() -> list[TaskSpec]:
    return [
        TaskSpec(task_id="inventory", capability_id="source_inventory", capability_version="stage01/1", resource_class="cpu")
    ]


def xx_v1_assessment_tasks() -> list[TaskSpec]:
    return [
        TaskSpec(
            task_id="quality_xx_v1",
            agent_name="QualityService",
            resource_class="cpu",
            required=True,
            parameters={"goal": "xx_v1_assessment"},
        ),
        TaskSpec(
            task_id="assessment_xx_v1",
            capability_id="xx_v1_score",
            capability_version="xx_v1_score/1",
            agent_name="AssessmentAgent",
            resource_class="cpu",
            required=True,
            depends_on=[TaskDependency(task_id="quality_xx_v1", mode="required_success")],
            retry_policy=RetryPolicy(max_attempts=1),
        ),
    ]


def longitudinal_tasks() -> list[TaskSpec]:
    return [
        TaskSpec(
            task_id="quality_longitudinal",
            agent_name="QualityService",
            resource_class="cpu",
            required=True,
            parameters={"goal": "longitudinal_xx_v1"},
        ),
        TaskSpec(
            task_id="longitudinal_xx_v1",
            capability_id="longitudinal_describe",
            capability_version="longitudinal_describe/1",
            agent_name="LongitudinalAgent",
            resource_class="cpu",
            required=True,
            depends_on=[TaskDependency(task_id="quality_longitudinal", mode="required_success")],
            retry_policy=RetryPolicy(max_attempts=1),
        ),
    ]


def multi_source_summary_tasks() -> list[TaskSpec]:
    return [
        *xx_v1_assessment_tasks(),
        *longitudinal_tasks(),
        TaskSpec(
            task_id="laboratory_optional",
            agent_name="LaboratoryGeneticsAgent",
            resource_class="cpu",
            required=False,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        TaskSpec(
            task_id="synthesis_report",
            agent_name="SynthesisAgent",
            resource_class="cpu",
            required=True,
            depends_on=[
                TaskDependency(task_id="assessment_xx_v1", mode="terminal"),
                TaskDependency(task_id="longitudinal_xx_v1", mode="terminal"),
                TaskDependency(task_id="laboratory_optional", mode="terminal"),
            ],
            parameters={"report_schema": "stage06.report_snapshot/1"},
        ),
    ]




def multimodal_summary_tasks() -> list[TaskSpec]:
    modality_tasks = [
        TaskSpec(
            task_id="text_observations",
            capability_id="text_extract",
            capability_version="text_extract/1",
            agent_name="TextAgent",
            resource_class="cpu",
            required=False,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        TaskSpec(
            task_id="knowledge_candidates",
            capability_id="knowledge_retrieve",
            capability_version="knowledge_retrieve/1",
            agent_name="KnowledgeAgent",
            resource_class="cpu",
            required=False,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        TaskSpec(
            task_id="diamond_compatibility",
            capability_id="diamond_validate",
            capability_version="diamond_validate/1",
            agent_name="ImagingAgent",
            resource_class="cpu",
            required=False,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
    ]
    tasks = []
    for task in multi_source_summary_tasks():
        if task.task_id == "synthesis_report":
            task = task.model_copy(update={
                "depends_on": task.depends_on + [
                    TaskDependency(task_id="text_observations", mode="terminal"),
                    TaskDependency(task_id="knowledge_candidates", mode="terminal"),
                    TaskDependency(task_id="diamond_compatibility", mode="terminal"),
                ]
            })
        tasks.append(task)
    return [*tasks[:-1], *modality_tasks, tasks[-1]]

