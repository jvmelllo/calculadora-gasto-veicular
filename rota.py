"""Distância e tempo entre dois endereços do RJ — passo 2 do projeto.

Usa o OpenRouteService (https://openrouteservice.org). Só depende da
biblioteca padrão do Python, então não precisa de `pip install`.

A chave de API fica no arquivo `.env` (ou na variável de ambiente
ORS_API_KEY). Nunca coloque a chave direto no código.

As funções recebem `requisitar` como parâmetro opcional. Os testes usam
isso para simular o serviço, e o site pode trocar o transporte depois.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://api.openrouteservice.org"
PASTA = Path(__file__).resolve().parent
ARQUIVO_ENV = PASTA / ".env"
VARIAVEL_CHAVE = "ORS_API_KEY"
CHAVE_MODELO = "cole_sua_chave_aqui"
TIMEOUT_SEGUNDOS = 8  # serviço lento? desiste logo e usa a reserva
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Caixa que cobre o estado do RJ (lon/lat) e ponto de foco no centro da capital.
# Os resultados da busca ficam restritos à caixa e priorizam o que está perto do foco.
RJ_LON_MIN, RJ_LON_MAX = -44.9, -40.9
RJ_LAT_MIN, RJ_LAT_MAX = -23.4, -20.7
FOCO_LON, FOCO_LAT = -43.1729, -22.9068

_PADRAO_COORDENADAS = re.compile(r"^\s*(-?\d{1,2}\.\d+)\s*[,;]\s*(-?\d{1,3}\.\d+)\s*$")


class ErroRota(Exception):
    """Falha ao obter a rota (chave, rede, endereço, cota...)."""


@dataclass(frozen=True)
class Local:
    nome: str
    lon: float
    lat: float


@dataclass(frozen=True)
class Rota:
    distancia_km: float
    duracao_min: float


# --------------------------------------------------------------------------
# Chave de API
# --------------------------------------------------------------------------
def carregar_chave(arquivo_env: Path = ARQUIVO_ENV, ambiente=None) -> str:
    ambiente = os.environ if ambiente is None else ambiente
    chave = str(ambiente.get(VARIAVEL_CHAVE, "")).strip()

    if not chave and Path(arquivo_env).exists():
        # utf-8-sig: o Bloco de Notas do Windows pode salvar com BOM
        for linha in Path(arquivo_env).read_text(encoding="utf-8-sig").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            nome, _, valor = linha.partition("=")
            if nome.strip() == VARIAVEL_CHAVE:
                chave = valor.strip().strip('"').strip("'")

    if not chave or chave == CHAVE_MODELO:
        raise ErroRota(
            f"Chave de API não encontrada. Crie o arquivo .env (copie de .env.example) "
            f"e preencha {VARIAVEL_CHAVE}=sua_chave. Veja o README.md."
        )
    return chave


# --------------------------------------------------------------------------
# Transporte HTTP (substituível nos testes)
# --------------------------------------------------------------------------
def _mensagem_do_erro(corpo: bytes) -> str:
    try:
        dados = json.loads(corpo.decode("utf-8", errors="replace"))
    except ValueError:
        return ""
    erro = dados.get("error") if isinstance(dados, dict) else None
    if isinstance(erro, dict):
        return str(erro.get("message", ""))
    return str(erro or "")


def _http(metodo: str, url: str, *, params=None, corpo=None, cabecalhos=None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    cab = {"Accept": "application/json", **(cabecalhos or {})}
    if dados is not None:
        cab["Content-Type"] = "application/json; charset=utf-8"

    pedido = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
    # As mensagens de erro abaixo nunca incluem a URL, porque ela pode conter a chave.
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = _mensagem_do_erro(e.read())
        if e.code in (401, 403):
            raise ErroRota("Chave de API recusada. Confira ORS_API_KEY no arquivo .env.") from None
        if e.code == 429:
            raise ErroRota(
                "Limite de consultas do plano gratuito atingido. Tente de novo mais tarde."
            ) from None
        if e.code in (400, 404):
            raise ErroRota(f"O serviço não conseguiu traçar a rota: {detalhe or e.code}") from None
        raise ErroRota(f"Erro {e.code} no serviço de rotas. {detalhe}".strip()) from None
    except urllib.error.URLError as e:
        raise ErroRota(f"Sem conexão com o serviço de rotas ({e.reason}).") from None
    except TimeoutError:
        raise ErroRota("O serviço de rotas demorou demais para responder.") from None
    except ValueError:
        raise ErroRota("Resposta inválida do serviço de rotas.") from None


# --------------------------------------------------------------------------
# Endereço -> coordenadas
# --------------------------------------------------------------------------
def _coordenadas(texto: str):
    """Aceita 'lat, lon' com ponto decimal, ex.: -22.9068, -43.1729."""
    m = _PADRAO_COORDENADAS.match(texto)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ErroRota(f"Coordenadas fora do intervalo válido: {texto!r}")
    return lat, lon


def geocodificar(texto: str, chave: str, requisitar=None) -> Local:
    texto = (texto or "").strip()
    if not texto:
        raise ErroRota("Informe um endereço.")

    coord = _coordenadas(texto)
    if coord:
        lat, lon = coord
        return Local(f"{lat:.5f}, {lon:.5f}", lon, lat)

    requisitar = requisitar or _http
    try:
        dados = requisitar(
            "GET",
            f"{BASE_URL}/geocode/search",
            params={
                "api_key": chave,
                "text": texto,
                "size": 1,
                "boundary.rect.min_lon": RJ_LON_MIN,
                "boundary.rect.min_lat": RJ_LAT_MIN,
                "boundary.rect.max_lon": RJ_LON_MAX,
                "boundary.rect.max_lat": RJ_LAT_MAX,
                "focus.point.lon": FOCO_LON,
                "focus.point.lat": FOCO_LAT,
            },
        )
    except ErroRota as erro_ors:
        # Serviço de endereços fora do ar (502, timeout...): tenta o Nominatim, do OpenStreetMap.
        try:
            return _geocodificar_nominatim(texto, requisitar)
        except ErroRota:
            raise erro_ors from None
    try:
        item = dados["features"][0]
        lon, lat = item["geometry"]["coordinates"][:2]
        nome = item.get("properties", {}).get("label") or texto
    except (KeyError, IndexError, TypeError, ValueError):
        raise ErroRota(
            f"Endereço não encontrado no RJ: {texto!r}. Tente incluir o bairro e a cidade, "
            f"ou informe as coordenadas como 'lat, lon'."
        ) from None
    return Local(str(nome), float(lon), float(lat))


def _geocodificar_nominatim(texto: str, requisitar) -> Local:
    """Busca de reserva. Política de uso do Nominatim: identificar o app e no máximo 1 consulta por segundo."""
    dados = requisitar(
        "GET",
        NOMINATIM_URL,
        params={
            "q": texto, "format": "jsonv2", "limit": 1, "countrycodes": "br",
            "viewbox": f"{RJ_LON_MIN},{RJ_LAT_MAX},{RJ_LON_MAX},{RJ_LAT_MIN}", "bounded": 1,
        },
        cabecalhos={"User-Agent": "calculadora-gasto-veicular/1.0 (uso pessoal)"},
    )
    try:
        item = dados[0]
        return Local(str(item.get("display_name") or texto), float(item["lon"]), float(item["lat"]))
    except (KeyError, IndexError, TypeError, ValueError):
        raise ErroRota(f"Endereço não encontrado no RJ: {texto!r}.") from None


# --------------------------------------------------------------------------
# Rota
# --------------------------------------------------------------------------
def calcular_rota(origem: Local, destino: Local, chave: str, requisitar=None) -> Rota:
    requisitar = requisitar or _http
    try:
        dados = requisitar(
            "POST",
            f"{BASE_URL}/v2/directions/driving-car",
            corpo={
                "coordinates": [[origem.lon, origem.lat], [destino.lon, destino.lat]],
                "instructions": False,  # só precisamos de distância e tempo: a resposta fica bem menor
            },
            cabecalhos={"Authorization": chave},
        )
    except ErroRota as erro_ors:
        # Serviço fora do ar (502, timeout...): tenta o servidor público do OSRM (OpenStreetMap).
        # Chave recusada ou cota esgotada não passam por aqui para o usuário ver o motivo real.
        if "Chave de API recusada" in str(erro_ors) or "Limite de consultas" in str(erro_ors):
            raise
        try:
            return _rota_osrm(origem, destino, requisitar)
        except ErroRota:
            raise erro_ors from None
    try:
        primeira = dados["routes"][0]
        resumo = primeira["summary"]
        metros = float(resumo["distance"])
        segundos = float(resumo["duration"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ErroRota("Resposta inesperada do serviço de rotas.") from None
    return Rota(distancia_km=metros / 1000, duracao_min=segundos / 60)


def _rota_osrm(origem: Local, destino: Local, requisitar) -> Rota:
    dados = requisitar(
        "GET",
        f"{OSRM_URL}/{origem.lon},{origem.lat};{destino.lon},{destino.lat}",
        params={"overview": "false"},
        cabecalhos={"User-Agent": "calculadora-gasto-veicular/1.0 (uso pessoal)"},
    )
    try:
        primeira = dados["routes"][0]
        return Rota(distancia_km=float(primeira["distance"]) / 1000, duracao_min=float(primeira["duration"]) / 60)
    except (KeyError, IndexError, TypeError, ValueError):
        raise ErroRota("Resposta inesperada do serviço de rotas.") from None


def formatar_duracao(minutos: float) -> str:
    total = int(round(minutos))
    horas, resto = divmod(total, 60)
    return f"{horas} h {resto:02d} min" if horas else f"{resto} min"
