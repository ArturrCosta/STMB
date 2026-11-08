# Notas da integração — Song to My Bills

Esta pasta parte do ZIP `STMB-feat-rhythm-mechanics.zip` enviado pelo usuário. Os arquivos da branch de ritmo foram preservados. A integração substituiu apenas `player.py`, adicionou `assets/images/player.png` e atualizou o README para documentar o sprite.

## Preservado da branch recebida

- `game.py`, `rhythm.py`, beatmap e música `Cidade em Pulso`;
- testes de ritmo e de integração do jogo;
- `tiled_map.py`, incluindo colisões dos prédios rotacionados;
- mapa Tiled, tilesets, prédios, loja, ranking, câmera e planejamento.

## Integração do personagem

- sprite sheet de 128×144 px, 12 quadros em células 32×48 px;
- quatro quadros para frente, costas e perfil esquerdo;
- perfil direito gerado por espelhamento horizontal;
- hitbox de colisão menor, posicionada na região inferior do sprite;
- a API usada por `game.py` (`player.image`, `player.rect`, `Player.update` e `reset_position`) foi mantida compatível.

## Verificações realizadas

- sintaxe de todos os arquivos Python validada com `compileall`;
- dimensões e modo RGBA do sprite conferidos;
- integração do `screen.blit(self.player.image, self.camera.apply(self.player.rect))` conferida;
- presença dos arquivos de música, beatmap e testes confirmada.

Os testes automatizados do jogo não puderam ser executados neste ambiente porque `pygame` e `pytmx` não estão instalados e o ambiente de execução não teve acesso à internet para instalá-los. É necessário executar os testes localmente no ambiente virtual do projeto.
