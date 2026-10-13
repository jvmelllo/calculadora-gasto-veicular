"""Pedágios no trajeto — passo 3 do projeto.

- carregar_pracas(): lê o cadastro em pedagios.json (tarifas com fonte e data de vigência).
- total_pedagio(): soma as tarifas das praças que você escolheu.

Só usa a biblioteca padrão do Python.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ARQUIVO_PEDAGIOS = Path(__file__).with_name("pedagios.json")


@dataclass(frozen=True)
class Praca:
    id: str
    nome: str
    rodovia: str
    concessionaria: str | None
    tarifa: float | None  # None = a confirmar (não entra no cálculo)
    tarifa_fim_de_semana: float | None
    vigencia: str | None
    fonte: str
    confianca: str
    observacao: str
    um_sentido: bool = False  # True = só cobra em um sentido (na ida e volta, conta uma vez)


def carregar_pracas(caminho: Path = ARQUIVO_PEDAGIOS) -> list[Praca]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return [
        Praca(
            id=p["id"],
            nome=p["nome"],
            rodovia=p.get("rodovia", ""),
            concessionaria=p.get("concessionaria"),
            tarifa=p.get("tarifa"),
            tarifa_fim_de_semana=p.get("tarifa_fim_de_semana"),
            vigencia=p.get("vigencia"),
            fonte=p.get("fonte", ""),
            confianca=p.get("confianca", ""),
            observacao=p.get("observacao", ""),
            um_sentido=bool(p.get("um_sentido", False)),
        )
        for p in dados["pracas"]
    ]


def tarifa_aplicavel(praca: Praca, fim_de_semana: bool = False) -> float | None:
    """Tarifa do dia: usa a de fim de semana/feriado só quando a praça tem uma."""
    if fim_de_semana and praca.tarifa_fim_de_semana is not None:
        return praca.tarifa_fim_de_semana
    return praca.tarifa


def passagens_da_viagem(praca: Praca, ida_e_volta: bool) -> int:
    """Quantas vezes a viagem paga a praça: 2 na ida e volta, ou 1 se ela só cobra em um sentido."""
    return 2 if ida_e_volta and not praca.um_sentido else 1


def total_pedagio(pracas, fim_de_semana: bool = False, ida_e_volta: bool = False) -> float:
    """Soma das tarifas; praças sem tarifa confirmada são ignoradas."""
    total = 0.0
    for p in pracas:
        tarifa = tarifa_aplicavel(p, fim_de_semana)
        if tarifa is not None:
            total += tarifa * passagens_da_viagem(p, ida_e_volta)
    return total
