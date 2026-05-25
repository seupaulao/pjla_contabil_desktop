"""
Módulo de funções de relatórios (portado de funcoes_relatorios.js).
Implementa: balancete, balanco_patrimonial, dre, dva, dfc.
Assume conexão sqlite3 (DB API). Retorna estruturas em dicionários/listas.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from typing import Any, Iterable, Optional

from pathlib import Path
import sqlite3

__all__ = [
    "balancete",
    "balanco_patrimonial",
    "dre",
    "dva",
    "dfc",
    "to_number",
]

DB_PATH = Path(__file__).parent.parent / "projeto_offline" / "contabilidade.db"
SCHEMA_PATH = Path(__file__).parent.parent / "scripts_banco_dados" / "banco_sqlite3_novo.sql"

EMPRESA_FIELDS = [
    ("cnpj", "CNPJ", True, "text"),
    ("nome", "NOME", True, "text"),
    ("uf", "UF", False, "text"),
    ("municipio", "MUNICIPIO", False, "text"),
    ("data_inicio", "DATA DE INICIO", False, "date"),
    ("data_fim", "DATA DE FIM", False, "date"),
]


# ============= DATABASE FUNCTIONS =============

def normalize_date(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("Use o formato DD/MM/AAAA.")


def display_date(value: Optional[str]) -> str:
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return value


def parse_decimal(value: str) -> float:
    text = value.strip()
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    if not text:
        raise ValueError("Informe um valor numérico.")
    amount = float(text)
    if amount <= 0:
        raise ValueError("Informe um valor maior que zero.")
    return amount


def format_currency(value: Any) -> str:
    amount = float(value or 0.0)
    text = f"{amount:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def connect_db() -> sqlite3.Connection:
    db_exists = DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_runtime_schema(conn, db_exists=db_exists)
    return conn


def ensure_runtime_schema(conn: sqlite3.Connection, db_exists: bool) -> None:
    if not db_exists and SCHEMA_PATH.exists():
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()

    columns = {row[1] for row in conn.execute("PRAGMA table_info(plano_contas)").fetchall()}
    extra_columns = {
        "grupo": "TEXT",
        "dre_grupo": "TEXT",
        "subgrupo": "TEXT",
        "fluxo_caixa_tipo": "TEXT",
    }
    for column_name, column_type in extra_columns.items():
        if column_name not in columns:
            conn.execute(f"ALTER TABLE plano_contas ADD COLUMN {column_name} {column_type}")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_lancamento_data ON lancamento(data)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lancamento_item_conta ON lancamento_item(conta_id)")
    conn.commit()


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchone()


def fetch_all(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def find_account(conn: sqlite3.Connection, empresa_id: int, raw_name: str) -> tuple[Optional[sqlite3.Row], str]:
    normalized = raw_name.strip()
    entry_type = "D"
    if normalized.lower().startswith("a "):
        entry_type = "C"
        normalized = normalized[2:].strip()

    account = fetch_one(
        conn,
        """
        SELECT *
        FROM plano_contas
        WHERE empresa_id = ?
          AND (UPPER(descricao) = UPPER(?) OR codigo = ? OR UPPER(descricao) LIKE UPPER(?))
        ORDER BY CASE
            WHEN UPPER(descricao) = UPPER(?) THEN 0
            WHEN codigo = ? THEN 1
            ELSE 2
        END,
        codigo
        LIMIT 1
        """,
        (empresa_id, normalized, normalized, f"%{normalized}%", normalized, normalized),
    )
    return account, entry_type


def fetch_lancamento(conn: sqlite3.Connection, empresa_id: int, lancamento_id: Any) -> Optional[sqlite3.Row]:
    return fetch_one(
        conn,
        """
        SELECT id, empresa_id, data, numero, historico
        FROM lancamento
        WHERE empresa_id = ? AND id = ?
        """,
        (empresa_id, lancamento_id),
    )


def fetch_lancamento_items(conn: sqlite3.Connection, lancamento_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        """
        SELECT li.id, li.conta_id, li.tipo, li.valor, li.historico, c.codigo, c.descricao
        FROM lancamento_item li
        JOIN plano_contas c ON c.id = li.conta_id
        WHERE li.lancamento_id = ?
        ORDER BY li.id
        """,
        (lancamento_id,),
    )


def summarize_items(items: list[dict[str, Any]]) -> tuple[float, float]:
    total_debitos = sum(item["valor"] for item in items if item["tipo"] == "D")
    total_creditos = sum(item["valor"] for item in items if item["tipo"] == "C")
    return total_debitos, total_creditos



def to_number(value: Any) -> float:
    """Converte valores nulos/strings para float com fallback 0."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    cur = db.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _optional_column(columns: set[str], column_name: str) -> str:
    if column_name in columns:
        return f"c.{column_name}"
    return f"NULL AS {column_name}"


def _empresa_filter(columns: set[str], empresa_id: Optional[int]) -> tuple[str, list[Any]]:
    if empresa_id is None:
        return "", []
    if "empresa_id" in columns:
        return "AND c.empresa_id = ?", [empresa_id]
    return "", []


