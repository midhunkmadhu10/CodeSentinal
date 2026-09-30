"""Repository endpoints: connect, list, detail, trigger indexing."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..db_models import Repository, User
from ..github import parse_repository
from ..schemas import RepositoryCreate, RepositoryOut
from ..worker import enqueue_job

router = APIRouter(prefix="/api/repos", tags=["repos"])


def _repo_to_out(repo: Repository) -> RepositoryOut:
    graph = repo.graph or {}
    return RepositoryOut(
        id=repo.id,
        owner=repo.owner,
        name=repo.name,
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        is_private=repo.is_private,
        index_status=repo.index_status,
        indexed_at=repo.indexed_at.isoformat() if repo.indexed_at else None,
        chunk_count=repo.chunk_count,
        symbol_count=repo.symbol_count,
        file_count=repo.file_count,
        graph_nodes=len(graph.get("nodes", [])),
        graph_edges=len(graph.get("edges", [])),
        last_error=repo.last_error,
        created_at=repo.created_at.isoformat() if repo.created_at else None,
    )


def _get_owned_repo(db: Session, user: User, repo_id: int) -> Repository:
    repo = db.get(Repository, repo_id)
    if repo is None or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.get("", response_model=list[RepositoryOut])
def list_repos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repos = db.query(Repository).filter(Repository.user_id == user.id).order_by(Repository.id).all()
    return [_repo_to_out(repo) for repo in repos]


@router.post("", response_model=RepositoryOut, status_code=201)
def connect_repo(
    req: RepositoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner, name = parse_repository(req.repository)
    existing = (
        db.query(Repository)
        .filter(Repository.user_id == user.id, Repository.full_name == f"{owner}/{name}")
        .first()
    )
    if existing is not None:
        return _repo_to_out(existing)
    repo = Repository(user_id=user.id, owner=owner, name=name, full_name=f"{owner}/{name}")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return _repo_to_out(repo)


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repo(
    repo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _repo_to_out(_get_owned_repo(db, user, repo_id))


@router.delete("/{repo_id}", status_code=204)
def delete_repo(
    repo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _get_owned_repo(db, user, repo_id)
    db.delete(repo)
    db.commit()


@router.post("/{repo_id}/index", response_model=RepositoryOut)
def trigger_index(
    repo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a background indexing job for this repository."""
    repo = _get_owned_repo(db, user, repo_id)
    if repo.index_status in ("indexing",):
        raise HTTPException(status_code=409, detail="Indexing is already in progress.")
    repo.index_status = "pending"
    repo.last_error = None
    db.commit()
    enqueue_job(db, type="index_repository", repo_id=repo.id, user_id=user.id,
                payload={"repo_id": repo.id})
    return _repo_to_out(repo)
