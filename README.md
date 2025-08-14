# ERP Bauxita - Sistema Expandido

**Versão:** 2.0.0  
**Data:** Agosto 2025  
**Autor:** Manus AI

## Visão Geral

O ERP Bauxita é um sistema empresarial robusto para gerenciamento da cadeia de suprimentos de bauxita, desenvolvido com Flask e arquitetura empresarial moderna. Este projeto representa uma expansão significativa do sistema original, incorporando padrões de design avançados, APIs RESTful completas e funcionalidades empresariais essenciais.

## Características Principais

### 🏗️ Arquitetura Empresarial
- **Padrão Repository**: Abstração de acesso a dados com repositórios específicos
- **Camada de Serviços**: Lógica de negócio encapsulada e reutilizável
- **APIs RESTful**: Endpoints padronizados com documentação completa
- **Middleware Personalizado**: Tratamento de erros e autenticação centralizados

### 🔐 Segurança e Autenticação
- **JWT Authentication**: Sistema de autenticação baseado em tokens
- **Controle de Acesso**: Roles e permissões granulares
- **Middleware de Segurança**: Proteção automática de endpoints

### 📊 Funcionalidades de Negócio
- **Gestão de Produção**: Cenários, planejamento e enrollment de parceiros
- **Gestão de Embarcações**: Fleet management e otimização de alocação
- **Gestão de Parceiros**: Relacionamentos comerciais e análise de performance
- **Relatórios e Analytics**: Métricas abrangentes e dashboards

### 🛠️ Qualidade e Manutenibilidade
- **Validações Robustas**: Regras de negócio implementadas nos services
- **Tratamento de Erros**: Sistema centralizado de error handling
- **Logging Estruturado**: Auditoria completa de operações
- **Documentação Abrangente**: APIs documentadas e código comentado

## Estrutura do Projeto

```
flask-erp-expanded/
├── app/
│   ├── __init__.py                 # Application factory
│   ├── extensions.py               # Flask extensions
│   ├── models/                     # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── production.py           # Production models
│   │   ├── vessel.py               # Vessel models
│   │   ├── partner.py              # Partner models
│   │   └── ...
│   ├── lib/                        # Base classes and utilities
│   │   ├── base_model.py           # Base model with audit fields
│   │   ├── repository/             # Repository pattern implementation
│   │   └── services/               # Base service classes
│   ├── repository/                 # Specific repositories
│   │   ├── __init__.py
│   │   ├── production_repository.py
│   │   ├── vessel_repository.py
│   │   └── partner_repository.py
│   ├── services/                   # Business logic services
│   │   ├── __init__.py
│   │   ├── production_service.py
│   │   ├── vessel_service.py
│   │   └── partner_service.py
│   ├── api/                        # RESTful API
│   │   └── v1/                     # API version 1
│   │       ├── __init__.py
│   │       ├── utils.py            # API utilities
│   │       └── resources/          # API endpoints
│   │           ├── production_api.py
│   │           ├── vessel_api.py
│   │           ├── partner_api.py
│   │           └── auth_api.py
│   ├── middleware/                 # Custom middleware
│   │   ├── __init__.py
│   │   ├── error_handler.py        # Global error handling
│   │   └── auth.py                 # Authentication middleware
│   └── main/                       # Main blueprint (web interface)
│       ├── __init__.py
│       └── routes.py
├── config.py                       # Configuration classes
├── main.py                         # Application entry point
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Instalação e Configuração

### Pré-requisitos
- Python 3.11+
- pip (gerenciador de pacotes Python)
- SQLite (para desenvolvimento) ou PostgreSQL (para produção)

### Instalação

1. **Clone o repositório:**
```bash
git clone <repository-url>
cd flask-erp-expanded
```

2. **Crie um ambiente virtual:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows
```

3. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente:**
```bash
# Crie um arquivo .env na raiz do projeto
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///app.db
DEBUG=True
```

5. **Inicialize o banco de dados:**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. **Execute a aplicação:**
```bash
python main.py
```

A aplicação estará disponível em `http://localhost:5000`

## Uso da API

### Autenticação

Todas as operações da API (exceto login) requerem autenticação via JWT token.

#### Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "admin123"
}
```

**Resposta:**
```json
{
    "success": true,
    "message": "Login successful",
    "data": {
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "user": {
            "id": 1,
            "username": "admin",
            "role": "admin",
            "email": "admin@bauxita-erp.com"
        },
        "expires_in": 3600,
        "token_type": "Bearer"
    }
}
```

#### Usando o Token
Inclua o token no header Authorization de todas as requisições:
```bash
Authorization: Bearer <token>
```

### Usuários Padrão

O sistema inclui usuários padrão para desenvolvimento:

| Username | Password | Role | Descrição |
|----------|----------|------|-----------|
| admin | admin123 | admin | Acesso completo ao sistema |
| operator | operator123 | operator | Operações do dia a dia |
| viewer | viewer123 | viewer | Apenas visualização |

### Endpoints Principais

#### Productions (Produções)
- `GET /api/v1/productions` - Listar produções
- `POST /api/v1/productions` - Criar nova produção
- `GET /api/v1/productions/{id}` - Obter produção específica
- `PUT /api/v1/productions/{id}` - Atualizar produção
- `DELETE /api/v1/productions/{id}` - Excluir produção
- `POST /api/v1/productions/{id}/activate` - Ativar cenário
- `POST /api/v1/productions/{id}/complete` - Completar cenário
- `GET /api/v1/productions/{id}/metrics` - Métricas da produção
- `GET /api/v1/productions/dashboard` - Dashboard de produção

#### Vessels (Embarcações)
- `GET /api/v1/vessels` - Listar embarcações
- `POST /api/v1/vessels` - Criar nova embarcação
- `GET /api/v1/vessels/{id}` - Obter embarcação específica
- `PUT /api/v1/vessels/{id}` - Atualizar embarcação
- `DELETE /api/v1/vessels/{id}` - Excluir embarcação
- `PUT /api/v1/vessels/{id}/status` - Alterar status
- `PUT /api/v1/vessels/{id}/owner` - Atribuir proprietário
- `GET /api/v1/vessels/fleet/overview` - Visão geral da frota
- `POST /api/v1/vessels/fleet/optimize` - Otimizar alocação

#### Partners (Parceiros)
- `GET /api/v1/partners` - Listar parceiros
- `POST /api/v1/partners` - Criar novo parceiro
- `GET /api/v1/partners/{id}` - Obter parceiro específico
- `PUT /api/v1/partners/{id}` - Atualizar parceiro
- `DELETE /api/v1/partners/{id}` - Excluir parceiro
- `GET /api/v1/partners/{id}/portfolio` - Portfolio do parceiro
- `GET /api/v1/partners/{id}/performance` - Avaliação de performance
- `GET /api/v1/partners/halco-buyers` - Compradores HALCO
- `GET /api/v1/partners/offtakers` - Offtakers

### Exemplos de Uso

#### Criar Nova Produção
```bash
POST /api/v1/productions
Authorization: Bearer <token>
Content-Type: application/json

{
    "scenario_name": "Cenário 2025 Q1",
    "scenario_description": "Planejamento para primeiro trimestre de 2025",
    "contractual_year": 2025,
    "total_planned_tonnage": 12000000,
    "start_date_contractual_year": "2025-01-01",
    "end_date_contractual_year": "2025-12-31",
    "standard_moisture_content": 3.00
}
```

#### Criar Nova Embarcação
```bash
POST /api/v1/vessels
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "MV Bauxita Express",
    "vtype": "capesize",
    "imo": "1234567",
    "dwt": 180000,
    "loa": 289.5,
    "beam": 45.0,
    "owner_partner_id": 1
}
```

#### Filtrar Embarcações por Status
```bash
GET /api/v1/vessels?status=active&type=capesize
Authorization: Bearer <token>
```

## Modelos de Dados

### Production (Produção)
Representa cenários de produção anuais com gestão de status e versionamento.

**Campos principais:**
- `scenario_name`: Nome do cenário
- `contractual_year`: Ano contratual
- `total_planned_tonnage`: Tonelagem total planejada
- `status`: Status do cenário (draft, planned, active, completed, archived)
- `enrolled_partners`: Parceiros inscritos no cenário

### Vessel (Embarcação)
Representa embarcações da frota com especificações técnicas.

**Campos principais:**
- `name`: Nome da embarcação
- `vtype`: Tipo (shuttle, panamax, capesize)
- `status`: Status operacional (active, inactive, maintenance, retired)
- `dwt`: Deadweight tonnage
- `loa`: Length overall
- `beam`: Boca da embarcação
- `owner_partner`: Parceiro proprietário

### Partner (Parceiro)
Representa parceiros comerciais e suas relações.

**Campos principais:**
- `name`: Nome do parceiro
- `entity_type`: Tipo de entidade (HALCO, OFFTAKER, etc.)
- `vessels`: Embarcações de propriedade
- `enrollments`: Inscrições em produções

## Funcionalidades Avançadas

### Sistema de Auditoria
Todos os modelos incluem campos de auditoria automáticos:
- `created_at`: Data de criação
- `updated_at`: Data da última atualização
- `created_by`: Usuário que criou
- `updated_by`: Usuário que atualizou
- `deleted_at`: Data de exclusão (soft delete)
- `deleted_by`: Usuário que excluiu

### Validações de Negócio
- **Produção**: Apenas um cenário ativo por ano
- **Embarcação**: IMO único, validações de especificações
- **Parceiro**: Nome único, validações de tipo de entidade

### Hooks e Eventos
O sistema de repositórios suporta hooks para:
- `before_create`: Antes da criação
- `after_create`: Após a criação
- `before_update`: Antes da atualização
- `after_update`: Após a atualização
- `before_delete`: Antes da exclusão
- `after_delete`: Após a exclusão

### Otimização de Frota
Algoritmo de otimização para alocação de embarcações baseado em:
- Requisitos de capacidade
- Tipo de embarcação
- Disponibilidade
- Eficiência operacional

## Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `SECRET_KEY` | Chave secreta para JWT | 'dev' |
| `DATABASE_URL` | URL do banco de dados | 'sqlite:///app.db' |
| `DEBUG` | Modo debug | True |
| `PORT` | Porta da aplicação | 5000 |

### Configurações por Ambiente

#### Desenvolvimento
```python
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
```

#### Produção
```python
class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```

## Monitoramento e Logs

### Logging
O sistema inclui logging estruturado para:
- Requisições HTTP
- Operações de banco de dados
- Erros e exceções
- Eventos de autenticação
- Operações de negócio

### Health Checks
Endpoints de health check disponíveis:
- `GET /api/v1/auth/health` - Status do serviço de autenticação
- `GET /` - Status geral da aplicação

## Desenvolvimento

### Adicionando Novos Endpoints

1. **Criar o repositório** (se necessário):
```python
# app/repository/new_repository.py
from app.lib.repository.base import BaseRepository
from app.models.new_model import NewModel

