# Song to My Bills — Planejamento do Projeto

## 1. Visão geral

**Nome:** Song to My Bills

**Gênero:** Jogo 2D top-down de exploração, progressão e minigame de ritmo.

**Ideia central:**
O jogador possui uma dívida e um tempo limitado para conseguir dinheiro e pagá-la. Para ganhar dinheiro, pode tocar música em diferentes estabelecimentos da cidade. Lugares mais sofisticados exigem roupas adequadas e apresentam músicas mais difíceis, mas oferecem recompensas maiores.

**Loop principal do jogo:**

Explorar a cidade → encontrar um local para tocar → jogar o minigame de ritmo → receber dinheiro/recompensa → comprar roupas/itens → acessar locais melhores → enfrentar músicas mais difíceis → juntar dinheiro suficiente → pagar a dívida antes do tempo acabar.

---

## 2. Requisitos obrigatórios do trabalho

- PyGame.
- Programação orientada a objetos.
- Controles por teclado e/ou mouse.
- Pelo menos 2 fases com desafios ou mecânicas diferentes.
- Arquivo de log para erros e acontecimentos.
- Níveis de dificuldade que alterem elementos do jogo.
- Sistema de pontuação baseado no desempenho.
- Banco de dados SQLite (ou similar) para ranking.
- Ranking persistente com:
  - nome do jogador;
  - pontuação;
  - dificuldade;
  - data/hora.
- Tela de ranking.
- Menu inicial com:
  - iniciar jogo;
  - selecionar dificuldade;
  - ver ranking;
  - sair.
- Feedback visual durante o jogo, como dinheiro/pontuação, vida ou tempo restante.

---

## 3. Escopo planejado do jogo

### Fase 1 — Cidade

O jogador pode explorar a cidade e acessar locais mais simples.

Elementos planejados:
- movimentação livre;
- ruas e obstáculos;
- bar ou local simples para tocar;
- loja de roupas;
- dinheiro inicial;
- primeira música de dificuldade baixa;
- tempo para quitar a dívida.

### Fase 2 — Área sofisticada

O jogador precisa cumprir uma condição para acessar a área.

Elementos planejados:
- estabelecimento mais sofisticado;
- exigência de roupa adequada;
- música mais difícil;
- recompensa maior;
- desafio adicional em relação à primeira fase.

---

## 4. Mecânicas principais

### Dívida e tempo

O jogador começa com uma dívida e precisa conseguir dinheiro antes do fim do prazo.

### Música / ritmo

O jogador toca música por meio de um minigame de ritmo.

A recompensa depende do desempenho:
- acertar todas as notas: recebe o pagamento;
- desempenho mais preciso: recebe bônus;
- erro grave: não recebe o pagamento e pode perder um item aleatório.

### Loja

A loja vende roupas e, futuramente, outros itens.

Algumas áreas/estabelecimentos exigem uma roupa específica.

### Progressão

Quanto melhor o jogador tocar:
- ganha mais dinheiro;
- compra itens;
- acessa locais melhores;
- enfrenta músicas mais difíceis;
- consegue recompensas maiores.

---

## 5. Sistema de dificuldade

A dificuldade será planejada para alterar parâmetros do jogo.

### Fácil
- notas mais lentas;
- menos obstáculos;
- maior tempo disponível.

### Médio
- notas em velocidade média;
- quantidade intermediária de obstáculos;
- tempo intermediário.

### Difícil
- notas mais rápidas;
- mais obstáculos;
- menor tempo disponível.

Os valores exatos serão ajustados durante os testes.

---

## 6. Ordem de desenvolvimento

### Etapa 1 — Base do projeto
- criar a pasta do projeto;
- criar e configurar a `.venv`;
- instalar PyGame;
- criar `main.py`;
- criar o game loop;
- configurar janela e FPS;
- criar primeiro commit no Git.

**Resultado:** jogo abre e fecha corretamente.

### Etapa 2 — Jogador
- criar classe `Player`;
- desenhar o jogador;
- movimentação com WASD;
- preparar estrutura para colisões.

**Resultado:** personagem controlável.

