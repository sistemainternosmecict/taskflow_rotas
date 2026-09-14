import difflib
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import unicodedata
import urllib.parse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Unidade, Configuracao

logger = logging.getLogger("RotasService")

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_PATH = BASE_DIR / "unidades_educacao.json"

# Expressões regulares para ignorar prefixos e títulos institucionais comuns
PREFIXOS_ESCOLA_REGEX = [
    r"\b(escola\s+municipalizada)\b",
    r"\b(escola\s+municipal)\b",
    r"\b(colegio\s+municipal)\b",
    r"\b(centro\s+municipal\s+de\s+educacao)\b",
    r"\b(centro\s+municipal)\b",
    r"\b(creche\s+municipal)\b",
    r"\b(casa\s+creche)\b",
    r"\b(casa\s+de\s+cultura)\b",
    r"\b(c\s*m\s+de\s+educacao\s+infantil)\b",
    r"\b(centro\s+de\s+capacitacao\s+profissional)\b",
    r"\b(centro\s+de\s+capacitacao)\b",
    r"\b(centro\s+de\s+apoio\s+a\s+inclusao\s+escolar)\b",
    r"\b(caie)\b",
    r"\b(e\s*m)\b",
    r"\b(c\s*m)\b",
    r"\b(profa?|professor|professora)\b",
    r"\b(vereador|ver|prefeito|pref)\b",
]


def normalizar_texto(texto: str) -> str:
    """Remove acentos, cedilhas, pontuações e converte para minúsculas."""
    if not texto:
        return ""
    texto_sem_acento = (
        unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    )
    # Substitui pontuações e caracteres especiais por espaço
    texto_limpo = re.sub(r"[^\w\s]", " ", texto_sem_acento.lower())
    return " ".join(texto_limpo.split())


def extrair_nucleo_nome(texto: str) -> str:
    """
    Remove observações entre parênteses e prefixos comuns como Casa Creche,
    Escola Municipal, E.M., C.M., etc., isolando o núcleo identificador da unidade.
    """
    if not texto:
        return ""
    # Remove conteúdo entre parênteses (ex: '(Escola e Creche em período parcial)')
    texto_sem_paren = re.sub(r"\(.*?\)", " ", texto)
    norm = normalizar_texto(texto_sem_paren)
    for padrao in PREFIXOS_ESCOLA_REGEX:
        norm = re.sub(padrao, " ", norm)
    return " ".join(norm.split())


def seed_database_if_empty(db: Session, json_path: Optional[Path] = None) -> int:
    """
    Importa os dados iniciais de unidades_educacao.json para a tabela SQLite
    se o banco estiver vazio. O arquivo JSON original NÃO é alterado.
    """
    total_existente = db.query(Unidade).count()
    if total_existente > 0:
        logger.info("Banco já possui %d unidades cadastradas. Seed ignorado.", total_existente)
        return total_existente

    caminho = json_path or DEFAULT_JSON_PATH
    if not caminho.exists():
        logger.warning("Arquivo de seed %s não encontrado!", caminho)
        return 0

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    logger.info("Iniciando seed de %d unidades para o banco SQLite...", len(dados))
    unidades_para_inserir = []
    for item in dados:
        nome = (item.get("nome") or "").strip()
        endereco = (item.get("endereco") or "").strip()
        if not nome:
            continue

        unidade = Unidade(
            nome=nome,
            endereco=endereco,
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            plus_code=item.get("plus_code"),
            plus_code_curto=item.get("plus_code_curto"),
        )
        unidades_para_inserir.append(unidade)

    db.bulk_save_objects(unidades_para_inserir)
    db.commit()
    total_inserido = db.query(Unidade).count()
    logger.info("Seed concluído com sucesso: %d unidades inseridas no SQLite.", total_inserido)
    return total_inserido


