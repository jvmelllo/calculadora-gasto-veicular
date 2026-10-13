import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import combustivel as comb
import rota as r
import viagem as v

CHAVE = "SEGREDO123"


def resposta_geo(label, lon, lat):
    return {"features": [{"geometry": {"coordinates": [lon, lat]}, "properties": {"label": label}}]}


def resposta_rota(metros, segundos):
    return {"routes": [{"summary": {"distance": metros, "duration": segundos}}]}


class ServicoFalso:
    """Simula a API: guarda as chamadas e devolve respostas prontas."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, metodo, url, *, params=None, corpo=None, cabecalhos=None):
        self.chamadas.append((metodo, url, params, corpo, cabecalhos))
        if "geocode" in url:
            if params["text"].lower().startswith("casa"):
                return resposta_geo("Casa, Tijuca, Rio de Janeiro", -43.24, -22.93)
            if params["text"].lower().startswith("centro"):
                return resposta_geo("Centro, Rio de Janeiro", -43.18, -22.90)
            return {"features": []}
        return resposta_rota(38200, 3120)  # 38,2 km, 52 min


class Chave(unittest.TestCase):
    def test_variavel_de_ambiente(self):
        self.assertEqual(r.carregar_chave(Path("nao-existe"), {"ORS_API_KEY": f" {CHAVE} "}), CHAVE)

    def test_arquivo_env_com_bom_e_aspas(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text('# comentário\n\nORS_API_KEY="abc123"\n', encoding="utf-8-sig")
            self.assertEqual(r.carregar_chave(env, {}), "abc123")

    def test_ausente_ou_modelo(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            with self.assertRaises(r.ErroRota):
                r.carregar_chave(env, {})
            env.write_text("ORS_API_KEY=cole_sua_chave_aqui\n", encoding="utf-8")
            with self.assertRaises(r.ErroRota):
                r.carregar_chave(env, {})


class Geocodificacao(unittest.TestCase):
    def test_le_coordenadas_na_ordem_lon_lat(self):
        loc = r.geocodificar("casa", CHAVE, ServicoFalso())
        self.assertEqual((loc.lon, loc.lat), (-43.24, -22.93))
        self.assertIn("Tijuca", loc.nome)

    def test_restringe_ao_rj(self):
        servico = ServicoFalso()
        r.geocodificar("casa", CHAVE, servico)
        _, url, params, _, _ = servico.chamadas[0]
        self.assertTrue(url.endswith("/geocode/search"))
        self.assertEqual(params["boundary.rect.min_lon"], r.RJ_LON_MIN)
        self.assertEqual(params["focus.point.lat"], r.FOCO_LAT)

    def test_sem_resultado(self):
        with self.assertRaises(r.ErroRota) as ctx:
            r.geocodificar("lugar nenhum", CHAVE, ServicoFalso())
        self.assertIn("não encontrado", str(ctx.exception))

    def test_coordenadas_diretas_nao_chamam_a_api(self):
        servico = ServicoFalso()
        loc = r.geocodificar("-22.9068, -43.1729", CHAVE, servico)
        self.assertEqual((loc.lat, loc.lon), (-22.9068, -43.1729))
        self.assertEqual(servico.chamadas, [])

    def test_texto_vazio(self):
        with self.assertRaises(r.ErroRota):
            r.geocodificar("   ", CHAVE, ServicoFalso())


class Rotas(unittest.TestCase):
    def test_converte_metros_e_segundos(self):
        o, d = r.Local("a", -43.24, -22.93), r.Local("b", -43.18, -22.90)
        servico = ServicoFalso()
        rota = r.calcular_rota(o, d, CHAVE, servico)
        self.assertAlmostEqual(rota.distancia_km, 38.2)
        self.assertAlmostEqual(rota.duracao_min, 52.0)
        metodo, url, _, corpo, cab = servico.chamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertTrue(url.endswith("/v2/directions/driving-car"))
        self.assertEqual(corpo["coordinates"], [[-43.24, -22.93], [-43.18, -22.90]])
        self.assertEqual(cab["Authorization"], CHAVE)

    def test_resposta_inesperada(self):
        o = d = r.Local("a", 0, 0)
        with self.assertRaises(r.ErroRota):
            r.calcular_rota(o, d, CHAVE, lambda *a, **k: {"routes": []})

    def test_formatar_duracao(self):
        self.assertEqual(r.formatar_duracao(52), "52 min")
        self.assertEqual(r.formatar_duracao(65.4), "1 h 05 min")
        self.assertEqual(r.formatar_duracao(120), "2 h 00 min")


class Http(unittest.TestCase):
    def erro_http(self, codigo, corpo=b'{"error":{"message":"detalhe"}}'):
        return urllib.error.HTTPError(
            f"https://x/?api_key={CHAVE}", codigo, "msg", {}, io.BytesIO(corpo)
        )

    def chamar_com(self, excecao):
        with mock.patch("urllib.request.urlopen", side_effect=excecao):
            with self.assertRaises(r.ErroRota) as ctx:
                r._http("GET", "https://x/", params={"api_key": CHAVE})
        return str(ctx.exception)

    def test_mapeia_erros_sem_vazar_a_chave(self):
        casos = {401: "Chave", 403: "Chave", 429: "Limite", 404: "detalhe", 500: "500"}
        for codigo, trecho in casos.items():
            msg = self.chamar_com(self.erro_http(codigo))
            self.assertIn(trecho, msg, codigo)
            self.assertNotIn(CHAVE, msg)

    def test_sem_rede(self):
        msg = self.chamar_com(urllib.error.URLError("sem internet"))
        self.assertIn("Sem conexão", msg)

    def test_resposta_nao_json(self):
        resposta = mock.MagicMock()
        resposta.__enter__.return_value.read.return_value = b"<html>"
        with mock.patch("urllib.request.urlopen", return_value=resposta):
            with self.assertRaises(r.ErroRota):
                r._http("GET", "https://x/")


class Viagem(unittest.TestCase):
    def rodar(self, *argv, servico=None):
        saida, erro = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as pasta, mock.patch.dict(
            os.environ, {"ORS_API_KEY": CHAVE}
        ), mock.patch("sys.stdin.isatty", return_value=False):
            config = Path(pasta) / "config.local.json"
            with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
                codigo = v.main(list(argv), requisitar=servico or ServicoFalso(), arquivo_config=config)
        return codigo, saida.getvalue(), erro.getvalue()

    def test_fluxo_completo(self):
        codigo, saida, _ = self.rodar(
            "centro", "--origem", "casa", "--preco", "6", "--consumo", "10"
        )
        self.assertEqual(codigo, 0)
        self.assertIn("38,2 km", saida)
        self.assertIn("52 min", saida)
        # 38,2 km / 10 km/l = 3,82 l * R$ 6,00 = R$ 22,92
        self.assertIn("R$ 22,92", saida)
        self.assertIn("Tijuca", saida)

    def test_ida_e_volta(self):
        codigo, saida, _ = self.rodar(
            "centro", "--origem", "casa", "--preco", "6", "--consumo", "10", "--ida-volta"
        )
        self.assertEqual(codigo, 0)
        self.assertIn("R$ 45,84", saida)
        self.assertIn("1 h 44 min", saida)

    def test_sem_origem_em_modo_nao_interativo(self):
        codigo, _, erro = self.rodar("centro", "--preco", "6")
        self.assertEqual(codigo, 1)
        self.assertIn("--origem", erro)

    def test_endereco_inexistente(self):
        codigo, _, erro = self.rodar("centro", "--origem", "lugar nenhum", "--preco", "6")
        self.assertEqual(codigo, 1)
        self.assertIn("não encontrado", erro)

    def test_salvar_origem_e_reutilizar(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = Path(pasta) / "config.local.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v.main(["--salvar-origem", "casa na Tijuca"], arquivo_config=config), 0)
            self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["origem"], "casa na Tijuca")
            self.assertEqual(v.carregar_config(config)["origem"], "casa na Tijuca")


class BuscaDeReserva(unittest.TestCase):
    def test_usa_nominatim_quando_o_ors_falha(self):
        chamadas = []

        def requisitar(metodo, url, **k):
            chamadas.append(url)
            if "openrouteservice" in url:
                raise r.ErroRota("Erro 502 no serviço de rotas.")
            return [{"display_name": "Praça Mauá, Centro", "lat": "-22.8963", "lon": "-43.1822"}]

        local = r.geocodificar("praça mauá", "k", requisitar)
        self.assertEqual((local.lat, local.lon), (-22.8963, -43.1822))
        self.assertEqual(len(chamadas), 2)

    def test_se_os_dois_falham_mostra_o_erro_do_ors(self):
        def requisitar(metodo, url, **k):
            raise r.ErroRota("Erro 502 no serviço de rotas." if "openrouteservice" in url else "outro")

        with self.assertRaisesRegex(r.ErroRota, "502"):
            r.geocodificar("x", "k", requisitar)

    def test_nao_usa_reserva_quando_o_ors_responde_sem_resultado(self):
        chamadas = []

        def requisitar(metodo, url, **k):
            chamadas.append(url)
            return {"features": []}

        with self.assertRaisesRegex(r.ErroRota, "não encontrado"):
            r.geocodificar("x", "k", requisitar)
        self.assertEqual(len(chamadas), 1)

    def test_reserva_sem_resultado(self):
        def requisitar(metodo, url, **k):
            if "openrouteservice" in url:
                raise r.ErroRota("Erro 502")
            return []

        with self.assertRaisesRegex(r.ErroRota, "502"):
            r.geocodificar("x", "k", requisitar)


class RotaDeReserva(unittest.TestCase):
    A = r.Local("a", -43.24, -22.93)
    B = r.Local("b", -43.18, -22.90)

    def test_usa_osrm_quando_o_ors_falha(self):
        urls = []

        def requisitar(metodo, url, **k):
            urls.append(url)
            if "openrouteservice" in url:
                raise r.ErroRota("Erro 502 no serviço de rotas.")
            return {"routes": [{"distance": 12500, "duration": 1500}]}

        rota = r.calcular_rota(self.A, self.B, "k", requisitar)
        self.assertAlmostEqual(rota.distancia_km, 12.5)
        self.assertAlmostEqual(rota.duracao_min, 25)
        self.assertIn("-43.24,-22.93;-43.18,-22.9", urls[1])

    def test_chave_recusada_nao_usa_reserva(self):
        def requisitar(metodo, url, **k):
            raise r.ErroRota("Chave de API recusada. Confira ORS_API_KEY no arquivo .env.")

        with self.assertRaisesRegex(r.ErroRota, "Chave"):
            r.calcular_rota(self.A, self.B, "k", requisitar)

    def test_se_os_dois_falham_mostra_o_erro_do_ors(self):
        def requisitar(metodo, url, **k):
            raise r.ErroRota("Erro 502 no serviço de rotas." if "openrouteservice" in url else "outro")

        with self.assertRaisesRegex(r.ErroRota, "502"):
            r.calcular_rota(self.A, self.B, "k", requisitar)


if __name__ == "__main__":
    unittest.main()
