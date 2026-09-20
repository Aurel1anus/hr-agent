from app.repositories.base import Repository
from app.models import Task
class TaskRepository(Repository[Task]): pass
