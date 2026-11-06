# Calculadora de gasto veicular (RJ)

Digite o destino e descubra quanto custa a viagem de carro no Rio de Janeiro: **distância, tempo, combustível e pedágio**. O app vem configurado com um Ford Fiesta 1.6 PowerShift 2014 e aceita outros veículos.

<!-- Adicione aqui uma captura de tela do app: ![Tela do app](docs/tela.png) -->
<!-- Adicione aqui o link do app publicado: **[Abrir o app](https://...)** -->

## O que faz

- **Rota:** origem e destino em texto (ou coordenadas) viram distância e tempo estimado, sem trânsito.
- **Combustível:** custo pelo consumo do carro (cidade, estrada ou misto) e pelo preço do litro. Aceita km/l ou l/100 km e calcula ida e volta.
- **Pedágio:** você escolhe as praças do trajeto, e a tarifa entra no total. Cada praça tem fonte e data de vigência, e as que cobram em um só sentido contam uma vez na ida e volta.
- **Veículos:** base com o Fiesta 2014 e a opção de incluir outros carros pelo consumo.
- **Três formas de usar:** interface web (Streamlit), terminal e planilha Excel.

## Como rodar

Precisa de Python (testado com 3.12).

1. Instale a dependência e copie o arquivo de configuração:

       pip install -r requirements.txt
       copy .env.example .env        (no Mac/Linux: cp .env.example .env)

2. Crie uma conta gratuita em [openrouteservice.org](https://openrouteservice.org), gere uma chave de API e cole no `.env`, no lugar de `cole_sua_chave_aqui`. O plano gratuito permite 2.000 rotas e 1.000 buscas de endereço por dia.

3. Abra a interface:

       python -m streamlit run app.py

   O navegador abre em `http://localhost:8501`.

Em hospedagem na nuvem (por exemplo, Streamlit Community Cloud), a chave vai nos "Secrets" da plataforma, no formato `ORS_API_KEY = "sua_chave"`, e nunca no repositório.

## Outras formas de usar

**Terminal**

    python combustivel.py --km 40 --preco 6,50 --ida-volta
    python viagem.py "Praça Mauá, Centro, Rio de Janeiro" --origem "Rua X, 100, Tijuca" --preco 6,50
    python viagem.py --salvar-origem "Rua X, 100, Tijuca, Rio de Janeiro"

A origem salva fica só no seu computador (`config.local.json`). O destino também aceita coordenadas, como `-22.9068, -43.1729`.

**Excel (`calculadora_combustivel.xlsx`)**

Funciona sozinho, sem Python nem internet. Você informa a distância em km. A aba *Calculadora* faz as contas, a aba *Veículos* guarda os consumos e a aba *Pedágios* tem as praças: marque "Sim" nas do seu trajeto.

## Dados e limites

- **Só o estado do RJ.** A busca de endereços é restrita a ele.
- **Tempo sem trânsito.** É uma estimativa.
- **Consumo do Fiesta:** valores atribuídos ao Inmetro (gasolina), com testes reais citados na fonte do veículo. Ajuste com o seu consumo medido.
- **Preço do litro:** informado por você.
- **Pedágios:** carro de passeio (categoria 1). As tarifas mudam todo ano, então confira a fonte de cada praça em `pedagios.json` antes de viajar. Praças marcadas como "a confirmar" ainda não têm tarifa e não entram no cálculo.

## Serviços e créditos

- Rotas e busca de endereços: [OpenRouteService](https://openrouteservice.org). Se ele falhar, o app tenta o Nominatim e o OSRM, que usam dados do OpenStreetMap.
- Dados do OpenStreetMap: © colaboradores do OpenStreetMap, licença ODbL.
- Tarifas: notícias e páginas das concessionárias e da ANTT, listadas em cada praça.

## Estrutura

| Arquivo | Para que serve |
| --- | --- |
| `app.py` | Interface web (Streamlit) |
| `combustivel.py` | Cálculo de combustível e base de veículos |
| `rota.py` | Endereço → distância e tempo |
| `pedagio.py`, `pedagios.json` | Cadastro e cálculo de pedágios |
| `viagem.py` | Viagem completa pelo terminal |
| `veiculos.json` | Veículos da base (`veiculos_extras.json` guarda os que você incluir) |
| `calculadora_combustivel.xlsx` | Versão em planilha |
| `diagnostico_rota.py` | Mede onde está a demora se a consulta de rota ficar lenta |
| `test_*.py` | Testes automáticos |

## Testes

    python -m unittest

## Dados que ficam fora do Git

O `.gitignore` protege `.env` (sua chave) e `config.local.json` (seu endereço).

## Evolução prevista

Estacionamentos próximos (com indicação de 24h), preços de postos no caminho, histórico de destinos recentes e tempo com trânsito.