def buscar_unidade_db(nome_busca: str, db: Session) -> Unidade:
    """
    Busca uma unidade educacional no banco pelo nome, mesmo que parcial ou abreviado.
    Ignora maiúsculas/minúsculas, acentos, cedilhas e prefixos como
    'Casa Creche', 'Escola Municipal', 'E.M.', 'C.M.', etc.
    """
    todas = db.query(Unidade).all()
    if not todas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma unidade cadastrada no banco de dados.",
        )

    termo_norm = normalizar_texto(nome_busca)
    termo_nucleo = extrair_nucleo_nome(nome_busca)

    # Tokens significativos da busca
    base_tokens = termo_nucleo if termo_nucleo else termo_norm
    tokens_busca = [t for t in base_tokens.split() if len(t) > 1]
    set_tokens_busca = set(tokens_busca)

    # 1. Correspondência exata no nome normalizado ou no núcleo
    for u in todas:
        u_norm = normalizar_texto(u.nome)
        u_nucleo = extrair_nucleo_nome(u.nome)
        if termo_norm == u_norm or (termo_nucleo and termo_nucleo == u_nucleo):
            return u

    # 2. Correspondência por Substring (no núcleo da unidade ou no nome normalizado)
    candidatos_substr = []
    for u in todas:
        u_norm = normalizar_texto(u.nome)
        u_nucleo = extrair_nucleo_nome(u.nome)

        if termo_nucleo and termo_nucleo in u_nucleo:
            candidatos_substr.append((u, len(u_nucleo) - len(termo_nucleo)))
        elif termo_norm in u_norm:
            candidatos_substr.append((u, len(u_norm) - len(termo_norm)))
        elif u_nucleo and u_nucleo in termo_norm:
            candidatos_substr.append((u, len(termo_norm) - len(u_nucleo)))

    if candidatos_substr:
        # Menor diferença de tamanho indica a opção mais precisa
        candidatos_substr.sort(key=lambda item: item[1])
        return candidatos_substr[0][0]

    # 3. Correspondência por Tokens (todas as palavras do termo estão no nome/núcleo)
    if set_tokens_busca:
        candidatos_tokens = []
        for u in todas:
            u_nucleo = extrair_nucleo_nome(u.nome)
            u_tokens = set(u_nucleo.split()) | set(normalizar_texto(u.nome).split())
            if set_tokens_busca.issubset(u_tokens):
                candidatos_tokens.append((u, len(u_nucleo)))
        if candidatos_tokens:
            candidatos_tokens.sort(key=lambda item: item[1])
            return candidatos_tokens[0][0]

    # 4. Similaridade aproximada (difflib) no núcleo e no nome completo
    nomes_nucleo_map = {extrair_nucleo_nome(u.nome): u for u in todas if extrair_nucleo_nome(u.nome)}
    termo_alvo = termo_nucleo if termo_nucleo else termo_norm
    matches = difflib.get_close_matches(termo_alvo, list(nomes_nucleo_map.keys()), n=1, cutoff=0.55)
    if matches:
        return nomes_nucleo_map[matches[0]]

    nomes_full_map = {normalizar_texto(u.nome): u for u in todas}
    matches_full = difflib.get_close_matches(termo_norm, list(nomes_full_map.keys()), n=1, cutoff=0.5)
    if matches_full:
        return nomes_full_map[matches_full[0]]

    # Sugestões se não encontrar
    sugestoes = difflib.get_close_matches(termo_norm, list(nomes_full_map.keys()), n=3, cutoff=0.3)
    sugestoes_nomes = [nomes_full_map[s].nome for s in sugestoes]
    msg_sugestao = f". Você quis dizer: {', '.join(sugestoes_nomes)}?" if sugestoes_nomes else ""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unidade '{nome_busca}' não encontrada{msg_sugestao}",
    )


def gerar_link_rota_maps(pontos: List[str]) -> str:
    """
    Gera um link oficial do Google Maps Directions a partir de uma lista ordenada de pontos.
    """
    if not pontos or len(pontos) < 2:
        raise ValueError("É necessário fornecer ao menos 2 pontos (origem e destino).")

    pontos_encoded = [urllib.parse.quote(ponto.strip()) for ponto in pontos]
    origem = pontos_encoded[0]
    destino = pontos_encoded[-1]
    waypoints = pontos_encoded[1:-1]

    url = f"https://www.google.com/maps/dir/?api=1&origin={origem}&destination={destino}"
    if waypoints:
        url += f"&waypoints={'%7C'.join(waypoints)}"

    return url


