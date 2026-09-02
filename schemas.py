from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CriarRotaPayload(BaseModel):
    unidades: List[str] = Field(
        ...,
        min_length=2,
        description="Lista ordenada de nomes das unidades para traçar a rota (mínimo 2).",
        examples=[["Casa Creche Adriana Rocha", "Casa Creche Carmo Gonçalves"]],
    )


class PontoRota(BaseModel):
    ordem: int
    id: int
    nome: str
    endereco: str
    plus_code_curto: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RotaResponse(BaseModel):
    link_maps: str
    total_pontos: int
    pontos: List[PontoRota]


class UnidadeBase(BaseModel):
    nome: str
    endereco: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    plus_code: Optional[str] = None
    plus_code_curto: Optional[str] = None


class UnidadeUpdatePlusCode(BaseModel):
    plus_code_curto: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Novo Plus Code curto para a unidade (ex: 4GHP+97).",
        examples=["4GHP+97"],
    )


class UnidadeResponse(UnidadeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
