"""Interface web (Streamlit) da calculadora de gasto veicular.

Para abrir:
    python -m streamlit run app.py

Reaproveita combustivel.py (cálculo) e rota.py (endereço -> distância e tempo).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import combustivel as comb
import pedagio
import rota as r
import viagem as v

st.set_page_config(page_title="Calculadora de gasto veicular", page_icon="⛽", layout="centered")

st.markdown(
    """
    <style>
      footer, #MainMenu { visibility: hidden; }
      /* some a dica "Press Enter to submit form" dentro dos campos */
      [data-testid="InputInstructions"] { display: none !important; }
      h1 { font-size: 1.9rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Ao clicar em Origem/Destino, o texto existente fica selecionado: o que você digitar o substitui.
SELECIONAR_AO_FOCAR = """
<script>
(function () {
  try {
    var doc = window.parent.document;
    if (doc.__selecionarAoFocar) return;
    doc.__selecionarAoFocar = true;
    var rotulos = ["Origem", "Destino"];
    var recemFocado = null;
    function alvo(el) {
      return el && el.tagName === "INPUT" && rotulos.indexOf(el.getAttribute("aria-label")) !== -1;
    }
    doc.addEventListener("focusin", function (e) {
      if (!alvo(e.target)) return;
      var el = e.target;
      var textoInicial = el.value;
      recemFocado = el;
      el.select();
      // Reforço após o clique, mas só se você ainda não digitou nada.
      setTimeout(function () { if (el.value === textoInicial) el.select(); }, 0);
    });
    // Soltar o mouse logo após o foco colocaria o cursor no texto e desfaria a seleção.
    doc.addEventListener("mouseup", function (e) {
      if (recemFocado && e.target === recemFocado) e.preventDefault();
      recemFocado = null;
    }, true);
  } catch (e) {}
})();
</script>
"""

ss = st.session_state


def _carregar_veiculos() -> dict:
    return comb.carregar_veiculos(comb.ARQUIVO_VEICULOS, comb.ARQUIVO_EXTRAS)


VEICULOS = _carregar_veiculos()
PRACAS = pedagio.carregar_pracas()
PRACAS_COM_TARIFA = {x.id: x for x in PRACAS if x.tarifa is not None}


# --------------------------------------------------------------------------
# Estado e callbacks
# Os campos numéricos só aceitam valores "na grade" do passo (ex.: passo 0,01 não aceita 12,526).
# Por isso tudo que a página preenche sozinha é arredondado para o passo do campo.
# --------------------------------------------------------------------------
def _consumo_do_cadastro_km_l() -> float:
    return comb.consumo_do_veiculo(VEICULOS[ss.veiculo], ss.percurso)


def _preencher_consumo() -> None:
    """Veículo ou percurso mudou: volta o consumo para o valor do cadastro."""
    ss.consumo = round(comb.consumo_na_unidade(_consumo_do_cadastro_km_l(), ss.unidade), 2)


def _trocar_unidade() -> None:
    """Unidade mudou: converte o número que está na tela (100/x vale nos dois sentidos)."""
    if ss.consumo > 0:
        ss.consumo = round(100 / ss.consumo, 2)


def _adicionar_veiculo() -> None:
    """Roda ao clicar em 'Incluir veículo' (antes de a página ser redesenhada)."""
    global VEICULOS
    try:
        id_, dados = comb.criar_veiculo(
            ss.novo_nome, ss.novo_cidade, ss.novo_estrada, existentes=VEICULOS.keys()
        )
        comb.salvar_veiculo(id_, dados, comb.ARQUIVO_EXTRAS)
    except comb.EntradaInvalida as erro:
        ss.msg_veiculo = ("erro", str(erro))
        return
    except OSError as erro:
        ss.msg_veiculo = ("erro", f"Não foi possível salvar o veículo: {erro}")
        return
    VEICULOS = _carregar_veiculos()
    ss.veiculo = id_
    _preencher_consumo()
    ss.novo_nome = ""
    ss.msg_veiculo = ("ok", f"{dados['nome']} incluído e selecionado.")


if "inicializado" not in ss:
    ss.veiculo = comb.VEICULO_PADRAO if comb.VEICULO_PADRAO in VEICULOS else next(iter(VEICULOS))
    ss.percurso = "misto"
    ss.unidade = "km/l"
    ss.consumo = round(_consumo_do_cadastro_km_l(), 2)
    ss.distancia = 0.0
    ss.preco = 6.50  # valor de exemplo: ajuste conforme o posto
    ss.ida_volta = False
    ss.origem_txt = ""
    ss.destino_txt = ""
    ss.lembrar = False
    ss.rota = None
    ss.pracas_sel = []
    ss.fim_de_semana = False
    ss.novo_nome = ""
    ss.novo_cidade = 10.0
    ss.novo_estrada = 12.0
    ss.inicializado = True


@st.cache_data(ttl=3600, show_spinner=False)
def consultar_rota(origem: str, destino: str):
    """Guarda por 1 h o resultado de cada par de endereços, para poupar a cota gratuita."""
    chave = r.carregar_chave()
    local_origem = r.geocodificar(origem, chave)
    local_destino = r.geocodificar(destino, chave)
    return local_origem, local_destino, r.calcular_rota(local_origem, local_destino, chave)


# --------------------------------------------------------------------------
# Página
# --------------------------------------------------------------------------
st.title("Calculadora de gasto veicular")
st.caption("Rio de Janeiro · distância e tempo pela rota, custo pelo consumo do seu carro")

# --- Rota -----------------------------------------------------------------
with st.form("form_rota"):
    st.subheader("Rota")
    col_origem, col_destino = st.columns(2)
    col_origem.text_input(
        "Origem", key="origem_txt", placeholder="Ex.: Rua Visconde de Pirajá, 500, Ipanema"
    )
    col_destino.text_input("Destino", key="destino_txt", placeholder="Ex.: Praça Mauá, Centro")
    st.checkbox(
        "Lembrar esta origem neste computador", key="lembrar",
        help="Se você deixar a origem em branco, usamos a origem salva.",
    )
    enviar = st.form_submit_button("Calcular rota", type="primary")

if enviar:
    origem = ss.origem_txt.strip() or v.carregar_config(v.ARQUIVO_CONFIG).get("origem", "").strip()
    destino = ss.destino_txt.strip()
    if not origem or not destino:
        st.warning("Preencha a origem e o destino.")
    else:
        try:
            with st.spinner("Calculando a rota..."):
                resultado_rota = consultar_rota(origem, destino)
        except r.ErroRota as erro:
            ss.rota = None
            st.error(str(erro))
        else:
            ss.rota = resultado_rota
            ss.distancia = round(float(resultado_rota[2].distancia_km), 1)
            if ss.lembrar:
                v.salvar_origem(origem, v.ARQUIVO_CONFIG)

if ss.rota:
    local_origem, local_destino, trajeto = ss.rota
    st.success(f"{local_origem.nome}  →  {local_destino.nome}")
    with st.expander("Ver no mapa"):
        st.map(
            pd.DataFrame(
                {
                    "lat": [local_origem.lat, local_destino.lat],
                    "lon": [local_origem.lon, local_destino.lon],
                }
            )
        )

# --- Cálculo do combustível ----------------------------------------------
with st.container(border=True):
    st.subheader("Cálculo do Combustível")

    col_dist, col_cons, col_preco = st.columns(3)
    col_dist.number_input(
        "Distância percorrida (km)", min_value=0.0, step=0.1, format="%.1f", key="distancia",
        help="Preenchida pela rota, mas você pode digitar qualquer valor.",
    )
    with col_cons:
        campo_consumo, campo_unidade = st.columns([3, 2])
        campo_consumo.number_input(
            "Consumo médio", min_value=0.01, step=0.01, format="%.2f", key="consumo"
        )
        campo_unidade.selectbox(
            "Unidade", comb.UNIDADES_CONSUMO, key="unidade", on_change=_trocar_unidade
        )
    col_preco.number_input(
        "Preço por litro (R$)", min_value=0.0, step=0.01, format="%.2f", key="preco",
        help="Valor de exemplo: troque pelo preço do posto.",
    )

    col_veiculo, col_percurso, col_volta = st.columns([3, 2, 2])
    col_veiculo.selectbox(
        "Veículo", list(VEICULOS), format_func=lambda k: VEICULOS[k]["nome"],
        key="veiculo", on_change=_preencher_consumo,
    )
    col_percurso.selectbox(
        "Percurso", comb.PERCURSOS, format_func=str.capitalize,
        key="percurso", on_change=_preencher_consumo,
    )
    col_volta.toggle("Ida e volta", key="ida_volta")

    with st.expander("De onde vem o consumo do veículo?"):
        st.caption(VEICULOS[ss.veiculo].get("fonte", "Sem fonte registrada."))

    with st.expander("Incluir veículo"):
        st.markdown(
            "Procure o consumo (gasolina, em km/l), por exemplo na tabela PBE Veicular do "
            "[Inmetro](https://www.gov.br/inmetro), e preencha abaixo."
        )
        with st.form("form_veiculo"):
            st.text_input("Nome do veículo", key="novo_nome", placeholder="Ex.: Fiat Argo 1.3 2020")
            c_cidade, c_estrada = st.columns(2)
            c_cidade.number_input(
                "Consumo na cidade (km/l)", min_value=0.01, step=0.01, format="%.2f", key="novo_cidade"
            )
            c_estrada.number_input(
                "Consumo na estrada (km/l)", min_value=0.01, step=0.01, format="%.2f", key="novo_estrada"
            )
            st.form_submit_button("Incluir veículo", on_click=_adicionar_veiculo)
        resposta = ss.pop("msg_veiculo", None)
        if resposta:
            (st.success if resposta[0] == "ok" else st.error)(resposta[1])

# --- Pedágio --------------------------------------------------------------
ss.pracas_sel = [i for i in ss.pracas_sel if i in PRACAS_COM_TARIFA]  # ids que sumiram do cadastro
with st.container(border=True):
    st.subheader("Pedágio")
    col_pracas, col_fds = st.columns([4, 2])
    col_pracas.multiselect(
        "Praças no trajeto", list(PRACAS_COM_TARIFA), format_func=lambda i: PRACAS_COM_TARIFA[i].nome,
        key="pracas_sel", placeholder="Escolha as praças por onde você vai passar",
    )
    col_fds.toggle(
        "Fim de semana ou feriado", key="fim_de_semana",
        help="Algumas praças, como as da Rio–Santos, cobram mais nesses dias.",
    )

    selecionadas = [PRACAS_COM_TARIFA[i] for i in ss.pracas_sel]
    for x in selecionadas:
        if x.observacao:
            st.caption(f"**{x.nome}:** {x.observacao}")

    with st.expander("Tarifas cadastradas, fontes e vigência"):
        st.caption(
            "Carro de passeio (categoria 1). Tarifas mudam todo ano: confira a fonte antes de viajar. "
            "Praças \"a confirmar\" não entram no cálculo."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Praça": x.nome,
                        "Carro": comb.brl(x.tarifa) if x.tarifa is not None else "a confirmar",
                        "Fim de semana": comb.brl(x.tarifa_fim_de_semana) if x.tarifa_fim_de_semana is not None else "—",
                        "Cobra em": "um sentido" if x.um_sentido else "dois sentidos",
                        "Vigência": x.vigencia or "—",
                        "Fonte": x.fonte,
                        "Observação": x.observacao,
                    }
                    for x in PRACAS
                ]
            ),
            hide_index=True,
        )

