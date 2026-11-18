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

## Como jogar

O agiota cobra uma parcela todos os dias, e a dívida e a cobrança sobem 50% a cada dia. Para pagar, toque nos palcos da cidade, compre roupas e fique de olho no HUD (dinheiro, dívida, **cobrança do dia seguinte** e o que acontece se você faltar).

- **Barzinho (fase 1):** música 1, sem pressão da plateia. Cachê base R$ 280.
- **Feira musical (fase 2):** música 2 e **energia da plateia**: errar notas esvazia a barra; se ela zerar, o show acaba sem cachê. Pede 1 peça de roupa. Cachê base R$ 520.
- **Casa de shows (fase 2):** *Cidade em Pulso* (provisória, será trocada) com a mesma mecânica de plateia. Pede 3 peças de roupa. Cachê base R$ 850.
- **Cobrança não paga:** começa uma caçada. Na 1ª falta vem só o agiota; a cada nova falta vêm **mais 2 capangas**, cada um saindo de um canto diferente do mapa. Cada um caça de um jeito: o agiota vem direto; os capangas cercam pelos lados, miram onde você vai estar ou tentam fechar o caminho à frente, e se afastam uns dos outros para não andarem em bolo (todos desviam dos prédios com A\*). Sobreviva até o tempo acabar.
- **Derrota:** só se o agiota ou um capanga te pegar. Faltar a cobrança não encerra o jogo, mas a próxima caçada fica maior.
- **Vitória:** quitar a dívida, embarcar no trem com a passagem ou sobreviver 30 dias. Vitórias dão bônus de pontos.

### Combos e bônus

Acertos seguidos aumentam o multiplicador de pontos: **2X** com 25 de combo, **3X** com 50 e **4X** com 100, com efeitos grandes na tela (multiplicador, "COMBO 50!", faíscas). No fim da música, o cachê ganha bônus: **Sequência de ouro** (combo de 90% da música) x1,5, **Sem erros** x2 e **Perfeito** (tudo Perfect) x3.

### O ciclo do dia e a noite

O dia vai das 08:00 às 03:00. Cada palco tem horário (Feira 08h–18h, Barzinho 12h–03h, Casa de shows 19h–03h). Dá para tocar quantas vezes quiser, mas repetir o mesmo local no mesmo dia paga 20% a menos a cada vez (mínimo 50%), e a ficha do local mostra isso. **A partir das 22:00 assaltantes rondam a cidade**: se pegarem você a pé, levam 40% do dinheiro, têm 50% de chance de levar também uma peça de roupa e te deixam atordoado. Em casa ou de Fusca você está seguro, e uma seta mostra o caminho de casa. Dormir antes da meia-noite deixa o dia seguinte **descansado** (+10% de velocidade); quem não dorme até as 03:00 fica **cansado** (35% mais lento).

### O Fusca

Comprado na loja (R$ 900), ele aparece estacionado ao lado da loja. Chegue perto e aperte **E** para entrar; **E** de novo para sair, e o carro fica onde você parou (a posição é salva). Na rua ele é bem mais rápido que a pé; **na grama perde 25% da velocidade**, levanta poeira e o HUD avisa. Assaltantes não pegam quem está de carro, mas o agiota e os capangas sim, se alcançarem.

### Preços

| Item | Preço |
|---|---|
| Chapéu / Sapatos / Calça / Blazer | R$ 100 / 150 / 200 / 300 |
| Fusca usado | R$ 900 |
| Passagem de trem (vitória) | R$ 2.400 |

Começa-se com R$ 400 (já pagando R$ 200 da primeira cobrança).

### Dificuldade

Escolha no menu (laterais, `1`, `2`, `3` ou `Enter` na opção *Dificuldade*).

| | Fácil | Normal | Difícil |
|---|---|---|---|
| Velocidade do jogador | 105% | 100% | 97% |
| Moradores na cidade | 6 | 9 | 13 |
| Velocidade do agiota | 150 | 185 | 215 |
| Tempo da caçada | 24 s | 20 s | 16 s |
| Assaltantes à noite | 2 | 3 | 4 |
| Nível das fases rítmicas | 1-3 | 2-4 | 3-5 |
| Multiplicador do cachê | 0,85 | 1,00 | 1,25 |

