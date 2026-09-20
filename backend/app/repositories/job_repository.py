from app.repositories.base import Repository
from app.models import Job
class JobRepository(Repository[Job]): pass
