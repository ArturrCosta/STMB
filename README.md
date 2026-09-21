# Song to My Bills

Jogo 2D desenvolvido em PyGame para o trabalho final da disciplina de Desenvolvimento de Software.

## Conceito

O jogador possui uma dívida e um tempo limitado para conseguir dinheiro.
Ele explora uma cidade, toca músicas em diferentes locais e usa o dinheiro
para progredir e acessar áreas melhores.

## Tecnologias

- Python
- PyGame
- PyTMX
- Tiled
- SQLite (futuramente)

## Como executar

1. Criar a virtual environment:
   `python -m venv .venv`

2. Ativar a virtual environment.

3. Instalar as dependências:
   `pip install -r requirements.txt`

4. Executar:
   `python main.py`

## Estado atual

- Janela do jogo
- Game loop
- Jogador com movimentação WASD
- Câmera
- Mapa criado no Tiled
- Mapa carregado no PyGame através do PyTMX