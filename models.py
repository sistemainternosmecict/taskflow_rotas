from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String
from database import Base


class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(255), nullable=False, index=True)
    endereco = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    plus_code = Column(String(50), nullable=True)
    plus_code_curto = Column(String(20), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Unidade(id={self.id}, nome='{self.nome}', plus_code_curto='{self.plus_code_curto}')>"