## Controles

| Tecla | Ação |
|---|---|
| `W`, `A`, `S`, `D` ou setas | Mover o personagem durante a exploração |
| `E` ou `Enter` | Interagir com um local próximo; entrar e sair do Fusca |
| `Esc` ou `P` | Pausar (também durante a perseguição); a janela sem foco pausa sozinha |
| `F2` | Ligar/desligar o som |
| Mouse | Clicar nas opções do menu e nos botões da ficha do palco |
| `M` (na pausa) | Salvar e voltar ao menu |
| `D`, `F`, `J` e `K` | Acionar as quatro pistas do minigame de ritmo |
| `I` | Abrir ou consultar o inventário rapidamente |
| Setas e `Enter` | Navegar pelos menus; no ranking, `←/→` filtram por dificuldade |

Durante a apresentação, `D`, `F`, `J` e `K` correspondem às pistas da esquerda para a direita. Pressione cada tecla quando o círculo chegar ao receptor; pressione várias ao mesmo tempo para notas simultâneas e mantenha a tecla até o fim das notas longas. `Esc` abandona sem pagamento. Ao terminar a música, `Enter` fecha o resultado.

Ao interagir com um palco (`E`) aparece uma ficha do local (faixa, duração, nível, cachê máximo e regra da fase) com duas opções: **Entrar no palco** (`Enter`/`E`/clique) ou **Cancelar** (`Esc`/clique). Se a música não puder ser carregada, a ficha mostra o motivo.

Em **Ajustes** (menu principal) ficam o volume da música, o volume dos efeitos e do ambiente, a velocidade das notas e a sincronia do áudio. **Calibrar sincronia automaticamente** toca batidas e mede o atraso entre o som e o seu toque; se as notas parecerem fora do tempo da música, faça a calibração uma vez. Os ajustes ficam em `data/rhythm_settings.json`.

A janela de acerto é generosa: uma nota que ainda encosta no receptor conta pontos (Perfect até 50 ms, Meh até 220 ms). A faixa clara sobre os receptores mostra essa janela.

## Sons

Efeitos (menu, compras, cachê, alarme do agiota, vitória/derrota...) e dois sons ambiente suaves (passarinhos de dia e grilos à noite, acompanhando o relógio do jogo) ficam em `assets/sounds/`. Eles são sintetizados por `python tools/make_sfx.py` (só biblioteca padrão); para usar sons próprios, substitua os `.wav` mantendo os nomes. `F2` liga/desliga o som. Se um arquivo faltar, o erro vai para `logs/error.log` e o jogo segue sem aquele som.

O jogo salva sozinho a cada dia, após cada apresentação e ao sair; o menu mostra **Continuar** quando há um save (`data/savegame.json`).

## Músicas e fases rítmicas

| Local | Faixa | Arquivos |
|---|---|---|
| Barzinho | Música 1 | `assets/music/musica1.wav` + `musica1.json` |
| Feira musical | Música 2 | `assets/music/musica2.wav` + `musica2.json` |
| Casa de shows | Cidade em Pulso (provisória) | `assets/music/cidade_em_pulso.wav` + `.json` |

A música de cada local é definida no campo `song` de `VENUES` (em `game.py`). O motor aceita WAV ou MP3 de qualquer duração e confere se a duração do áudio bate com a do JSON. Prefira **WAV PCM de verdade** (se tiver um MP3, converta: `ffmpeg -i musica.mp3 musica.wav`): é o formato que qualquer instalação do pygame lê sem surpresas.

### Sincronia das notas

Duas coisas fazem as notas parecerem fora da música, e o jogo trata as duas:

1. **Atraso do áudio do computador** (varia de máquina para máquina): use *Ajustes > Calibrar sincronia*. Durante o show o relógio das notas também é corrigido continuamente pela posição real da música.
2. **Notas em lugares onde nada acontece na música**: o gerador agora só põe nota onde há um ataque real (verificado: 0–3% de notas sem ataque, antes eram até 35%). Para as músicas oficiais, o melhor é **gravar a fase tocando junto**:

