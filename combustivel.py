"""Calculadora de combustível — passo 1 do projeto "Custo de Rota".

Uso rápido:
    python combustivel.py --km 40 --consumo 10 --preco 6,50
    python combustivel.py --km 40 --percurso cidade --preco 6,50 --ida-volta
    python combustivel.py                 # modo interativo (pergunta km e preço)
    python combustivel.py --listar-veiculos

As funções de cálculo não fazem entrada/saída. Assim elas podem ser
reaproveitadas depois pelo site (Vercel) e pelas próximas etapas
(rota, pedágio, estacionamento).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ARQUIVO_VEICULOS = Path(__file__).with_name("veiculos.json")
# Veículos incluídos pelo usuário na interface ficam separados do cadastro base.
ARQUIVO_EXTRAS = Path(__file__).with_name("veiculos_extras.json")
CONSUMO_MAXIMO_PLAUSIVEL_KM_L = 60
VEICULO_PADRAO = "fiesta-1.6-powershift-2014"
PERCURSOS = ("cidade", "estrada", "misto")
UNIDADES_CONSUMO = ("km/l", "l/100 km")


class EntradaInvalida(ValueError):
    """Valor informado que não pode ser usado no cálculo."""


# --------------------------------------------------------------------------
# Leitura de números e veículos
# --------------------------------------------------------------------------
def ler_numero(valor) -> float:
    """Converte '6,50', '1.234,56', 'R$ 6,50' ou 6.5 em float."""
    if isinstance(valor, bool):
        raise EntradaInvalida(f"Número inválido: {valor!r}")
    if isinstance(valor, (int, float)):
        numero = float(valor)
    else:
        texto = str(valor).strip().lower().replace("r$", "").replace(" ", "")
        if "," in texto:  # formato brasileiro: ponto = milhar, vírgula = decimal
            texto = texto.replace(".", "").replace(",", ".")
        try:
            numero = float(texto)
        except ValueError:
            raise EntradaInvalida(f"Número inválido: {valor!r}") from None
    if not math.isfinite(numero):
        raise EntradaInvalida(f"Número inválido: {valor!r}")
    return numero


def carregar_veiculos(caminho: Path = ARQUIVO_VEICULOS, extras: Path | None = ARQUIVO_EXTRAS) -> dict:
    """Cadastro base + veículos incluídos pelo usuário (o cadastro base tem prioridade no id)."""
    with open(caminho, encoding="utf-8") as arquivo:
        veiculos = json.load(arquivo)
    if extras and Path(extras).exists():
        try:
            adicionais = json.loads(Path(extras).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            adicionais = {}
        for id_, dados in adicionais.items():
            veiculos.setdefault(id_, dados)
    return veiculos


def _slug(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")


def criar_veiculo(
    nome, consumo_cidade, consumo_estrada, existentes=(), fonte: str = "Informado pelo usuário."
) -> tuple[str, dict]:
    """Valida os dados e devolve (id, registro) prontos para salvar."""
    nome = " ".join(str(nome).split())
    if not nome:
        raise EntradaInvalida("Informe o nome do veículo.")
    cidade, estrada = ler_numero(consumo_cidade), ler_numero(consumo_estrada)
    if cidade <= 0 or estrada <= 0:
        raise EntradaInvalida("Os consumos precisam ser maiores que zero.")
    if max(cidade, estrada) > CONSUMO_MAXIMO_PLAUSIVEL_KM_L:
        raise EntradaInvalida(
            f"Consumo acima de {CONSUMO_MAXIMO_PLAUSIVEL_KM_L} km/l parece um erro de digitação."
        )
    base = _slug(nome) or "veiculo"
    id_, n = base, 2
    while id_ in existentes:
        id_, n = f"{base}-{n}", n + 1
    return id_, {
        "nome": nome,
        "combustivel": "gasolina",
        "consumo_cidade_km_l": cidade,
        "consumo_estrada_km_l": estrada,
        "fonte": fonte,
    }


def salvar_veiculo(id_: str, dados: dict, extras: Path = ARQUIVO_EXTRAS) -> None:
    try:
        atuais = json.loads(Path(extras).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        atuais = {}
    atuais[id_] = dados
    Path(extras).write_text(json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8")


def consumo_do_veiculo(veiculo: dict, percurso: str = "misto") -> float:
    """Consumo em km/l para o tipo de percurso (cidade, estrada ou misto).

    Misto assume a mesma distância na cidade e na estrada, o que dá a
    média harmônica dos dois consumos.
    """
    percurso = percurso.lower()
    cidade = float(veiculo["consumo_cidade_km_l"])
    estrada = float(veiculo["consumo_estrada_km_l"])
    if percurso == "cidade":
        return cidade
    if percurso == "estrada":
        return estrada
    if percurso == "misto":
        return 2 / (1 / cidade + 1 / estrada)
    raise EntradaInvalida(f"Percurso desconhecido: {percurso!r} (use {', '.join(PERCURSOS)})")


def consumo_para_km_l(valor, unidade: str = "km/l") -> float:
    """Converte um consumo digitado (km/l ou l/100 km) para km/l."""
    numero = ler_numero(valor)
    if numero <= 0:
        raise EntradaInvalida("O consumo precisa ser maior que zero.")
    if unidade == "km/l":
        return numero
    if unidade == "l/100 km":
        return 100 / numero
    raise EntradaInvalida(f"Unidade desconhecida: {unidade!r} (use {', '.join(UNIDADES_CONSUMO)})")


def consumo_na_unidade(km_l: float, unidade: str = "km/l") -> float:
    """Mostra um consumo em km/l na unidade pedida (km/l ou l/100 km)."""
    if km_l <= 0:
        raise EntradaInvalida("O consumo precisa ser maior que zero.")
    if unidade == "km/l":
        return km_l
    if unidade == "l/100 km":
        return 100 / km_l
    raise EntradaInvalida(f"Unidade desconhecida: {unidade!r} (use {', '.join(UNIDADES_CONSUMO)})")


# --------------------------------------------------------------------------
# Cálculo
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoCombustivel:
    distancia_km: float  # distância total considerada (já dobrada na ida e volta)
    consumo_km_l: float
    preco_litro: float
    litros: float
    custo: float
    custo_por_km: float


def calcular_combustivel(
    distancia_km, consumo_km_l, preco_litro, ida_e_volta: bool = False
) -> ResultadoCombustivel:
    distancia = ler_numero(distancia_km)
    consumo = ler_numero(consumo_km_l)
    preco = ler_numero(preco_litro)

    if distancia < 0:
        raise EntradaInvalida("A distância não pode ser negativa.")
    if consumo <= 0:
        raise EntradaInvalida("O consumo precisa ser maior que zero.")
    if preco < 0:
        raise EntradaInvalida("O preço por litro não pode ser negativo.")

    if ida_e_volta:
        distancia *= 2

    litros = distancia / consumo
    return ResultadoCombustivel(
        distancia_km=distancia,
        consumo_km_l=consumo,
        preco_litro=preco,
        litros=litros,
        custo=litros * preco,
        custo_por_km=preco / consumo,
    )


# --------------------------------------------------------------------------
# Formatação (pt-BR)
# --------------------------------------------------------------------------
def numero_br(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(valor: float) -> str:
    return "R$ " + numero_br(valor)


def resumo(r: ResultadoCombustivel, origem_consumo: str) -> str:
    return "\n".join(
        [
            "Cálculo do Combustível",
            f"  Distância total ........ {numero_br(r.distancia_km, 1)} km",
            f"  Consumo ................ {numero_br(r.consumo_km_l)} km/l  ({origem_consumo})",
            f"  Preço por litro ........ {brl(r.preco_litro)}",
            "  ----------------------------------",
            f"  Litros necessários ..... {numero_br(r.litros)} l",
            f"  Custo do combustível ... {brl(r.custo)}",
            f"  Custo por km ........... {brl(r.custo_por_km)}",
        ]
    )


# --------------------------------------------------------------------------
# Terminal
# --------------------------------------------------------------------------
def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Calculadora de combustível (km/l).")
    p.add_argument("--km", help="distância percorrida, em km")
    p.add_argument("--consumo", help="consumo médio em km/l (tem prioridade sobre --veiculo)")
    p.add_argument("--veiculo", default=VEICULO_PADRAO, help="id do veículo em veiculos.json")
    p.add_argument("--percurso", choices=PERCURSOS, default="misto", help="tipo de percurso")
    p.add_argument("--preco", help="preço por litro, em R$")
    p.add_argument("--ida-volta", action="store_true", help="dobra a distância informada")
    p.add_argument("--listar-veiculos", action="store_true", help="mostra os veículos cadastrados")
    return p


def perguntar(texto: str) -> str:
    try:
        return input(texto).strip()
    except EOFError:
        raise EntradaInvalida("Entrada encerrada antes de completar os dados.") from None


def main(argv=None) -> int:
    args = montar_parser().parse_args(argv)
    try:
        veiculos = carregar_veiculos()

        if args.listar_veiculos:
            for id_, v in veiculos.items():
                print(f"{id_}: {v['nome']}")
            return 0

        interativo = args.km is None or args.preco is None
        if interativo and not sys.stdin.isatty():
            raise EntradaInvalida(
                "Informe --km e --preco (ou rode em um terminal para o modo interativo)."
            )

        distancia = args.km if args.km is not None else perguntar("Distância percorrida (km): ")

        if args.consumo is not None:
            consumo = ler_numero(args.consumo)
            origem = "informado"
        else:
            if args.veiculo not in veiculos:
                raise EntradaInvalida(
                    f"Veículo {args.veiculo!r} não encontrado. Use --listar-veiculos."
                )
            veiculo = veiculos[args.veiculo]
            consumo = consumo_do_veiculo(veiculo, args.percurso)
            origem = f"{veiculo['nome']}, {args.percurso}"

        preco = args.preco if args.preco is not None else perguntar("Preço por litro (R$): ")

        ida_volta = args.ida_volta
        if interativo and not ida_volta:
            ida_volta = perguntar("Ida e volta? [s/N]: ").lower() in ("s", "sim")

        resultado = calcular_combustivel(distancia, consumo, preco, ida_volta)
    except EntradaInvalida as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    print(resumo(resultado, origem))
    return 0


if __name__ == "__main__":
    sys.exit(main())