class NewRepository(BaseRepository[NewModel]):
    def __init__(self):
        super().__init__(NewModel)
    
    def custom_method(self):
        # Implementar lógica específica
        pass
```

2. **Criar o service**:
```python
# app/services/new_service.py
from app.repository.new_repository import NewRepository

class NewService:
    def __init__(self):
        self.repo = NewRepository()
    
    def business_method(self):
        # Implementar lógica de negócio
        pass
```

3. **Criar a API**:
```python
# app/api/v1/resources/new_api.py
from flask import Blueprint
from app.services.new_service import NewService
from app.api.v1.utils import api_response, error_handler

bp = Blueprint('new_api', __name__, url_prefix='/new')
service = NewService()

@bp.route('', methods=['GET'])
@error_handler
def list_items():
    items = service.repo.get_active()
    return api_response(data={'items': items})
```

4. **Registrar o blueprint**:
```python
# app/api/v1/__init__.py
from .resources import new_api
api_v1.register_blueprint(new_api.bp)
```

### Executando Testes

```bash
# Instalar dependências de teste
pip install pytest pytest-cov

# Executar testes
pytest

# Executar com coverage
pytest --cov=app
```

### Migrações de Banco

```bash
# Criar nova migração
flask db migrate -m "Descrição da migração"

# Aplicar migrações
flask db upgrade

# Reverter migração
flask db downgrade
```

## Deployment

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "main.py"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/bauxita_erp
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=bauxita_erp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Produção
Para deployment em produção, considere:
- Usar PostgreSQL ao invés de SQLite
- Configurar HTTPS/SSL
- Implementar rate limiting
- Configurar logging para arquivo
- Usar servidor WSGI (Gunicorn)
- Implementar monitoramento (Prometheus/Grafana)

## Contribuição

### Padrões de Código
- Seguir PEP 8 para Python
- Usar type hints
- Documentar funções e classes
- Escrever testes para novas funcionalidades
- Manter cobertura de testes > 80%

### Processo de Contribuição
1. Fork o repositório
2. Crie uma branch para sua feature
3. Implemente as mudanças
4. Escreva testes
5. Execute os testes
6. Submeta um Pull Request

## Roadmap

### Versão 2.1
- [ ] Sistema de notificações
- [ ] Relatórios avançados
- [ ] Integração com sistemas externos
- [ ] Dashboard em tempo real

### Versão 2.2
- [ ] Mobile API
- [ ] Sistema de workflow
- [ ] Análise preditiva
- [ ] Integração com IoT

## Suporte

Para suporte técnico ou dúvidas sobre o sistema:

- **Documentação**: Este README e comentários no código
- **Issues**: Use o sistema de issues do repositório
- **Email**: suporte@bauxita-erp.com (exemplo)

## Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo LICENSE para detalhes.

---

**Desenvolvido por Manus AI**  
**Versão 2.0.0 - Agosto 2025**

