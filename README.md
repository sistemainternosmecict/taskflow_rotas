# Rotas Taskflow API 🚀

API em **FastAPI** servida por **Granian** para cálculo de rotas no Google Maps utilizando **Plus Code Curto** e gestão visual das unidades educacionais com persistência em **SQLite** via **SQLAlchemy**.

---

## 🛠️ Tecnologias

- **FastAPI**: Framework web moderno e de alto desempenho.
- **Granian**: Servidor HTTP Rust para aplicações Python ASGI/RSGI.
- **SQLAlchemy**: ORM para manipulação e persistência de dados.
- **SQLite**: Banco de dados relacional leve armazenado em `data/rotas.db`.
- **Jinja2 & Tailwind CSS**: Template para interface web de consulta e edição rápida de Plus Codes.

---

## 🏃 Como Executar

### 1. Iniciar com Granian (Recomendado)
```bash
granian --interface asgi --reload --reload-ignore-dirs data --host 0.0.0.0 --port 8000 main:app
```

Ou execute diretamente via Python:
```bash
python main.py
```

Acesse a aplicação em:
- **Interface Web de Edição:** [http://127.0.0.1:8000/unidades/editar](http://127.0.0.1:8000/unidades/editar)
- **Documentação Swagger (OpenAPI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📌 Rotas da API

### 1. Gerar Rota (`POST /api/rotas`)
Recebe uma lista com os nomes das unidades e retorna o link formatado do Google Maps com base no `plus_code_curto` cadastrado no banco SQLite.

**Requisição:**
```json
POST /api/rotas
Content-Type: application/json

{
  "unidades": [
    "Casa Creche Adriana Rocha",
    "Casa Creche Carmo Gonçalves",
    "Casa Creche Benta de Souza Quintes"
  ]
}
```

**Resposta:**
```json
{
  "link_maps": "https://www.google.com/maps/dir/?api=1&origin=4GHP%2B97&destination=4H7J%2B3X&waypoints=4G2C%2BV7",
  "total_pontos": 3,
  "pontos": [
    {
      "ordem": 1,
      "id": 2,
      "nome": "Casa Creche Adriana Rocha",
      "endereco": "Rua Manoel Apolinário dos Santos, 07 - Rio da Areia",
      "plus_code_curto": "4GHP+97",
      "latitude": -22.871174,
      "longitude": -42.463771
    },
    {
      "ordem": 2,
      "id": 4,
      "nome": "Casa Creche Carmo Gonçalves",
      "endereco": "Rua Nicomedes Pereira dos Santos, 85, Verde Vale",
      "plus_code_curto": "4G2C+V7",
      "latitude": -22.897922,
      "longitude": -42.479475
    },
    {
      "ordem": 3,
      "id": 3,
      "nome": "Casa Creche Benta de Souza Quintes",
      "endereco": "Avenida Nova Saquarema, 1373 - Vilatur",
      "plus_code_curto": "4H7J+3X",
      "latitude": -22.889906,
      "longitude": -42.417742
    }
  ]
}
```

---

### 2. Interface de Edição de Plus Codes (`GET /unidades/editar`)
- Tabela responsiva com todos os registros do SQLite.
- Filtro em tempo real por nome, endereço ou código.
- Edição do campo `plus_code_curto` com salvamento instantâneo via botão "Salvar".
- Link direto para validar a localização no Google Maps.

---

### 3. Salvar Plus Code Curto via Formulário Web (`POST /unidades/editar/{id}`)
Atualiza o `plus_code_curto` via submissão de formulário HTML.

---

### 4. Salvar Plus Code Curto via API REST (`PUT /api/unidades/{id}`)
```json
PUT /api/unidades/1
Content-Type: application/json

{
  "plus_code_curto": "4G3P+7J"
}
```

---

### 5. Listar Unidades (`GET /api/unidades` ou `GET /api/v1/unidades`)
Retorna todas as unidades cadastradas no SQLite.

---

### 6. Obter Plus Code do Ponto de Partida (`GET /api/v1/ponto-partida`)
Retorna o Plus Code configurado como ponto de partida (origem) para o cálculo automático de distâncias e roteirização no frontend.

**Aliases disponíveis:**
- `GET /api/v1/ponto-partida`
- `GET /api/ponto-partida`

**Resposta:**
```json
{
  "plus_code": "4G3P+JM",
  "ponto_partida": "4G3P+JM",
  "descricao": "Sede da Secretaria de Educação",
  "updated_at": "2026-09-02T15:32:50.903782"
}
```

---

### 7. Definir / Atualizar Ponto de Partida (`PUT /api/v1/ponto-partida`)
Atualiza o Plus Code de partida no banco SQLite.

**Aliases disponíveis:**
- `PUT /api/v1/ponto-partida`
- `POST /api/v1/ponto-partida`
- `PUT /api/ponto-partida`

**Requisição:**
```json
{
  "plus_code": "4G3P+JM",
  "descricao": "Sede da Secretaria de Educação"
}
```

**Resposta:**
```json
{
  "plus_code": "4G3P+JM",
  "ponto_partida": "4G3P+JM",
  "descricao": "Sede da Secretaria de Educação",
  "updated_at": "2026-09-02T15:32:50.903782"
}
```

