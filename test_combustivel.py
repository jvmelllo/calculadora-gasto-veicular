import contextlib
import io
import unittest

import combustivel as c


class LerNumero(unittest.TestCase):
    def test_formatos_brasileiros(self):
        self.assertEqual(c.ler_numero("6,50"), 6.5)
        self.assertEqual(c.ler_numero("R$ 6,50"), 6.5)
        self.assertEqual(c.ler_numero("1.234,56"), 1234.56)
        self.assertEqual(c.ler_numero("40"), 40.0)
        self.assertEqual(c.ler_numero(12), 12.0)

    def test_invalidos(self):
        for ruim in ("abc", "", "nan", "inf", None, True):
            with self.assertRaises(c.EntradaInvalida, msg=repr(ruim)):
                c.ler_numero(ruim)


class Calculo(unittest.TestCase):
    def test_exemplo_da_conversa(self):
        # 40 km, 10 km/l, R$ 6,00/l -> 4 litros -> R$ 24,00
        r = c.calcular_combustivel(40, 10, 6)
        self.assertAlmostEqual(r.litros, 4.0)
        self.assertAlmostEqual(r.custo, 24.0)
        self.assertAlmostEqual(r.custo_por_km, 0.6)

    def test_ida_e_volta_dobra_distancia(self):
        r = c.calcular_combustivel(40, 10, 6, ida_e_volta=True)
        self.assertAlmostEqual(r.distancia_km, 80.0)
        self.assertAlmostEqual(r.litros, 8.0)
        self.assertAlmostEqual(r.custo, 48.0)

    def test_aceita_texto(self):
        r = c.calcular_combustivel("40", "10", "6,50")
        self.assertAlmostEqual(r.custo, 26.0)

    def test_distancia_zero(self):
        r = c.calcular_combustivel(0, 10, 6)
        self.assertEqual(r.custo, 0.0)

    def test_entradas_invalidas(self):
        with self.assertRaises(c.EntradaInvalida):
            c.calcular_combustivel(-1, 10, 6)
        with self.assertRaises(c.EntradaInvalida):
            c.calcular_combustivel(40, 0, 6)
        with self.assertRaises(c.EntradaInvalida):
            c.calcular_combustivel(40, 10, -1)


class Veiculos(unittest.TestCase):
    def setUp(self):
        self.fiesta = c.carregar_veiculos()[c.VEICULO_PADRAO]

    def test_cidade_e_estrada(self):
        self.assertAlmostEqual(c.consumo_do_veiculo(self.fiesta, "cidade"), 11.4)
        self.assertAlmostEqual(c.consumo_do_veiculo(self.fiesta, "estrada"), 13.9)

    def test_misto_e_media_harmonica(self):
        misto = c.consumo_do_veiculo(self.fiesta, "misto")
        self.assertAlmostEqual(misto, 2 / (1 / 11.4 + 1 / 13.9))
        self.assertTrue(11.4 < misto < 13.9)

    def test_percurso_desconhecido(self):
        with self.assertRaises(c.EntradaInvalida):
            c.consumo_do_veiculo(self.fiesta, "montanha")


