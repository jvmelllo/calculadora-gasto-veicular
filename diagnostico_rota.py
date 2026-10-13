"""Mede onde o tempo está indo na consulta de rota. Rode: python diagnostico_rota.py"""
import socket
import time

import rota as r

HOST = "api.openrouteservice.org"


def medir(nome, funcao):
    t0 = time.perf_counter()
    try:
        resultado = funcao()
        print(f"{nome:<28} {time.perf_counter() - t0:6.2f} s  ok")
        return resultado
    except Exception as e:  # noqa: BLE001 - é um script de diagnóstico
        print(f"{nome:<28} {time.perf_counter() - t0:6.2f} s  ERRO: {e}")
        return None


print("Teste de rede e do serviço de rotas (cada etapa espera até 8 s, como no app)\n")
medir("DNS (IPv4+IPv6)", lambda: socket.getaddrinfo(HOST, 443))
medir("conexão TCP 443", lambda: socket.create_connection((HOST, 443), timeout=8).close())
chave = r.carregar_chave()
origem = medir("busca do endereço (origem)", lambda: r.geocodificar("jacarepaguá, rio de janeiro", chave))
destino = medir("busca do endereço (destino)", lambda: r.geocodificar("praça mauá, centro, rio de janeiro", chave))
if origem and destino:
    rota = medir("cálculo da rota", lambda: r.calcular_rota(origem, destino, chave))
    if rota:
        print(f"\nRota: {rota.distancia_km:.1f} km, {r.formatar_duracao(rota.duracao_min)}")
