from typing import Generic, TypeVar
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")

class Repository(Generic[ModelT]):
    def __init__(self, db: Session):
        self.db = db

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        return entity