```powershell
python tools/record_chart.py assets/music/musica1.wav
```

Aperte D F J K no ritmo enquanto a música toca (segure para notas longas). Os toques são encaixados na batida e viram o nível mais difícil; os níveis fáceis ficam com as notas dos tempos fortes. O JSON anterior vira `.bak.json`. Dá para gravar várias vezes até ficar bom.

Para **trocar ou criar uma música**: coloque o áudio em `assets/music/`, gere o mapa e aponte o local para o novo JSON.

```powershell
python -m pip install -r requirements-dev.txt          # só o numpy, uma vez
python tools/make_beatmap.py assets/music/minha.wav --title "Minha música"
```

Com `--ending 4`, os últimos 4 segundos viram encerramento (mais notas e notas longas acompanhando o som), como na Música 2. `tools/make_beatmap.py` analisa o áudio (andamento, batidas e onsets por faixa de frequência) e gera os **5 níveis** de dificuldade com notas simples, simultâneas e longas, já validados pelas mesmas regras do jogo. Se o andamento detectado estiver errado, use `--bpm` e `--offset`; `--density` ajusta a quantidade de notas. O JSON tem `title`, `audio`, `bpm`, `offset`, `duration` e `levels` de `0` a `4`; cada nota tem `time` (segundos relativos ao `offset`), `lane` (`0` a `3`) e `duration` opcional. `tools/generate_demo.py` recria a faixa e o mapa de demonstração.

## O que está implementado

- Janela redimensionável e maximizada, mantendo a proporção 16:9, com pausa automática ao perder o foco;
- Mapa criado no Tiled (PyTMX) pré-renderizado, câmera que acompanha o jogador e desenho ordenado por profundidade;
- Movimento em oito direções e sprites animados em quatro direções;
- Colisão com a camada `Collision`, com prédios (inclusive rotacionados) e com os moradores;
- **Fase 1** (barzinho) e **fase 2** (feira e casa de shows, com roupa exigida e plateia que pode vaiar);
- Minigame de ritmo 4K com notas simples, simultâneas e longas, seis julgamentos, combo, precisão e uma faixa por local;
- **IA do agiota e capangas**: busca de caminho A\* sobre uma grade de navegação, rota refeita a cada 0,35 s, saída de cantos diferentes, setas na borda da tela;
- Assaltantes noturnos que avistam e perseguem o jogador a pé; Fusca dirigível que fica estacionado onde foi deixado;
- Multiplicador por combo, bônus de fim de música e efeitos animados no show;
- Moradores que passeiam pelos caminhos reais da cidade (também A\*) e funcionam como obstáculos;
- Dinheiro, dívida e cobrança diária (+50% ao dia), pontuação, perda de itens e finais de vitória/derrota;
- Ciclo do dia: horários de funcionamento dos palcos, um show por local por dia, céu que escurece ao entardecer, lembretes e seta para casa à noite, bônus por dormir cedo e cansaço por virar a noite;
- HUD em cartões (relógio com linha do dia, dinheiro, próxima cobrança, progresso), mensagens coloridas por tipo e barra de atordoamento;
- Loja com roupas, Fusca e passagem;
- Menu (Continuar, Novo jogo, Dificuldade, Ranking, Como jogar, Sair), pausa, fim de jogo e ranking filtrável por dificuldade;
- Ranking em SQLite (nome, pontuação, dias, dificuldade, resultado, data/hora) e salvamento de partida em JSON;
- Registro de eventos em `logs/game.log` e de problemas em `logs/error.log`.

## Sprite e animação do personagem

O personagem usa `assets/images/player.png`, um sprite sheet PNG com transparência (RGBA). A folha tem **128×144 px**, organizada em **4 colunas × 3 linhas**; cada quadro mede **32×48 px**.

| Linha | Direção | Observação |
|---|---|---|
| 1 | Frente / baixo | Quatro quadros |
| 2 | Costas / cima | Quatro quadros |
| 3 | Perfil esquerdo | Quatro quadros; o lado direito é criado por espelhamento no Pygame |