def processar_calculo_rota(nomes_escolas: List[str], db: Session) -> Dict[str, Any]:
    """
    Localiza as unidades no banco de dados SQLite, utiliza o 'plus_code_curto'
    cadastrado para cada uma e gera o link de rota do Google Maps.
    """
    if not nomes_escolas or len(nomes_escolas) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário fornecer ao menos 2 unidades (origem e destino) para traçar a rota.",
        )

    pontos_rota: List[Dict[str, Any]] = []
    codigos_maps: List[str] = []

    for ordem, nome in enumerate(nomes_escolas, start=1):
        unidade = buscar_unidade_db(nome, db)
        
        # Prioriza o plus_code_curto do banco SQLite
        codigo = (
            unidade.plus_code_curto
            or unidade.plus_code
            or (f"{unidade.latitude},{unidade.longitude}" if unidade.latitude and unidade.longitude else None)
        )

        if not codigo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"A unidade '{unidade.nome}' não possui Plus Code ou coordenadas cadastradas.",
            )

        codigos_maps.append(codigo)
        pontos_rota.append({
            "ordem": ordem,
            "id": unidade.id,
            "nome": unidade.nome,
            "endereco": unidade.endereco,
            "plus_code_curto": codigo,
            "latitude": unidade.latitude,
            "longitude": unidade.longitude,
        })

    link_maps = gerar_link_rota_maps(codigos_maps)

    return {
        "link_maps": link_maps,
        "total_pontos": len(pontos_rota),
        "pontos": pontos_rota,
    }


def atualizar_plus_code_curto(unidade_id: int, novo_codigo: str, db: Session) -> Unidade:
    """Atualiza o campo plus_code_curto de uma unidade no banco SQLite."""
    unidade = db.query(Unidade).filter(Unidade.id == unidade_id).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidade com ID {unidade_id} não encontrada.",
        )

    unidade.plus_code_curto = novo_codigo.strip()
    db.commit()
    db.refresh(unidade)
    return unidade


CHAVE_PONTO_PARTIDA = "ponto_partida_plus_code"
CHAVE_PONTO_PARTIDA_DESC = "ponto_partida_descricao"


def obter_ponto_partida(db: Session) -> Dict[str, Any]:
    """Retorna o Plus Code e a descrição do ponto de partida configurados no banco SQLite."""
    cfg_code = db.query(Configuracao).filter(Configuracao.chave == CHAVE_PONTO_PARTIDA).first()
    cfg_desc = db.query(Configuracao).filter(Configuracao.chave == CHAVE_PONTO_PARTIDA_DESC).first()

    code = (cfg_code.valor if cfg_code and cfg_code.valor else "").strip()
    desc = (cfg_desc.valor if cfg_desc and cfg_desc.valor else "Sede / Ponto de Partida Padrão").strip()
    updated = cfg_code.updated_at if cfg_code else None

    return {
        "plus_code": code,
        "ponto_partida": code,
        "descricao": desc,
        "updated_at": updated,
    }


def salvar_ponto_partida(db: Session, plus_code: str, descricao: Optional[str] = None) -> Dict[str, Any]:
    """Cria ou atualiza o Plus Code do ponto de partida no banco SQLite."""
    codigo_limpo = (plus_code or "").strip()
    if not codigo_limpo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O Plus Code do ponto de partida não pode ser vazio.",
        )

    cfg_code = db.query(Configuracao).filter(Configuracao.chave == CHAVE_PONTO_PARTIDA).first()
    if not cfg_code:
        cfg_code = Configuracao(
            chave=CHAVE_PONTO_PARTIDA,
            valor=codigo_limpo,
            descricao="Plus Code do ponto de partida padrão para cálculo de rotas",
        )
        db.add(cfg_code)
    else:
        cfg_code.valor = codigo_limpo

    if descricao is not None:
        desc_limpa = descricao.strip()
        cfg_desc = db.query(Configuracao).filter(Configuracao.chave == CHAVE_PONTO_PARTIDA_DESC).first()
        if not cfg_desc:
            cfg_desc = Configuracao(
                chave=CHAVE_PONTO_PARTIDA_DESC,
                valor=desc_limpa,
                descricao="Descrição ou identificação do ponto de partida",
            )
            db.add(cfg_desc)
        else:
            cfg_desc.valor = desc_limpa

    db.commit()
    db.refresh(cfg_code)
    return obter_ponto_partida(db)

