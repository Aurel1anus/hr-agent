from app.repositories.base import Repository
from app.models import Application
class ApplicationRepository(Repository[Application]): pass
