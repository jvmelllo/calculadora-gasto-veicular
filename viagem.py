"""Custo de uma viagem: endereço de destino -> distância, tempo e combustível.

Exemplos:
    python viagem.py "Praça Mauá, Centro, Rio de Janeiro" --origem "Rua X, 100, Tijuca" --preco 6,50
    python viagem.py "Praça Mauá, Centro, Rio de Janeiro" --preco 6,50 --ida-volta
    python viagem.py --salvar-origem "Rua X, 100, Tijuca"

O endereço de origem é salvo em config.local.json (não vai para o Git).
O tempo é uma estimativa sem trânsito.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import combustivel as comb
import rota as r

ARQUIVO_CONFIG = Path(__file__).with_name("config.local.json")


def carregar_config(arquivo: Path = ARQUIVO_CONFIG) -> dict:
    try:
        return json.loads(Path(arquivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar_origem(texto: str, arquivo: Path = ARQUIVO_CONFIG) -> None:
    config = carregar_config(arquivo)
    config["origem"] = texto
    Path(arquivo).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Distância, tempo e custo de combustível até um destino no RJ.")
    p.add_argument("destino", nargs="?", help="endereço de destino (ou 'lat, lon')")
    p.add_argument("--origem", help="endereço de partida (se omitido, usa o salvo)")
    p.add_argument("--salvar-origem", metavar="ENDERECO", help="salva o endereço de partida padrão e sai")
    p.add_argument("--preco", help="preço por litro, em R$")
    p.add_argument("--consumo", help="consumo em km/l (tem prioridade sobre --veiculo)")
    p.add_argument("--veiculo", default=comb.VEICULO_PADRAO, help="id do veículo em veiculos.json")
    p.add_argument("--percurso", choices=comb.PERCURSOS, default="misto", help="tipo de percurso")
    p.add_argument("--ida-volta", action="store_true", help="considera ida e volta")
    return p


def main(argv=None, requisitar=None, arquivo_config: Path = ARQUIVO_CONFIG) -> int:
    args = montar_parser().parse_args(argv)
    try:
        if args.salvar_origem:
            salvar_origem(args.salvar_origem, arquivo_config)
            print(f"Origem salva em {Path(arquivo_config).name}.")
            return 0

        interativo = sys.stdin.isatty()

        destino_txt = args.destino
        if not destino_txt:
            if not interativo:
                raise comb.EntradaInvalida("Informe o endereço de destino.")
            destino_txt = comb.perguntar("Endereço de destino: ")

        origem_txt = args.origem or carregar_config(arquivo_config).get("origem")
        if not origem_txt:
            if not interativo:
                raise comb.EntradaInvalida(
                    "Informe --origem (ou salve com --salvar-origem 'seu endereço')."
                )
            origem_txt = comb.perguntar("Endereço de partida: ")
            if comb.perguntar("Salvar como partida padrão? [S/n]: ").lower() not in ("n", "nao", "não"):
                salvar_origem(origem_txt, arquivo_config)

        preco = args.preco
        if preco is None:
            if not interativo:
                raise comb.EntradaInvalida("Informe --preco (preço por litro).")
            preco = comb.perguntar("Preço por litro (R$): ")

        if args.consumo is not None:
            consumo, origem_consumo = comb.ler_numero(args.consumo), "informado"
        else:
            veiculos = comb.carregar_veiculos()
            if args.veiculo not in veiculos:
                raise comb.EntradaInvalida(f"Veículo {args.veiculo!r} não encontrado em veiculos.json.")
            veiculo = veiculos[args.veiculo]
            consumo = comb.consumo_do_veiculo(veiculo, args.percurso)
            origem_consumo = f"{veiculo['nome']}, {args.percurso}"

        chave = r.carregar_chave()
        local_origem = r.geocodificar(origem_txt, chave, requisitar)
        local_destino = r.geocodificar(destino_txt, chave, requisitar)
        trajeto = r.calcular_rota(local_origem, local_destino, chave, requisitar)

        resultado = comb.calcular_combustivel(trajeto.distancia_km, consumo, preco, args.ida_volta)
    except (comb.EntradaInvalida, r.ErroRota) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    duracao = trajeto.duracao_min * (2 if args.ida_volta else 1)
    rotulo_tempo = "Tempo (ida e volta)" if args.ida_volta else "Tempo de viagem"
    print("Viagem")
    print(f"  Origem ................. {local_origem.nome}")
    print(f"  Destino ................ {local_destino.nome}")
    print(f"  Distância (só ida) ..... {comb.numero_br(trajeto.distancia_km, 1)} km")
    print(f"  {rotulo_tempo:<22}. {r.formatar_duracao(duracao)}  (estimativa sem trânsito)")
    print()
    print(comb.resumo(resultado, origem_consumo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
