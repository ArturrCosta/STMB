# Song to My Bills

Jogo 2D desenvolvido em **Python e Pygame** para o trabalho final da disciplina de Desenvolvimento de Software.

O jogador explora uma cidade, participa de minigames musicais para ganhar dinheiro e precisa administrar uma dívida enquanto tenta cumprir seus objetivos.

## Requisitos

- Windows e PowerShell;
- Python **3.13 (64 bits)**;
- Git, caso o projeto seja baixado pelo GitHub.

As dependências do Python estão listadas em `requirements.txt`.

## Como executar pela primeira vez

Abra o PowerShell na pasta principal do projeto — a pasta que contém `main.py` e `requirements.txt`.

### 1. Criar o ambiente virtual

O ambiente virtual mantém as bibliotecas do projeto separadas das outras instalações de Python do computador. Use Python 3.13 (64 bits).

Se o Python 3.13 estiver instalado em `C:\Python313`, execute:

```powershell
C:\Python313\python.exe -m venv .venv
```

Em computadores nos quais o inicializador `py` estiver configurado corretamente, também é possível usar:

```powershell
py -3.13 -m venv .venv
```

> Se a pasta `.venv` já existir e estiver funcionando, não precisa criá-la de novo.

### 2. Ativar o ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Quando estiver ativado, o terminal mostrará `(.venv)` no começo da linha.

### 3. Instalar as dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Iniciar o jogo

```powershell
python main.py
```

## Como executar nas próximas vezes

Depois que o ambiente virtual e as dependências estiverem instalados, **não é necessário repetir a instalação**. Sempre que abrir o projeto novamente:

1. Abra o PowerShell na pasta do projeto.
2. Ative o ambiente virtual:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Inicie o jogo:

   ```powershell
   python main.py
   ```

Para sair do ambiente virtual quando terminar, execute `deactivate`.

## Controles

| Tecla | Ação |
|---|---|
| `W`, `A`, `S`, `D` ou setas | Mover o personagem durante a exploração |
| `E` ou `Enter` | Interagir com um local próximo |
| `Esc` ou `P` | Pausar durante a exploração |
| `D`, `F`, `J` e `K` | Acionar as quatro pistas do minigame de ritmo |
| `Espaço` | Reagir ao evento do cobrador |
| `I` | Abrir ou consultar o inventário rapidamente |
| Setas e `Enter` | Navegar pelos menus |

Durante a apresentação, `D`, `F`, `J` e `K` correspondem às pistas da esquerda para a direita. Pressione cada tecla quando o círculo chegar ao receptor; pressione várias ao mesmo tempo para notas simultâneas e mantenha a tecla até o fim das notas longas. `Esc` abandona sem pagamento. Ao terminar a música, `Enter` fecha o resultado.

Antes de tocar, use `↑/↓` para selecionar e `←/→` para ajustar velocidade visual, volume e offsets de áudio e entrada. A velocidade muda apenas a aproximação das notas. Offset de áudio positivo atrasa o mapa em relação ao início da reprodução; offset de entrada positivo compensa teclas percebidas tardiamente. Os ajustes são salvos em `data/rhythm_settings.json`.

Para testar a demonstração, inicie o jogo com `python main.py`, escolha uma dificuldade e interaja com o Barzinho. A faixa original **Cidade em Pulso** dura 36 segundos. Para adicionar outra música, coloque um WAV e um JSON em `assets/music/`, seguindo `cidade_em_pulso.json`: informe `title`, `audio`, `bpm`, `offset`, `duration` e `levels` de `0` a `4`. Cada nota tem `time` (segundos relativos ao `offset` inicial), `lane` (`0` a `3`) e `duration` opcional para notas longas. O motor escolhe automaticamente os JSON dessa pasta e alterna entre eles a cada apresentação. O arquivo `tools/generate_demo.py` recria a faixa e os mapas de demonstração.

## O que está implementado no protótipo

