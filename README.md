# PySocketCommLib

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Development Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/Jhonattan-rocha/PySocketCommLib)

Uma biblioteca Python abrangente para comunicação de baixo nível via socket, oferecendo ferramentas para criar sistemas baseados em socket com suporte a WebSocket, servidores HTTP, ORM para banco de dados, sistemas de autenticação e criptografia.

## 🚀 Características

- **Servidores Assíncronos e com Threading**: Suporte completo para programação assíncrona e baseada em threads
- **WebSocket e HTTP**: Implementação de servidores WebSocket e HTTP
- **ORM Integrado**: Sistema ORM completo com suporte a múltiplos bancos de dados
- **Autenticação**: Sistema de autenticação flexível e extensível
- **Criptografia**: Suporte a criptografia AES, RSA e Fernet
- **Gerenciamento de Tarefas**: Sistema de gerenciamento de tarefas assíncronas
- **SSL/TLS**: Suporte completo a conexões seguras
- **Rate Limiting**: Controle de taxa de requisições
- **Sistema de Eventos**: Sistema de eventos para comunicação entre componentes

## 📦 Instalação

```bash
pip install PySocketCommLib
```

Para desenvolvimento:
```bash
pip install PySocketCommLib[dev]
```

## 🏁 Início Rápido

### Servidor Assíncrono Básico

```python
import asyncio
from PySocketCommLib import AsyncServer, Server_ops

async def main():
    # Configuração do servidor
    options = Server_ops(
        host="localhost",
        port=8080,
        auth_method="none"
    )
    
    # Criar e iniciar servidor
    server = AsyncServer(options)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Cliente Assíncrono

```python
import asyncio
from PySocketCommLib import AsyncClient, Client_ops

async def main():
    options = Client_ops(
        host="localhost",
        port=8080
    )
    
    client = AsyncClient(options)
    await client.connect()
    
    # Enviar mensagem
    await client.send_message(b"Hello, Server!")
    
    # Receber resposta
    response = await client.receive_message()
    print(f"Resposta: {response}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Usando o ORM

```python
from PySocketCommLib import BaseModel, IntegerField, TextField, DateTimeField
from PySocketCommLib.ORM.dialetecs.sqlite import SqliteConnection

# Definir modelo
class User(BaseModel):
    id = IntegerField(primary_key=True)
    name = TextField(nullable=False)
    email = TextField(unique=True)
    created_at = DateTimeField()
    
    class Meta:
        table_name = "users"

# Configurar conexão
connection = SqliteConnection("database.db")
User.set_connection(connection)

# Criar tabela
User.create_table()

# Inserir dados
user = User(name="João", email="joao@example.com")
user.save()

# Consultar dados
users = User.filter(name="João")
print(users)
```

## 🏗️ Arquitetura

### Estrutura de Diretórios

```
PySocketCommLib/
├── Abstracts/          # Classes abstratas base
├── Auth/              # Sistema de autenticação
├── Client/            # Implementações de cliente
├── Server/            # Implementações de servidor
├── Crypt/             # Sistema de criptografia
├── ORM/               # Object-Relational Mapping
├── Events/            # Sistema de eventos
├── Files/             # Manipulação de arquivos
├── Options/           # Configurações
├── Protocols/         # Protocolos de comunicação
├── TaskManager/       # Gerenciamento de tarefas
└── tests/             # Testes unitários
```

### Componentes Principais

#### Servidores
- **AsyncServer**: Servidor assíncrono usando asyncio
- **ThreadServer**: Servidor baseado em threads

#### Clientes
- **AsyncClient**: Cliente assíncrono
- **ThreadClient**: Cliente baseado em threads

#### ORM
- **BaseModel**: Classe base para modelos
- **Campos**: IntegerField, TextField, FloatField, BooleanField, etc.
- **Consultas**: Select, Insert, Update, Delete
- **Dialetos**: Suporte a SQLite, PostgreSQL, MySQL

#### Autenticação
- **NoAuth**: Sem autenticação
- **SimpleTokenAuth**: Autenticação por token simples

#### Criptografia
- **AESCrypt**: Criptografia AES
- **RSACrypt**: Criptografia RSA
- **FernetCrypt**: Criptografia Fernet

## 📚 Documentação Detalhada

### Configuração de SSL/TLS

```python
from PySocketCommLib import Server_ops, SSLContextOps
import ssl

# Configurar SSL
ssl_ops = SSLContextOps(
    CERTFILE="server.crt",
    KEYFILE="server.key",
    ssl_context=ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
)

options = Server_ops(
    host="localhost",
    port=8443,
    ssl_ops=ssl_ops
)
```

### Sistema de Eventos

```python
from PySocketCommLib import Events

events = Events()

# Registrar callback
@events.on("user_connected")
def on_user_connected(user_id):
    print(f"Usuário {user_id} conectado")

# Emitir evento
events.emit("user_connected", "user123")
```

### Rate Limiting

```python
from PySocketCommLib.Server import AsyncTokenBucket

# Criar bucket de tokens (10 tokens, 1 token por segundo)
bucket = AsyncTokenBucket(capacity=10, refill_rate=1.0)

# Verificar se pode processar requisição
if await bucket.consume(1):
    # Processar requisição
    pass
else:
    # Rate limit excedido
    pass
```

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Executar com cobertura
pytest --cov=PySocketCommLib

# Executar testes específicos
pytest tests/test_server.py
```

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

### Padrões de Código

```bash
# Formatação com black
black PySocketCommLib/

# Linting com flake8
flake8 PySocketCommLib/

# Type checking com mypy
mypy PySocketCommLib/
```

## 📋 Roadmap

- [ ] Suporte a HTTP/2
- [ ] WebSocket com compressão
- [ ] Sistema de plugins
- [ ] Métricas e monitoramento
- [ ] Suporte a Redis para cache
- [ ] Migrations automáticas no ORM
- [ ] Interface web de administração
- [ ] Documentação interativa

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👨‍💻 Autor

**Jhonattan Rocha**
- GitHub: [@Jhonattan-rocha](https://github.com/Jhonattan-rocha)
- Email: jhonattan246rocha@gmail.com

## 🙏 Agradecimentos

- Comunidade Python pela inspiração
- Contribuidores do projeto
- Usuários que reportam bugs e sugerem melhorias

---

⭐ Se este projeto te ajudou, considere dar uma estrela no GitHub!