#!/usr/bin/env python3
"""
PySocketCommLib CLI — ferramenta de linha de comando.

Comandos disponíveis:
    pysocketcomm info                        Informações sobre a biblioteca
    pysocketcomm db migrate       [opts]     Aplicar migrations pendentes
    pysocketcomm db rollback      [opts]     Reverter N migrations
    pysocketcomm db status        [opts]     Listar migrations aplicadas/pendentes
    pysocketcomm db new-migration NAME       Criar arquivo de migration vazio
    pysocketcomm db makemigrations [opts]    Gerar migrations a partir dos modelos

Opções de conexão (para comandos db):
    --driver    sqlite | psql | mysql   (padrão: sqlite)
    --database  Nome/caminho do banco   (obrigatório)
    --host      Host do servidor        (padrão: localhost)
    --port      Porta                   (padrão: dialeto-específico)
    --user      Usuário
    --password  Senha
    --dir       Diretório de migrations (padrão: ./migrations)
"""

import sys
import argparse
from pathlib import Path

# Garante que o pacote é importável quando executado diretamente
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

__version__ = "0.2.0"


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def _make_connection(args):
    """Cria e conecta ao banco de dados de acordo com --driver."""
    driver = getattr(args, 'driver', 'sqlite')

    if driver == 'sqlite':
        from PySocketCommLib.ORM.dialetecs.sqlite import SqliteConnection
        conn = SqliteConnection(database=args.database)

    elif driver == 'psql':
        from PySocketCommLib.ORM.dialetecs.psql import PsqlConnection
        port = getattr(args, 'port', None) or 5432
        conn = PsqlConnection(
            host=getattr(args, 'host', 'localhost'),
            port=int(port),
            user=getattr(args, 'user', None),
            password=getattr(args, 'password', None),
            database=args.database,
        )

    elif driver == 'mysql':
        from PySocketCommLib.ORM.dialetecs.mysql import MySQLConnection
        port = getattr(args, 'port', None) or 3306
        conn = MySQLConnection(
            host=getattr(args, 'host', 'localhost'),
            port=int(port),
            user=getattr(args, 'user', None),
            password=getattr(args, 'password', None),
            database=args.database,
        )

    else:
        print(f"Driver desconhecido: '{driver}'. Use sqlite, psql ou mysql.")
        sys.exit(1)

    if not conn.connect():
        print(f"Falha ao conectar ao banco '{args.database}' usando driver '{driver}'.")
        sys.exit(1)

    return conn


# ---------------------------------------------------------------------------
# Comando: info
# ---------------------------------------------------------------------------

def cmd_info(_args):
    from PySocketCommLib import __version__ as lib_version
    print(f"PySocketCommLib {lib_version}")
    print()
    print("Componentes disponíveis:")
    components = [
        ("Servidores",    "AsyncServer, ThreadServer"),
        ("Clientes",      "AsyncClient, ThreadClient"),
        ("HTTP",          "AsyncHttpServerProtocol (ASGI)"),
        ("Auth",          "NoAuth, SimpleTokenAuth, HttpAuth, SimpleTokenHttpAuth"),
        ("Pipeline",      "CodecMiddleware, CryptMiddleware, EventsMiddleware"),
        ("ORM",           "BaseModel + dialetos: SQLite, PostgreSQL, MySQL"),
        ("Migrations",    "MigrationManager, CreateTable, AddColumn, …"),
        ("Pool",          "ConnectionPool, AsyncConnectionPool"),
        ("Monitoring",    "ServerMonitor, MetricsCollector, HealthChecker"),
        ("Criptografia",  "Crypt (AES + RSA)"),
        ("Arquivos",      "File (gzip, transfer)"),
        ("Eventos",       "Events"),
    ]
    col = max(len(c[0]) for c in components) + 2
    for name, detail in components:
        print(f"  {name:<{col}}{detail}")
    return 0


# ---------------------------------------------------------------------------
# Comando: db
# ---------------------------------------------------------------------------

def _db_connection_args(parser):
    """Adiciona argumentos de conexão a um subparser."""
    parser.add_argument('--driver',   default='sqlite',
                        choices=['sqlite', 'psql', 'mysql'],
                        help='Driver do banco de dados (padrão: sqlite)')
    parser.add_argument('--database', required=True,
                        help='Nome do banco ou caminho do arquivo SQLite')
    parser.add_argument('--host',     default='localhost',
                        help='Host do servidor (padrão: localhost)')
    parser.add_argument('--port',     type=int, default=None,
                        help='Porta (padrão: 5432 psql / 3306 mysql)')
    parser.add_argument('--user',     default=None, help='Usuário')
    parser.add_argument('--password', default=None, help='Senha')
    parser.add_argument('--dir',      default='migrations',
                        help='Diretório de migrations (padrão: ./migrations)')


