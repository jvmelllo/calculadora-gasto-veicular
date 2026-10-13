# Calculadora de gasto veicular (RJ)

## Interface web (Streamlit) — jeito mais fácil de usar
    pip install -r requirements.txt
    python -m streamlit run app.py

Na primeira vez o Streamlit pode pedir um e-mail no terminal: aperte Enter para pular.
O navegador abre sozinho em http://localhost:8501.

Antes, configure a chave da rota (veja "Passo 2" abaixo).

Para usar outro carro: em "Cálculo do Combustível" > "Incluir veículo", informe o nome e o consumo
(gasolina, km/l) na cidade e na estrada. Ele fica salvo em `veiculos_extras.json`.

## Passo 1 — combustível (terminal)
    python combustivel.py --km 40 --preco 6,50 --ida-volta

## Passo 2 — destino, distância e tempo (terminal)
Usa o OpenRouteService (plano gratuito: 2.000 rotas e 1.000 buscas de endereço por dia).

1. Crie uma conta em https://openrouteservice.org e gere uma chave de API gratuita no painel.
2. Copie `.env.example` para `.env` e cole a chave no lugar de `cole_sua_chave_aqui`.
3. Salve o endereço de partida (fica só no seu PC, em `config.local.json`):

       python viagem.py --salvar-origem "Rua X, 100, Tijuca, Rio de Janeiro"

4. Calcule uma viagem:

       python viagem.py "Praça Mauá, Centro, Rio de Janeiro" --preco 6,50
       python viagem.py "Praça Mauá, Centro, Rio de Janeiro" --preco 6,50 --ida-volta --percurso cidade

O destino também aceita coordenadas no formato `-22.9068, -43.1729`.
O tempo é uma estimativa sem trânsito.

## Passo 3 — pedágio (você escolhe as praças)
Na interface, a seção "Pedágio" tem a lista "Praças no trajeto": escolha as praças por onde você vai
passar e o valor entra no custo total. Marque "Fim de semana ou feriado" para usar a tarifa maior
das praças que têm uma (Rio–Santos). No Excel, use a aba "Pedágios" (marque Sim nas praças do trajeto).

- **Ida e volta:** praça dos dois sentidos conta 2×; a que cobra só em um sentido (Ponte Rio–Niterói:
  Rio → Niterói; BR-101 em São Gonçalo: rumo a Niterói) conta 1×.
- Os dados ficam em `pedagios.json` (carro de passeio, com fonte e data de vigência de cada praça).
- Tarifas mudam todo ano: confira a fonte antes de viajar.
- `"tarifa": null` = a confirmar: a praça aparece só na tabela de tarifas e não entra no cálculo.
  Quando confirmar o valor, preencha `tarifa`, `vigencia` e `fonte`, e troque `confianca` para `alta`.
- `"um_sentido": true` marca a praça que só cobra em um sentido.

## Testes
    python -m unittest

## Não suba para o Git / Vercel
`.env` (chave) e `config.local.json` (seu endereço) já estão no `.gitignore`.
