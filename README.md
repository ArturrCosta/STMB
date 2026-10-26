# Song to My Bills

Jogo 2D desenvolvido em Python e Pygame para o trabalho final da disciplina de Desenvolvimento de Software.

## Como executar

1. Instale o Python 3.13 (ou uma versão compatível com o Pygame 2.6.1).
2. Abra o terminal na pasta do projeto.
3. Crie e ative o ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
4. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```
5. Inicie o jogo:
   ```powershell
   python main.py
   ```

## Controles

- **WASD ou setas:** mover o personagem.
- **E ou Enter:** interagir com o local próximo.
- **ESC ou P:** pausar durante a exploração.
- **A, S e D:** tocar as três pistas do minigame de ritmo.
- **Espaço:** reagir ao evento do cobrador.
- **I:** mostrar o inventário rapidamente.
- **Enter / setas:** navegar nos menus.

## O que já funciona no protótipo

- Janela redimensionável e maximizada, mantendo a proporção 16:9.
- Mapa do Tiled carregado com PyTMX e câmera que segue o jogador.
- Movimento em oito direções com velocidade diagonal corrigida.
- Colisão básica com a camada `Collision` e com prédios sem rotação.
- Duas etapas de progressão: Fase 1 (cidade, loja e barzinho) e Fase 2 (feira e casa de shows, com exigência de roupa).
- Marcadores provisórios e interações de loja, barzinho, feira musical, casa de shows, casa do jogador e estação de trem.
- Minigame de ritmo com três pistas, acertos, erros e bônus de precisão.
- Dinheiro, dívida, cobranças diárias, crescimento de 50% e condição de derrota.
- Loja com roupas, Fusca e passagem; roupas desbloqueiam locais mais difíceis.
- Evento aleatório do cobrador com teste rápido de reação.
- Condição de vitória por fuga de trem ou por sobreviver 30 dias.
- Menu, escolha de dificuldade, pausa, fim de jogo e tela de ranking.
- Ranking persistente em SQLite e log em `logs/game.log`.

## Arquivos importantes

- `main.py`: inicialização da janela e loop principal.
- `game.py`: estados, regras, interações, minigame e interface.
- `player.py`: movimento e colisões do personagem.
- `camera.py`: acompanhamento e limites da câmera.
- `tiled_map.py`: leitura/renderização do mapa e colisões.
- `ranking.py`: salvamento e consulta do ranking SQLite.
- `assets/maps/cidade.tmx`: mapa principal.

## Observações

- Os marcadores coloridos dos locais são provisórios: as coordenadas estão centralizadas em `ZONES`, no começo de `game.py`, para facilitar movê-los quando os assets finais estiverem prontos.
- O tileset usado pelo mapa agora está dentro de `assets/maps/tiles do mapa.png`, então não depende de um caminho de arquivo fora do projeto.
- O jogador e a interface usam formas e cores provisórias; podem ser substituídos pelos assets finais sem reescrever as regras.
- O banco `data/ranking.db` e o arquivo `logs/game.log` são criados automaticamente quando o jogo inicia. Eles não precisam ser adicionados ao Git.