def cmd_db_migrate(args):
    from PySocketCommLib.ORM.migrations import MigrationManager
    conn = _make_connection(args)
    try:
        manager = MigrationManager(conn, migrations_dir=args.dir)
        migrations = manager.load_migrations_from_directory()
        if not migrations:
            print(f"Nenhum arquivo de migration encontrado em '{args.dir}'.")
            return 0
        manager.apply_migrations(migrations)
        return 0
    finally:
        conn.disconnect()


def cmd_db_rollback(args):
    from PySocketCommLib.ORM.migrations import MigrationManager
    conn = _make_connection(args)
    try:
        manager = MigrationManager(conn, migrations_dir=args.dir)
        migrations = manager.load_migrations_from_directory()
        manager.rollback_migrations(migrations, count=args.count)
        return 0
    finally:
        conn.disconnect()


def cmd_db_status(args):
    from PySocketCommLib.ORM.migrations import MigrationManager
    conn = _make_connection(args)
    try:
        manager = MigrationManager(conn, migrations_dir=args.dir)
        migrations = manager.load_migrations_from_directory()
        applied = set(manager.get_applied_migrations())
        pending = [m for m in migrations if m.name not in applied]

        print(f"Migrations aplicadas ({len(applied)}):")
        for name in sorted(applied):
            print(f"  [x] {name}")

        print(f"\nMigrations pendentes ({len(pending)}):")
        for m in pending:
            print(f"  [ ] {m.name}")

        return 0
    finally:
        conn.disconnect()


def cmd_db_makemigrations(args):
    """
    Introspect the live DB schema, compare against declared models, and
    write a new migration file with the detected differences.

    --app  Dotted import path to a module whose models should be registered
           (e.g. ``myproject.models``).  May be repeated.
           The module only needs to be imported — all BaseModel subclasses
           are auto-registered via __init_subclass__.
    --name  Name for the generated migration (default: auto).
    --drop-tables   Also emit DropTable for tables with no matching model.
    --drop-columns  Also emit DropColumn for columns with no matching field.
    """
    import importlib
    from datetime import datetime
    from PySocketCommLib.ORM.migrations.generator import generate_operations
    from PySocketCommLib.ORM.migrations import MigrationManager
    from PySocketCommLib.ORM.models.model import BaseModel

    # Import requested app modules so their models register themselves.
    for app in (args.apps or []):
        try:
            importlib.import_module(app)
        except ImportError as exc:
            print(f"Aviso: não foi possível importar '{app}': {exc}")

    conn = _make_connection(args)
    try:
        models = list(BaseModel._registry)
        if not models:
            print(
                "Nenhum modelo encontrado. Use --app myapp.models para importar seus modelos."
            )
            return 1

        ops = generate_operations(
            conn,
            models,
            drop_tables=args.drop_tables,
            drop_columns=args.drop_columns,
        )

        if not ops:
            print("Nenhuma diferença detectada. Schema já está atualizado.")
            return 0

        print(f"{len(ops)} operação(ões) detectada(s):")
        for op in ops:
            print(f"  • {type(op).__name__}")

        # Write migration file
        migration_name = args.name or f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        manager = MigrationManager(conn, migrations_dir=args.dir)
        filepath = manager.create_migration_file(migration_name)

        # Patch the generated file with the actual operations
        _patch_migration_file(filepath, ops, migration_name)

        print(f"Migration criada: {filepath}")
        return 0
    finally:
        conn.disconnect()


def _patch_migration_file(filepath: str, ops, migration_name: str) -> None:
    """
    Replace the placeholder ``operations = []`` in a generated migration file
    with repr strings for each detected operation.
    """
    from pathlib import Path

    lines = []
    for op in ops:
        cls = type(op).__name__
        if cls == "CreateTable":
            lines.append(
                f"    # CreateTable('{op.table_name}', {{...}}),"
            )
            lines.append(
                f"    # TODO: preencha os campos da tabela '{op.table_name}'"
            )
        elif cls == "AddColumn":
            lines.append(
                f"    # AddColumn('{op.table_name}', '{op.column_name}', <FieldType>()),"
            )
        elif cls == "DropColumn":
            lines.append(
                f"    DropColumn('{op.table_name}', '{op.column_name}'),"
            )
        elif cls == "AlterColumn":
            lines.append(
                f"    # AlterColumn('{op.table_name}', '{op.column_name}', old_field, new_field),"
            )
        elif cls == "DropTable":
            lines.append(f"    DropTable('{op.table_name}'),")
        else:
            lines.append(f"    # {cls}(...)  — preencha manualmente")

    ops_block = "\n".join(lines) if lines else "    # Sem operações detectadas"

    content = Path(filepath).read_text(encoding="utf-8")
    content = content.replace(
        "operations = [\n"
        "    # Adicione suas operações aqui. Exemplos:\n"
        "    # CreateTable(\"users\", {\n"
        "    #     \"id\": IntegerField(primary_key=True),\n"
        "    #     \"name\": TextField(nullable=False),\n"
        "    #     \"email\": TextField(unique=True),\n"
        "    # }),\n"
        "    # AddColumn(\"users\", \"phone\", TextField(nullable=True)),\n"
        "]",
        f"operations = [\n{ops_block}\n]",
    )
    Path(filepath).write_text(content, encoding="utf-8")