A animação avança a cada 0,12 segundo enquanto o personagem se move. Parado, usa o primeiro quadro da direção atual. Ao substituir o desenho no Aseprite, mantenha o tamanho de cada célula e a ordem das linhas, ou ajuste as constantes no início de `player.py`.

## Próximas etapas de desenvolvimento

- Trocar *Cidade em Pulso* e as músicas provisórias pelas faixas oficiais (basta gerar o JSON com `tools/make_beatmap.py` e atualizar `song` em `VENUES`);
- Os prédios que faltavam (casa de shows, barzinho, sua casa, loja e feira) foram desenhados por `tools/make_buildings.py` e já estão no mapa; para usar arte própria, substitua os PNGs em `assets/images/buildings/` mantendo o tamanho.
- Trocar os moradores desenhados por código por sprites, se quiser.

As posições dos pontos de entrada ficam na estrutura `ZONES`, no início de `game.py`.

## Arquivos importantes

| Arquivo ou pasta | Função |
|---|---|
| `main.py` | Janela, loop principal e tratamento de erro de inicialização |
| `game.py` | Estados do jogo, regras, interações, minigames e interface |
| `rhythm.py` | Carregamento de beatmaps, julgamento, plateia e configurações do ritmo |
| `player.py` / `npc.py` | Jogador, moradores e agiota |
| `navigation.py` | Grade de navegação e busca de caminhos (A\*) |
| `tiled_map.py` / `camera.py` | Mapa (colisão, chão, pré-renderização) e câmera |
| `ranking.py` / `savegame.py` | Ranking em SQLite e salvamento da partida |
| `log_setup.py` | `logs/game.log` (tudo) e `logs/error.log` (problemas) |
| `audio.py` | Efeitos sonoros e sons ambiente (`assets/sounds/`) |
| `ui.py` | Fontes, painéis, barras, ícones e textos da interface |
| `assets/fonts/` | Fonte Poppins (licença SIL OFL, em `OFL.txt`) |
| `tools/make_beatmap.py` | Gerador de fases rítmicas a partir de um áudio |
| `tools/record_chart.py` | Gravador de fases: tocar junto com a música para criar o beatmap |
| `tools/make_buildings.py` | Desenha casa de shows, barzinho, casa do jogador, loja e feira e os coloca no `cidade.tmx` |
| `car.py` | O Fusca (dirigir, estacionar, grama) |
| `tools/make_sfx.py` | Gerador dos efeitos e sons ambiente |
| `tests/` | Testes automatizados (`python -m unittest discover -s tests`) |
| `docs/relatorio_tecnico.md` | Rascunho do relatório: diagrama de classes, banco de dados, dificuldades |
| `assets/` | Imagens, mapas (`.tmx`/`.tsx`) e músicas |

## Dados gerados pelo jogo

Ao jogar, o jogo cria automaticamente, se necessário:

- `data/ranking.db`: banco de dados SQLite do ranking;
- `data/savegame.json` e `data/rhythm_settings.json`: partida salva e ajustes do ritmo;
- `logs/game.log` e `logs/error.log`: eventos e problemas (falha ao carregar assets, exceções e acessos inválidos ao banco).

Esses arquivos são gerados durante o uso e não precisam ser adicionados ao Git. Se o ranking ou um asset falhar, o erro vai para `logs/error.log` e o jogo continua (ou encerra com uma mensagem clara, no caso de um asset essencial ausente).

## Testes

```powershell
python -m unittest discover -s tests
```

Os testes usam SDL "dummy" (sem janela), não mexem no ranking, nos ajustes nem no save do jogador e conferem: todas as músicas em todos os níveis, os caminhos dos tilesets, a plateia, o agiota, a navegação, o menu e o save.

## Observações

- Os marcadores coloridos dos locais e as imagens dos prédios que faltam serão trocados pelos assets finais.
- Todos os tilesets ficam dentro do projeto (`assets/`), sem depender de caminhos de outro computador; um teste automático confere isso.
- Se a ativação do ambiente virtual for bloqueada pelo PowerShell, execute o seguinte comando apenas na janela atual do terminal e tente ativá-lo novamente:

  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\.venv\Scripts\Activate.ps1
  ```
