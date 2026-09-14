import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Unidade, Configuracao
from schemas import (
    CriarRotaPayload,
    PontoPartidaPayload,
    PontoPartidaResponse,
    RotaResponse,
    UnidadeResponse,
    UnidadeUpdatePlusCode,
)
from services import (
    atualizar_plus_code_curto,
    obter_ponto_partida,
    processar_calculo_rota,
    salvar_ponto_partida,
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

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env.strip():
    origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
else:
    origins = [
        "*",
        "https://taskflow-frontend-pqok.onrender.com",
        "http://192.168.100.215:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
@app.post("/api/rotas", response_model=RotaResponse, include_in_schema=False)
def criar_rota(
    payload: CriarRotaPayload,
    db: Session = Depends(get_db),
):
    """
    Endpoint principal solicitado:
    Recebe payload com lista de strings contendo os nomes das unidades e retorna a rota.
    """
    return processar_calculo_rota(payload.unidades, db)


# --- ROTAS DO PONTO DE PARTIDA ---


@app.get(
    "/api/v1/ponto-partida",
    response_model=PontoPartidaResponse,
    summary="Obter Plus Code do ponto de partida",
    description=(
        "Retorna o Plus Code configurado como ponto de partida (origem) para "
        "o cálculo de distâncias e montagem das rotas no frontend."
    ),
)
@app.get(
    "/api/ponto-partida", response_model=PontoPartidaResponse, include_in_schema=False
)
@app.get(
    "/api/v1/configuracoes/ponto-partida",
    response_model=PontoPartidaResponse,
    include_in_schema=False,
)
@app.get(
    "/api/configuracoes/ponto-partida",
    response_model=PontoPartidaResponse,
    include_in_schema=False,
)
def get_ponto_partida(db: Session = Depends(get_db)):
    """Retorna o Plus Code configurado para o ponto de partida."""
    return obter_ponto_partida(db)


@app.put(
    "/api/v1/ponto-partida",
    response_model=PontoPartidaResponse,
    summary="Definir/atualizar Plus Code do ponto de partida",
    description="Salva ou atualiza o Plus Code de partida no banco SQLite.",
)
@app.post(
    "/api/v1/ponto-partida",
    response_model=PontoPartidaResponse,
    include_in_schema=False,
)
@app.put(
    "/api/ponto-partida", response_model=PontoPartidaResponse, include_in_schema=False
)
@app.post(
    "/api/ponto-partida", response_model=PontoPartidaResponse, include_in_schema=False
)
@app.put(
    "/api/v1/configuracoes/ponto-partida",
    response_model=PontoPartidaResponse,
    include_in_schema=False,
)
@app.post(
    "/api/configuracoes/ponto-partida",
    response_model=PontoPartidaResponse,
    include_in_schema=False,
)
def set_ponto_partida(
    payload: PontoPartidaPayload,
    db: Session = Depends(get_db),
):
    """Atualiza o Plus Code do ponto de partida via API REST."""
    return salvar_ponto_partida(db, payload.plus_code, payload.descricao)


# --- TEMPLATES VISUAIS E FORMULÁRIOS HTML ---


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
    e o ponto de partida direto no banco SQLite.
    """
    unidades = db.query(Unidade).order_by(Unidade.id).all()
    ponto_partida = obter_ponto_partida(db)
    return templates.TemplateResponse(
        request=request,
        name="editar_unidades.html",
        context={
            "unidades": unidades,
            "ponto_partida": ponto_partida,
            "mensagem_sucesso": mensagem,
        },
    )


@app.post(
    "/configuracoes/ponto-partida",
    response_class=HTMLResponse,
    summary="Salvar Plus Code do ponto de partida via formulário HTML",
)
def salvar_ponto_partida_formulario(
    request: Request,
    plus_code: str = Form(...),
    descricao: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Recebe o formulário POST do template para salvar o ponto de partida."""
    dados = salvar_ponto_partida(db, plus_code, descricao)
    unidades = db.query(Unidade).order_by(Unidade.id).all()
    msg = f"Plus Code do Ponto de Partida atualizado para '{dados['plus_code']}' com sucesso!"
    return templates.TemplateResponse(
        request=request,
        name="editar_unidades.html",
        context={
            "unidades": unidades,
            "ponto_partida": dados,
            "mensagem_sucesso": msg,
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
    ponto_partida = obter_ponto_partida(db)
    msg = f"Plus Code curto da unidade '{unidade.nome}' atualizado para '{unidade.plus_code_curto}' com sucesso!"
    return templates.TemplateResponse(
        request=request,
        name="editar_unidades.html",
        context={
            "unidades": unidades,
            "ponto_partida": ponto_partida,
            "mensagem_sucesso": msg,
        },
    )


# --- ROTAS RESTful ADICIONAIS ---


@app.get(
    "/api/v1/unidades",
    response_model=List[UnidadeResponse],
    summary="Listar todas as unidades educacionais",
)
@app.get("/api/unidades", response_model=List[UnidadeResponse], include_in_schema=False)
def listar_unidades(db: Session = Depends(get_db)):
    """Retorna todas as unidades cadastradas no SQLite com seus Plus Codes e coordenadas."""
    return db.query(Unidade).order_by(Unidade.id).all()


@app.get(
    "/api/v1/unidades/{unidade_id}",
    response_model=UnidadeResponse,
    summary="Obter detalhes de uma unidade educacional",
)
@app.get(
    "/api/unidades/{unidade_id}",
    response_model=UnidadeResponse,
    include_in_schema=False,
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
@app.put(
    "/api/unidades/{unidade_id}",
    response_model=UnidadeResponse,
    include_in_schema=False,
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