def balancete(
    db: sqlite3.Connection,
    data_inicio: str,
    data_fim: str,
    empresa_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna lista de contas com debitos, creditos e saldo entre datas.
    data_inicio and data_fim devem ser strings compatíveis com o formato da coluna l.data.
    """
    columns = _table_columns(db, "plano_contas")
    empresa_filter, empresa_params = _empresa_filter(columns, empresa_id)

    sql = f"""
    SELECT 
      c.id,
      c.codigo,
      c.descricao,
      c.natureza,
      {_optional_column(columns, 'grupo')},
      {_optional_column(columns, 'dre_grupo')},
      {_optional_column(columns, 'subgrupo')},
      {_optional_column(columns, 'fluxo_caixa_tipo')},

      SUM(CASE WHEN li.tipo='D' THEN li.valor ELSE 0 END) AS debitos,
      SUM(CASE WHEN li.tipo='C' THEN li.valor ELSE 0 END) AS creditos

    FROM plano_contas c
    LEFT JOIN lancamento_item li ON li.conta_id = c.id
    LEFT JOIN lancamento l ON l.id = li.lancamento_id

    WHERE l.data BETWEEN ? AND ?
    {empresa_filter}
    GROUP BY c.id
    ORDER BY c.codigo
    """

    cur = db.cursor()
    cur.execute(sql, [data_inicio, data_fim, *empresa_params])
    rows = cur.fetchall()

    # Ensure rows are accessible by name if using row_factory; otherwise map manually
    cols = [d[0] for d in cur.description]

    result = []
    for row in rows:
        r = dict(zip(cols, row))
        deb = to_number(r.get("debitos"))
        cred = to_number(r.get("creditos"))

        natureza = r.get("natureza")
        if natureza == 'D':
            saldo = deb - cred
        else:
            saldo = cred - deb

        r["debitos"] = deb
        r["creditos"] = cred
        r["saldo"] = saldo

        result.append(r)

    return result


def balanco_patrimonial(
    db: sqlite3.Connection,
    data_inicio: str,
    data_fim: str,
    empresa_id: Optional[int] = None,
) -> Dict[str, Any]:
    dados = balancete(db, data_inicio, data_fim, empresa_id=empresa_id)

    ativo = []
    passivo = []
    pl = []

    for c in dados:
        if c.get("saldo") == 0:
            continue

        grupo = c.get("grupo")
        if grupo == 'ATIVO':
            ativo.append(c)
        elif grupo == 'PASSIVO':
            passivo.append(c)
        elif grupo == 'PL':
            pl.append(c)

    total_ativo = sum([to_number(i.get("saldo")) for i in ativo])
    total_passivo_pl = sum([to_number(i.get("saldo")) for i in (passivo + pl)])

    return {
        "ativo": ativo,
        "passivo": passivo,
        "patrimonio_liquido": pl,
        "total_ativo": total_ativo,
        "total_passivo_pl": total_passivo_pl,
    }


def dre(
    db: sqlite3.Connection,
    data_inicio: str,
    data_fim: str,
    empresa_id: Optional[int] = None,
) -> Dict[str, float]:
    dados = balancete(db, data_inicio, data_fim, empresa_id=empresa_id)

    grupos = {}
    for c in dados:
        chave = c.get("dre_grupo")
        if not chave:
            continue
        grupos[chave] = grupos.get(chave, 0.0) + to_number(c.get("saldo"))

    receita = to_number(grupos.get("RECEITA_BRUTA"))
    custo = to_number(grupos.get("CUSTO"))
    despesa = to_number(grupos.get("DESPESA_OPERACIONAL"))
    financeiro = to_number(grupos.get("RESULTADO_FINANCEIRO"))

    resultado = receita - custo - despesa + financeiro

    return {
        "receita": receita,
        "custo": custo,
        "despesa": despesa,
        "financeiro": financeiro,
        "resultado": resultado,
    }


def dva(
    db: sqlite3.Connection,
    data_inicio: str,
    data_fim: str,
    empresa_id: Optional[int] = None,
) -> Dict[str, Any]:
    dados = balancete(db, data_inicio, data_fim, empresa_id=empresa_id)

    receitas = 0.0
    insumos = 0.0
    pessoal = 0.0
    impostos = 0.0
    capital_terceiros = 0.0

    for c in dados:
        sub = c.get("subgrupo")
        if not sub:
            continue
        if sub == 'RECEITAS':
            receitas += to_number(c.get("saldo"))
        elif sub == 'INSUMOS':
            insumos += to_number(c.get("saldo"))
        elif sub == 'PESSOAL':
            pessoal += to_number(c.get("saldo"))
        elif sub == 'IMPOSTOS':
            impostos += to_number(c.get("saldo"))
        elif sub == 'CAPITAL_TERCEIROS':
            capital_terceiros += to_number(c.get("saldo"))

    valor_adicionado = receitas - insumos

    return {
        "receitas": receitas,
        "insumos": insumos,
        "valor_adicionado": valor_adicionado,
        "distribuicao": {
            "pessoal": pessoal,
            "impostos": impostos,
            "capital_terceiros": capital_terceiros,
        },
    }


def dfc(
    db: sqlite3.Connection,
    data_inicio: str,
    data_fim: str,
    empresa_id: Optional[int] = None,
) -> Dict[str, float]:
    dados = balancete(db, data_inicio, data_fim, empresa_id=empresa_id)

    operacional = 0.0
    investimento = 0.0
    financiamento = 0.0

    for c in dados:
        tipo = c.get("fluxo_caixa_tipo")
        if tipo == 'OPERACIONAL':
            operacional += to_number(c.get("saldo"))
        elif tipo == 'INVESTIMENTO':
            investimento += to_number(c.get("saldo"))
        elif tipo == 'FINANCIAMENTO':
            financiamento += to_number(c.get("saldo"))

    variacao_caixa = operacional + investimento + financiamento

    return {
        "operacional": operacional,
        "investimento": investimento,
        "financiamento": financiamento,
        "variacao_caixa": variacao_caixa,
    }
