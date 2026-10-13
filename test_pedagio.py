import re
import unittest

import pedagio as p


def praca(id_="x", tarifa=5.0, fds=None, **extra):
    base = dict(
        id=id_, nome=id_, rodovia="", concessionaria=None, tarifa=tarifa, tarifa_fim_de_semana=fds,
        vigencia=None, fonte="", confianca="alta", observacao="",
    )
    base.update(extra)
    return p.Praca(**base)


class Totais(unittest.TestCase):
    def test_soma_simples_e_ida_e_volta(self):
        pracas = [praca("a", 6.60), praca("b", 4.00)]
        self.assertAlmostEqual(p.total_pedagio(pracas), 10.60)
        self.assertAlmostEqual(p.total_pedagio(pracas, ida_e_volta=True), 21.20)

    def test_praca_de_um_sentido_conta_uma_vez_na_ida_e_volta(self):
        pracas = [praca("a", 6.60, um_sentido=True), praca("b", 4.00)]
        self.assertAlmostEqual(p.total_pedagio(pracas), 10.60)
        self.assertAlmostEqual(p.total_pedagio(pracas, ida_e_volta=True), 6.60 + 8.00)

    def test_fim_de_semana_so_onde_existe(self):
        pracas = [praca("a", 4.90, fds=8.10), praca("b", 6.60)]
        self.assertAlmostEqual(p.total_pedagio(pracas, fim_de_semana=False), 11.50)
        self.assertAlmostEqual(p.total_pedagio(pracas, fim_de_semana=True), 14.70)

    def test_fim_de_semana_com_ida_e_volta(self):
        self.assertAlmostEqual(p.total_pedagio([praca("a", 4.90, fds=8.10)], True, True), 16.20)

    def test_sem_tarifa_nao_entra(self):
        self.assertAlmostEqual(p.total_pedagio([praca("a", None), praca("b", 3.0)]), 3.0)

    def test_vazio(self):
        self.assertEqual(p.total_pedagio([]), 0)


class CadastroReal(unittest.TestCase):
    """Protege o pedagios.json contra erro de digitação ao editar à mão."""

    @classmethod
    def setUpClass(cls):
        cls.pracas = p.carregar_pracas()
        cls.por_id = {x.id: x for x in cls.pracas}

    def test_ids_unicos_e_campos_obrigatorios(self):
        ids = [x.id for x in self.pracas]
        self.assertEqual(len(ids), len(set(ids)))
        for x in self.pracas:
            self.assertTrue(x.nome and x.fonte.startswith("https://"), x.id)
            self.assertIn(x.confianca, ("alta", "media", "pendente"), x.id)

    def test_tarifas_plausiveis_e_com_vigencia(self):
        for x in self.pracas:
            if x.tarifa is None:
                self.assertEqual(x.confianca, "pendente", x.id)
                continue
            self.assertTrue(1 <= x.tarifa <= 60, (x.id, x.tarifa))
            if x.tarifa_fim_de_semana is not None:
                self.assertGreaterEqual(x.tarifa_fim_de_semana, x.tarifa, x.id)
            self.assertTrue(re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", x.vigencia or ""), (x.id, x.vigencia))

    def test_praca_sem_tarifa_tem_motivo_na_observacao(self):
        for x in self.pracas:
            if x.tarifa is None:
                self.assertTrue(x.observacao.strip(), x.id)

    def test_pracas_de_um_sentido(self):
        self.assertTrue(self.por_id["ponte-rio-niteroi"].um_sentido)
        self.assertTrue(self.por_id["br101-norte-sao-goncalo"].um_sentido)
        self.assertFalse(self.por_id["dutra-itatiaia"].um_sentido)

    def test_total_da_ponte_na_ida_e_volta_conta_uma_vez(self):
        ponte = self.por_id["ponte-rio-niteroi"]
        self.assertAlmostEqual(p.total_pedagio([ponte], ida_e_volta=True), ponte.tarifa)


if __name__ == "__main__":
    unittest.main()