valor_pedagio = pedagio.total_pedagio(selecionadas, ss.fim_de_semana, ss.ida_volta)

# --- Resultado ------------------------------------------------------------
with st.container(border=True):
    st.subheader("Resultado")
    if ss.distancia <= 0 and valor_pedagio <= 0:
        st.info("Calcule uma rota ou digite a distância para ver o custo.")
    else:
        try:
            km_l = comb.consumo_para_km_l(ss.consumo, ss.unidade)
            res = comb.calcular_combustivel(ss.distancia, km_l, ss.preco, ss.ida_volta)
        except comb.EntradaInvalida as erro:
            st.error(str(erro))
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Combustível", comb.brl(res.custo))
            m2.metric("Pedágio", comb.brl(valor_pedagio))
            m3.metric("Custo total da viagem", comb.brl(res.custo + valor_pedagio))

            m4, m5, m6, m7 = st.columns(4)
            m4.metric("Litros", f"{comb.numero_br(res.litros)} l")
            m5.metric("Custo por km", comb.brl(res.custo_por_km))
            m6.metric("Distância total", f"{comb.numero_br(res.distancia_km, 1)} km")
            # O tempo só vale enquanto a distância for a da rota calculada.
            if ss.rota and round(ss.distancia, 1) == round(ss.rota[2].distancia_km, 1):
                minutos = ss.rota[2].duracao_min * (2 if ss.ida_volta else 1)
                m7.metric("Tempo estimado", r.formatar_duracao(minutos), help="Sem trânsito.")
            if ss.ida_volta and selecionadas:
                st.caption(
                    "Pedágio de ida e volta: praças dos dois sentidos contam 2×; as que cobram "
                    "só em um sentido contam 1×."
                )
            st.caption("Tempo estimado sem trânsito. O consumo real do carro varia com o uso.")

components.html(SELECIONAR_AO_FOCAR, height=0)