- Janela redimensionável e maximizada, mantendo a proporção 16:9;
- Mapa criado no Tiled, carregado com PyTMX, e câmera que acompanha o jogador;
- Movimento em oito direções, com velocidade diagonal corrigida;
- Personagem com sprites animados em quatro direções (frente, costas e laterais; lado direito espelhado), com quatro quadros por direção;
- Colisão com a camada `Collision` e com prédios da camada `Buildings`, inclusive os que foram rotacionados no Tiled;
- Duas etapas de progressão: fase 1 (cidade, loja e barzinho) e fase 2 (feira musical e casa de shows, que exige roupa adequada);
- Interações provisórias com loja, barzinho, feira musical, casa de shows, casa do jogador e estação de trem;
- Minigame de ritmo 4K com música, beatmaps, notas simples, simultâneas e longas, seis julgamentos, combo e precisão;
- Sistema de dinheiro, dívida, cobranças diárias, aumento diário de 50% da dívida e condição de derrota;
- Loja com roupas, Fusca e passagem; roupas desbloqueiam locais mais difíceis;
- Evento aleatório do cobrador com teste rápido de reação;
- Condições de vitória por fuga de trem ou por sobreviver 30 dias;
- Menu inicial, escolha de dificuldade, pausa, fim de jogo e tela de ranking;
- Ranking salvo localmente em SQLite e registro de eventos em `logs/game.log`.

## Sprite e animação do personagem

O personagem usa `assets/images/player.png`, um sprite sheet PNG com transparência (RGBA). A folha tem **128×144 px**, organizada em **4 colunas × 3 linhas**; cada quadro mede **32×48 px**.

| Linha | Direção | Observação |
|---|---|---|
| 1 | Frente / baixo | Quatro quadros |
| 2 | Costas / cima | Quatro quadros |
| 3 | Perfil esquerdo | Quatro quadros; o lado direito é criado por espelhamento no Pygame |

A animação avança a cada 0,12 segundo enquanto o personagem se move. Parado, usa o primeiro quadro da direção atual. Ao substituir o desenho no Aseprite, mantenha o tamanho de cada célula e a ordem das linhas, ou ajuste as constantes no início de `player.py`.

## Próximas etapas de desenvolvimento

- Criar músicas e beatmaps adicionais para variar o repertório das apresentações;
- Revisar as mecânicas já implementadas para identificar o que ainda está simples, incompleto ou precisa de balanceamento;
- Substituir os elementos visuais provisórios pelas pixel arts finais e fazer os ajustes de integração.

As posições dos pontos de entrada e interação já foram ajustadas no mapa. Caso precisem ser alteradas novamente, as coordenadas ficam na estrutura `ZONES`, no início de `game.py`.

## Arquivos importantes

| Arquivo ou pasta | Função |
|---|---|
| `main.py` | Inicialização da janela e loop principal |
| `game.py` | Estados do jogo, regras, interações, minigame e interface |
| `player.py` | Movimento, colisões e animação do personagem |
| `assets/images/player.png` | Sprite sheet do personagem (quadros de 32×48 px) |
| `camera.py` | Acompanhamento do jogador e limites da câmera |
| `tiled_map.py` | Leitura e renderização do mapa e tratamento de colisões |
| `ranking.py` | Salvamento e consulta do ranking |
| `assets/maps/cidade.tmx` | Mapa principal criado no Tiled |
| `assets/maps/tiles do mapa.png` | Imagem do tileset referenciada pelo mapa |
| `requirements.txt` | Bibliotecas necessárias para executar o projeto |

## Dados gerados pelo jogo

Ao iniciar, o jogo cria automaticamente, se necessário:

- `data/ranking.db`: banco de dados local do ranking;
- `logs/game.log`: arquivo de registro de eventos e informações de execução.

Esses arquivos são gerados durante o uso e não precisam ser adicionados ao Git.

## Observações

- Os marcadores coloridos e algumas interações ainda são provisórios e serão ajustados ao mapa e aos assets finais.
- O tileset do mapa fica dentro do próprio projeto, evitando depender de um caminho de arquivo de outro computador.
- O personagem já utiliza o sprite sheet `assets/images/player.png`; a interface ainda contém elementos provisórios que podem receber os assets finais.
- Se a ativação do ambiente virtual for bloqueada pelo PowerShell, execute o seguinte comando apenas na janela atual do terminal e tente ativá-lo novamente:

  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\.venv\Scripts\Activate.ps1
  ```
