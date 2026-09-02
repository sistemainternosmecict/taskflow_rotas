import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Unidade
from schemas import (
    CriarRotaPayload,
    RotaResponse,
    UnidadeResponse,
    UnidadeUpdatePlusCode,
)
from services import (
    atualizar_plus_code_curto,
    processar_calculo_rota,
    seed_database_if_empty,
)

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RotasAPI")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida do FastAPI: cria as tabelas no SQLite e executa o seed inicial se necessário."""
    logger.info("Inicializando banco de dados SQLite...")
    Base.metadata.create_all(bind=engine)

    # Executa o seed inicial se a tabela estiver vazia
    db: Session = SessionLocal()
    try:
        total = seed_database_if_empty(db)
        logger.info("Banco de dados pronto com %d unidades.", total)
    finally:
        db.close()

    yield
    logger.info("Encerrando aplicação.")


app = FastAPI(
    title="Rotas Taskflow API",
    description="API com FastAPI e Granian para otimização de rotas e gestão de Plus Codes em SQLite.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- ROTAS PRINCIPAIS ---


@app.get("/", include_in_schema=False)
def home():
    """Redireciona para a página visual de edição das unidades."""
    return RedirectResponse(url="/unidades/editar", status_code=status.HTTP_302_FOUND)


@app.post(
    "/api/v1/rotas",
    response_model=RotaResponse,
    summary="Criar rota otimizada no Google Maps",
    description=(
        "Recebe uma lista ordenada com os nomes das unidades educacionais, "
        "localiza os Plus Codes curtos no SQLite e gera a URL de rota do Google Maps."
    ),
)
def criar_rota(
    payload: CriarRotaPayload,
    db: Session = Depends(get_db),
):
    """
    Endpoint principal solicitado:
    Recebe payload com lista de strings contendo os nomes das unidades e retorna a rota.
    """
    return processar_calculo_rota(payload.unidades, db)


@app.get(
    "/unidades/editar",
    response_class=HTMLResponse,
    summary="Interface para visualizar e editar os Plus Codes curtos",
)
def template_editar_unidades(
    request: Request,
    mensagem: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Rota que traz um template Jinja2 para visualizar e editar os plus_code_curto
    direto no banco SQLite.
    """
    unidades = db.query(Unidade).order_by(Unidade.id).all()
    return templates.TemplateResponse(
        request=request,
        name="editar_unidades.html",
        context={
            "unidades": unidades,
            "mensagem_sucesso": mensagem,
        },
    )


@app.post(
    "/unidades/editar/{unidade_id}",
    response_class=HTMLResponse,
    summary="Salvar Plus Code curto via formulário HTML",
)
def salvar_plus_code_formulario(
    request: Request,
    unidade_id: int,
    plus_code_curto: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Recebe o formulário POST do template para salvar e atualizar o plus_code_curto no SQLite.
    """
    unidade = atualizar_plus_code_curto(unidade_id, plus_code_curto, db)
    unidades = db.query(Unidade).order_by(Unidade.id).all()
    msg = f"Plus Code curto da unidade '{unidade.nome}' atualizado para '{unidade.plus_code_curto}' com sucesso!"
    return templates.TemplateResponse(
        request=request,
        name="editar_unidades.html",
        context={
            "unidades": unidades,
            "mensagem_sucesso": msg,
        },
    )


# --- ROTAS RESTful ADICIONAIS ---


@app.get(
    "/api/v1/unidades",
    response_model=List[UnidadeResponse],
    summary="Listar todas as unidades educacionais",
)
def listar_unidades(db: Session = Depends(get_db)):
    """Retorna todas as unidades cadastradas no SQLite com seus Plus Codes e coordenadas."""
    return db.query(Unidade).order_by(Unidade.id).all()


@app.get(
    "/api/v1/unidades/{unidade_id}",
    response_model=UnidadeResponse,
    summary="Obter detalhes de uma unidade educacional",
)
def obter_unidade(unidade_id: int, db: Session = Depends(get_db)):
    """Busca uma unidade específica pelo ID."""
    unidade = db.query(Unidade).filter(Unidade.id == unidade_id).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidade com ID {unidade_id} não encontrada.",
        )
    return unidade


@app.put(
    "/api/v1/unidades/{unidade_id}",
    response_model=UnidadeResponse,
    summary="Atualizar Plus Code curto via API REST",
)
def atualizar_unidade_api(
    unidade_id: int,
    payload: UnidadeUpdatePlusCode,
    db: Session = Depends(get_db),
):
    """Atualiza programaticamente o Plus Code curto de uma unidade no SQLite."""
    return atualizar_plus_code_curto(unidade_id, payload.plus_code_curto, db)


if __name__ == "__main__":
    # Permite rodar com Granian programaticamente se executado com `python main.py`
    import granian

    granian.Granian(
        "main:app",
        address="0.0.0.0",
        port=8000,
        interface="asgi",
        reload=True,
        reload_ignore_dirs=["data"],
    ).serve()
