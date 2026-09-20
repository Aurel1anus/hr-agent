from app.repositories.base import Repository
from app.models import Candidate
class CandidateRepository(Repository[Candidate]): pass
