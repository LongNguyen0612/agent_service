from libs.result import Result, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories import TaskRepository
from src.adapter.repositories import SqlAlchemyTaskRepository
from .dtos import ListProjectTasksCommand, ListProjectTasksResponse, TaskSummaryDTO


class ListProjectTasksUseCase:
    """Use case for listing all tasks in a project"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, command: ListProjectTasksCommand) -> Result[ListProjectTasksResponse]:
        """
        Execute the list project tasks use case

        Returns:
            Result[ListProjectTasksResponse]: Success with list of tasks or error
        """
        async with self.uow as session:
            # Create repository
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)

            # AC-2.2.1, AC-2.2.2, AC-2.2.4: Get tasks with optional status filter
            # Repository already orders by created_at DESC and enforces tenant isolation
            status_filter = command.status.value if command.status else None
            tasks = await task_repo.find_by_project_id(
                command.project_id, command.tenant_id, status=status_filter
            )

            # AC-2.2.3: Empty project returns empty array
            task_summaries = [
                TaskSummaryDTO(
                    id=task.id,
                    title=task.title,
                    status=task.status,
                    created_at=task.created_at,
                )
                for task in tasks
            ]

            return Return.ok(ListProjectTasksResponse(tasks=task_summaries))