class IncluirVeiculo(unittest.TestCase):
    def test_criar_gera_id_sem_acentos_e_unico(self):
        id_, dados = c.criar_veiculo("  Fiat   Argo 1.3 Flex 2020 ", "12,3", 14.5)
        self.assertEqual(id_, "fiat-argo-1-3-flex-2020")
        self.assertEqual(dados["nome"], "Fiat Argo 1.3 Flex 2020")
        self.assertEqual(dados["consumo_cidade_km_l"], 12.3)
        id2, _ = c.criar_veiculo("Fiat Argo 1.3 Flex 2020", 12, 14, existentes={id_})
        self.assertEqual(id2, "fiat-argo-1-3-flex-2020-2")
        self.assertEqual(c.criar_veiculo("Citroën C3", 10, 12)[0], "citroen-c3")

    def test_validacoes(self):
        for args in (("", 10, 12), ("Carro", 0, 12), ("Carro", 10, -1), ("Carro", "abc", 12), ("Carro", 200, 12)):
            with self.assertRaises(c.EntradaInvalida, msg=repr(args)):
                c.criar_veiculo(*args)

    def test_salvar_e_carregar_junto_com_o_cadastro_base(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as pasta:
            extras = Path(pasta) / "extras.json"
            id_, dados = c.criar_veiculo("Meu Carro", 9.5, 12.0)
            c.salvar_veiculo(id_, dados, extras)
            c.salvar_veiculo("outro", {**dados, "nome": "Outro"}, extras)
            todos = c.carregar_veiculos(c.ARQUIVO_VEICULOS, extras)
            self.assertIn(c.VEICULO_PADRAO, todos)
            self.assertEqual(todos["meu-carro"]["consumo_cidade_km_l"], 9.5)
            self.assertIn("outro", todos)

    def test_extras_ausente_ou_corrompido_nao_quebra(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as pasta:
            extras = Path(pasta) / "extras.json"
            self.assertIn(c.VEICULO_PADRAO, c.carregar_veiculos(c.ARQUIVO_VEICULOS, extras))
            extras.write_text("{ isso nao e json", encoding="utf-8")
            self.assertIn(c.VEICULO_PADRAO, c.carregar_veiculos(c.ARQUIVO_VEICULOS, extras))

    def test_cadastro_base_tem_prioridade(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as pasta:
            extras = Path(pasta) / "extras.json"
            c.salvar_veiculo(c.VEICULO_PADRAO, {"nome": "Impostor"}, extras)
            todos = c.carregar_veiculos(c.ARQUIVO_VEICULOS, extras)
            self.assertNotEqual(todos[c.VEICULO_PADRAO]["nome"], "Impostor")


class UnidadesDeConsumo(unittest.TestCase):
    def test_para_km_l(self):
        self.assertAlmostEqual(c.consumo_para_km_l(12.5, "km/l"), 12.5)
        self.assertAlmostEqual(c.consumo_para_km_l(8, "l/100 km"), 12.5)
        self.assertAlmostEqual(c.consumo_para_km_l("8,0", "l/100 km"), 12.5)

    def test_na_unidade(self):
        self.assertAlmostEqual(c.consumo_na_unidade(12.5, "km/l"), 12.5)
        self.assertAlmostEqual(c.consumo_na_unidade(12.5, "l/100 km"), 8.0)

    def test_ida_e_volta_sem_perda(self):
        for km_l in (9.7, 12.53, 18.0):
            l100 = c.consumo_na_unidade(km_l, "l/100 km")
            self.assertAlmostEqual(c.consumo_para_km_l(l100, "l/100 km"), km_l)

    def test_invalidos(self):
        with self.assertRaises(c.EntradaInvalida):
            c.consumo_para_km_l(0, "km/l")
        with self.assertRaises(c.EntradaInvalida):
            c.consumo_para_km_l(10, "mpg")
        with self.assertRaises(c.EntradaInvalida):
            c.consumo_na_unidade(0, "km/l")


class Formatacao(unittest.TestCase):
    def test_brl(self):
        self.assertEqual(c.brl(24), "R$ 24,00")
        self.assertEqual(c.brl(1234.5), "R$ 1.234,50")


class Terminal(unittest.TestCase):
    def rodar(self, *argv):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = c.main(list(argv))
        return codigo, saida.getvalue()

    def test_com_consumo_manual(self):
        codigo, texto = self.rodar("--km", "40", "--consumo", "10", "--preco", "6")
        self.assertEqual(codigo, 0)
        self.assertIn("R$ 24,00", texto)
        self.assertIn("4,00 l", texto)

    def test_com_veiculo_cidade_ida_volta(self):
        codigo, texto = self.rodar(
            "--km", "40", "--percurso", "cidade", "--preco", "6", "--ida-volta"
        )
        self.assertEqual(codigo, 0)
        self.assertIn("80,0 km", texto)
        self.assertIn("Fiesta", texto)

    def test_erro_retorna_1(self):
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            codigo = c.main(["--km", "40", "--consumo", "0", "--preco", "6"])
        self.assertEqual(codigo, 1)
        self.assertIn("maior que zero", erro.getvalue())


if __name__ == "__main__":
    unittest.main()
