from fastapi import HTTPException

def not_found(detail: str = "资源不存在") -> HTTPException:
    return HTTPException(status_code=404, detail=detail)