def cmd_db_new_migration(args):
    from PySocketCommLib.ORM.migrations import MigrationManager
    from PySocketCommLib.ORM.abstracts.connection_types import Connection

    # MigrationManager só precisa do diretório para criar o arquivo,
    # mas o construtor exige uma conexão para criar a tabela de controle.
    # Usamos a conexão apenas se --database for fornecido.
    if args.database:
        conn = _make_connection(args)
        try:
            manager = MigrationManager(conn, migrations_dir=args.dir)
            filepath = manager.create_migration_file(args.migration_name)
        finally:
            conn.disconnect()
    else:
        # Sem conexão: cria o arquivo diretamente
        from datetime import datetime
        mig_dir = Path(args.dir)
        mig_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = mig_dir / f"{timestamp}_{args.migration_name}.py"
        content = f'''"""Migration: {args.migration_name}

Generated: {datetime.now().isoformat()}
"""

from PySocketCommLib.ORM.migrations.operations import (
    CreateTable, DropTable, AddColumn, DropColumn,
    RenameColumn, AlterColumn, RunSQL,
)
from PySocketCommLib.ORM.migrations.migration import Migration
from PySocketCommLib.ORM.abstracts.field_types import (
    IntegerField, TextField, FloatField, BooleanField,
    DateTimeField, DecimalField, ForeignKeyField,
)

operations = [
    # Adicione suas operações aqui.
]

dependencies = []

migration = Migration("{args.migration_name}", operations, dependencies)
'''
        filepath.write_text(content, encoding='utf-8')
        print(f"[migration] Arquivo criado: {filepath}")

    return 0


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='pysocketcomm',
        description='PySocketCommLib — ferramenta de linha de comando',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--version', action='version',
                        version=f'PySocketCommLib {__version__}')

    sub = parser.add_subparsers(dest='command', metavar='COMMAND')

    # info
    sub.add_parser('info', help='Informações sobre a biblioteca')

    # db
    db_parser = sub.add_parser('db', help='Gerenciamento de banco de dados')
    db_sub = db_parser.add_subparsers(dest='db_command', metavar='DB_COMMAND')

    # db migrate
    p = db_sub.add_parser('migrate', help='Aplicar migrations pendentes')
    _db_connection_args(p)

    # db rollback
    p = db_sub.add_parser('rollback', help='Reverter N migrations')
    _db_connection_args(p)
    p.add_argument('--count', type=int, default=1,
                   help='Número de migrations a reverter (padrão: 1)')

    # db status
    p = db_sub.add_parser('status', help='Mostrar status das migrations')
    _db_connection_args(p)

    # db new-migration
    p = db_sub.add_parser('new-migration', help='Criar arquivo de migration vazio')
    p.add_argument('migration_name', help='Nome da migration')
    p.add_argument('--dir', default='migrations',
                   help='Diretório de migrations (padrão: ./migrations)')
    p.add_argument('--driver',   default='sqlite',
                   choices=['sqlite', 'psql', 'mysql'])
    p.add_argument('--database', default=None,
                   help='Banco para registrar a migration (opcional)')
    p.add_argument('--host',     default='localhost')
    p.add_argument('--port',     type=int, default=None)
    p.add_argument('--user',     default=None)
    p.add_argument('--password', default=None)

    # db makemigrations
    p = db_sub.add_parser(
        'makemigrations',
        help='Gerar migration automática comparando modelos com o banco atual',
    )
    _db_connection_args(p)
    p.add_argument(
        '--app', dest='apps', action='append', metavar='MODULE',
        help='Módulo Python cujos modelos devem ser importados (pode repetir)',
    )
    p.add_argument(
        '--name', default=None,
        help='Nome da migration gerada (padrão: auto_YYYYMMDD_HHMMSS)',
    )
    p.add_argument(
        '--drop-tables', action='store_true', default=False,
        help='Incluir DropTable para tabelas sem modelo correspondente',
    )
    p.add_argument(
        '--drop-columns', action='store_true', default=False,
        help='Incluir DropColumn para colunas sem campo correspondente',
    )

    return parser


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == 'info':
            return cmd_info(args)

        if args.command == 'db':
            if not args.db_command:
                # mostra ajuda do subgrupo db
                parser.parse_args(['db', '--help'])
                return 0
            dispatch = {
                'migrate':        cmd_db_migrate,
                'rollback':       cmd_db_rollback,
                'status':         cmd_db_status,
                'new-migration':  cmd_db_new_migration,
                'makemigrations': cmd_db_makemigrations,
            }
            handler = dispatch.get(args.db_command)
            if handler:
                return handler(args)
            print(f"Subcomando db desconhecido: '{args.db_command}'")
            return 1

        print(f"Comando desconhecido: '{args.command}'")
        return 1

    except KeyboardInterrupt:
        print("\nOperação cancelada.")
        return 1
    except Exception as e:
        print(f"Erro: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