### Etapa 3 — Câmera
- criar classe `Camera`;
- fazer a câmera acompanhar o jogador;
- limitar a câmera ao tamanho do mapa.

**Resultado:** jogador preparado para um mapa maior que a tela.

### Etapa 4 — Mapa
- criar mapa no Tiled;
- criar tileset;
- criar camadas do mapa;
- criar camada de colisão;
- integrar Tiled com PyTMX;
- renderizar o mapa no PyGame.

**Resultado:** cidade explorável.

### Etapa 5 — Colisões e interação
- impedir o jogador de atravessar paredes;
- criar áreas de interação;
- detectar quando o jogador entra em locais especiais.

**Resultado:** cidade com regras físicas e pontos de interação.

### Etapa 6 — Sistema de dinheiro e dívida
- criar dinheiro inicial;
- criar valor da dívida;
- criar cronômetro;
- criar condição de vitória;
- criar condição de derrota.

**Resultado:** objetivo principal do jogo funcionando.

### Etapa 7 — Minigame de ritmo
- criar sistema de notas;
- detectar acertos e erros;
- calcular desempenho;
- calcular recompensa;
- implementar penalidade por erro grave.

**Resultado:** principal minigame funcionando de forma independente.

### Etapa 8 — Loja e roupas
- criar loja;
- criar itens;
- comprar roupas;
- guardar itens do jogador;
- verificar requisitos dos estabelecimentos.

**Resultado:** progressão por compra e acesso.

### Etapa 9 — Fases
- separar a Fase 1 e a Fase 2;
- criar desafios diferentes;
- implementar progressão entre fases;
- manter dinheiro e progresso entre fases.

**Resultado:** requisito de duas fases funcionando.

### Etapa 10 — Dificuldade
- implementar Fácil, Médio e Difícil;
- conectar dificuldade à velocidade das notas;
- ajustar quantidade de obstáculos;
- ajustar tempo disponível.

**Resultado:** dificuldades realmente alteram o jogo.

### Etapa 11 — Interface
- menu inicial;
- seleção de dificuldade;
- HUD;
- tela de vitória/derrota;
- tela de ranking.

**Resultado:** fluxo completo de jogo.

### Etapa 12 — Banco de dados
- criar banco SQLite;
- criar tabela de ranking;
- salvar nome;
- salvar pontuação;
- salvar dificuldade;
- salvar data/hora;
- consultar melhores pontuações.

**Resultado:** ranking persistente.

### Etapa 13 — Logs
- criar `error.log`;
- registrar erros de carregamento de assets;
- registrar exceções;
- registrar falhas relacionadas ao banco.

**Resultado:** requisito de log atendido.

### Etapa 14 — Testes e polimento
- testar todas as fases;
- testar as três dificuldades;
- testar ranking;
- testar situações de erro;
- corrigir bugs;
- organizar código;
- revisar nomes e comentários;
- preparar versão final.

### Etapa 15 — Entrega
- revisar GitHub;
- escrever relatório técnico;
- fazer diagrama de classes;
- escrever manual de execução;
- gravar vídeo demonstrativo;
- preparar apresentação.

---

## 7. Estrutura inicial de pastas

```text
Song to My Bills/
│
├── main.py
├── game.py
├── player.py
├── camera.py
│
├── assets/
│   ├── images/
│   ├── sounds/
│   └── maps/
│
├── maps/
│
├── database/
│
├── logs/
│
└── README.md
```

A estrutura poderá crescer conforme novas mecânicas forem implementadas.

---

## 8. Regra de desenvolvimento

Prioridade:

1. Fazer funcionar.
2. Organizar.
3. Testar.
4. Melhorar a aparência.

Evitar adicionar mecânicas opcionais antes de todos os requisitos obrigatórios estarem funcionando.

Recursos como sons, animações, save e IA simples ficam para depois caso haja tempo.

---

## 9. Primeiro objetivo do projeto

Ao final da primeira etapa:

- o projeto possui uma `.venv` funcionando;
- PyGame instalado;
- janela abrindo;
- game loop funcionando;
- jogador desenhado;
- jogador se movimentando com WASD.

Depois disso, o próximo objetivo será integrar a câmera e começar o mapa.
