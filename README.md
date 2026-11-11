# TRANSCENDÊNCIA — A Lenda do Cavaleiro Plano

Trabalho final de **Computação Gráfica** — CEFET-MG (Prof. Dr. Raulivan Rodrigo).
Jogo em **Python + pygame**. Para passar de cada fase, o jogador precisa aplicar um conceito da disciplina.

## Enredo

No Reino de **Planícia**, tudo é plano: um mundo de pixels sem cor. Sir **Lineu**, um cavaleiro 2D, recebe uma
mensagem de **Volumar, o Arquimago Volumétrico**, um ser da Terceira Dimensão. Volumar conta que **Vorax, o Dragão
Achatador**, esmagou Planícia até restarem só pixels e agora quer achatar também o mundo 3D. Para enfrentá-lo, Lineu
precisa dominar as "Artes dos Geômetras" e **transcender para o 3D**.

O **prólogo é jogável**: Lineu anda pelo vilarejo monocromático com as setas (o cenário rola com uma câmera 2D),
conversa com os aldeões, recebe do Capitão Ortogonal a missão de patrulhar os arredores e, ao começar a questionar o
próprio mundo, recebe a visita de Volumar.

O mundo vai ficando mais robusto a cada fase: começa numa grade monocromática de fósforo verde, ganha cores,
texturas, formas, curvas, profundidade e termina num mundo 3D renderizado em tempo real.

## Fases e conceitos

| Fase | Cenário | Conceito aplicado | O que o jogador faz |
|---|---|---|---|
| I | O Mundo de Pixels | **Rasterização**: Bresenham e Ponto Médio | Constrói pontes com retas de Bresenham, com no máximo 45° e desviando de pixels corrompidos; abre um portal escolhendo o raio da circunferência |
| II | O Vale das Cores | **RGB** (aditivo), **CMYK** (subtrativo), **Alpha** | Mistura luz RGB, reproduz um estandarte com tintas CMYK e acerta a opacidade de uma ponte espectral (C = αF + (1-α)B) |
| III | O Véu Esmeralda | **Chroma key** | Escolhe a cor-chave com um conta-gotas e ajusta a tolerância para remover o véu sem apagar a floresta verde |
| IV | A Fortaleza das Matrizes | **Transformações 2D** em **coordenadas homogêneas** | Compõe matrizes 3x3 (translação, escala, rotação, reflexão, cisalhamento, escala e rotação em torno de um ponto) para encaixar a chave em 5 fechaduras |
| V | O Mapa do Cartógrafo | **SRU → SRN → SRD** (window/viewport) | Mira uma catapulta convertendo km em pixels; na rodada noturna, digita xd e yd calculados |
| VI | A Torre das Curvas | **Curvas de Bézier** / De Casteljau | Arrasta pontos de controle para guiar uma bola de fogo pelos anéis, desviando dos pilares (quadrática e cúbicas) |
| VII | O Limiar da Profundidade | **Projeções** ortográfica e perspectiva | Gira objetos 3D até a projeção coincidir com a fechadura (quadrado, hexágono do cubo, triângulo, túnel em perspectiva) |
| VIII | A Forja da Revolução | **Superfícies de revolução** e **malhas** | Modela o perfil (Bézier) de um elmo e de um cálice; a forja gira o perfil e gera a malha 3D |
| IX | Transcendência | **Câmera virtual** (lookAt), **pipeline 3D**, **modelos OBJ**, **mapeamento de textura** | Explora em primeira pessoa um mundo 3D (castelo, moinho, lagos, florestas, montanhas) e os sete reinos que o Feitiço Dimensional de Vorax achatou, onde os planicianos ainda andam desenhados no chão; absorve os 3 Cristais Dimensionais que selam o feitiço, descobre que o quarto cristal é o próprio Vorax e o derrota em 3D, devolvendo a altura aos reinos |

Em todas as fases, **H** abre o "Pergaminho do Conhecimento", com a teoria e as fórmulas do conceito.

## Como executar

```bash
pip install pygame numpy
python main.py
```

Para ir direto a uma fase (útil na apresentação): `python main.py 7`.

**Qualidade gráfica**: em *Menu → Configurações* o jogador escolhe gráficos **Simplificados** (malhas reduzidas,
mais FPS) ou **Bonitos** (malhas completas, detalhe alto até longe, luz hemisférica e bordas suavizadas). O painel
mostra o Vorax animado nas duas qualidades lado a lado. A escolha fica gravada em `save.json` e vale para as cenas
3D (Fases VIII e IX e o final).

**Modo demonstração** (o jogo se joga sozinho, do menu ao final, com cursor e legendas explicando cada passo):

```bash
python main.py --demo
```

ESC encerra a demonstração.

### Controles gerais
- **Prólogo**: SETAS andam, ESPAÇO pula, E conversa com os aldeões
- **Fase IX**: o MOUSE gira a câmera (fica capturado durante o jogo; M solta/prende), W/A/S/D andam (SHIFT corre), clique ou ESPAÇO lançam raios, RODA altera o FOV
- **ESPAÇO / ENTER / clique**: avança os diálogos (TAB pula o diálogo)
- **H**: pergaminho com o conceito da fase
- **F5**: reinicia a fase
- **ESC**: volta ao menu
- **F2**: liga/desliga o som
- **F3**: mostra o FPS
- **F9**: pula a fase atual (atalho para a apresentação)

Os controles específicos de cada fase aparecem na parte inferior da tela.

## Implementação (tudo feito do zero)

Os algoritmos estão em `engine/cg.py`. O pygame é usado apenas para abrir a janela, ler a entrada e pintar
pixels/polígonos.

- `bresenham`, `midpoint_circle`: rasterização apenas com inteiros
- `cmyk_to_rgb`, `rgb_to_cmyk`, `alpha_blend`, `chroma_key` (vetorizado com numpy)
- `T2, S2, R2, Ref2, Sh2, apply2`: matrizes homogêneas 3x3
- `sru_to_srn`, `srn_to_srd`, `srd_to_sru`: window/viewport com inversão do eixo Y
- `de_casteljau`, `bezier`, `bernstein_cubic`
- `T3, S3, Rx, Ry, Rz, look_at, perspective, ortho`: matrizes 4x4, câmera e projeções
- `revolution`, `box`, `cylinder`, `cone`, `octahedron`: modelagem por malhas

`engine/render3d.py` é um **pipeline 3D em software**:
vértice (SRO) → Model → SRU → View (lookAt) → recorte no plano *near* (Sutherland–Hodgman) → Projeção →
divisão por *w* (SRN) → Viewport (SRD). A visibilidade usa *back-face culling* e o algoritmo do pintor, e a
iluminação usa Lambert com sombreamento constante e névoa. Na qualidade **Bonitos** a luz ambiente é
**hemisférica** (faces voltadas para o céu recebem mais luz que as voltadas para o chão) e as bordas dos polígonos
são suavizadas com linhas antisserrilhadas.

Na Fase IX o pipeline ganhou também:
- **modelos OBJ/MTL** (representação por faces) com cor por face amostrada da textura, correção de gama e
  **simplificação por agrupamento de vértices**, mais um **nível de detalhe (LOD)** escolhido pela distância;
- **agrupamento de geometria estática** em blocos espaciais, para reduzir o número de chamadas;
- **simplificação por colapso de arestas com erro quádrico** (Garland & Heckbert, `model.simplify_qem`), usada nas
  árvores: ao contrário do agrupamento de vértices, preserva troncos e galhos finos;
- **três níveis de detalhe na vegetação**: malha completa de perto, malha simplificada a média distância e
  **impostor** de longe (a árvore é desenhada uma vez pelo próprio pipeline em 8 ângulos e vira um *billboard*);
- **descarte por visibilidade (frustum culling)**: antes de transformar os vértices de um objeto, sua esfera
  envolvente é testada contra o campo de visão (`Renderer3D.visible`); os impostores ficam em cache por tamanho e
  nível de névoa, com no máximo 3 imagens novas por quadro, para o FPS não oscilar ao andar;
- **grama e flores procedurais** (triângulos gerados por célula do mapa), com as pontas balançando ao vento por
  deformação de vértices, e **escala não uniforme animada** nos reinos achatados (tremem a cada cristal absorvido e
  recuperam a altura quando o feitiço se desfaz);
- **recorte de polígonos 2D (Sutherland–Hodgman)** contra a viewport;
- **mapeamento de textura com perspectiva correta** por lançamento de raios (um raio por pixel cruzando o plano do
  chão), usado nos reinos 2D achatados e nas pessoas 2D, com alongamento **anamórfico** para ficarem legíveis da
  altura dos olhos;
- **animação esquelética** do Vorax: o modelo glTF tem um esqueleto e cada vértice segue até 4 ossos com pesos
  (*linear blend skinning*, v' = Σ wᵢ·Gᵢ·Bᵢ⁻¹·v). O script `tools/bake_gltf.py` lê o `.glb` do zero (JSON + buffer
  binário), percorre o grafo de cena, interpola os quadros-chave (linear e SLERP nos quatérnios), calcula o
  skinning e grava as poses em `assets/models/vorax_anim.npz`, em duas versões (malha completa e simplificada). No
  jogo, a pose é interpolada entre dois quadros (v(t) = (1-α)·A + α·B).
  O modelo original só traz o voo; o ataque, o dano e a morte são **animações sintéticas** criadas no script:
  sobre o voo, somam-se rotações a ossos específicos (q' = q · q(eixo, θ(t)), com envelopes suaves no tempo).
  No ataque Vorax recua o pescoço, abre a mandíbula e dá o bote, e a bola de fogo sai da ponta do focinho na pose
  daquele instante. No dano ele recua a cabeça e, na morte, fecha as asas e tomba o pescoço.

Para refazer os modelos animados depois de trocar o `.glb`: `python tools/bake_gltf.py`.

O game loop usa **delta time**, então o movimento não depende do FPS.

## Estrutura

```
main.py                 ponto de entrada
engine/
  core.py               game loop, cenas, classe base das fases
  cg.py                 algoritmos de Computação Gráfica
  render3d.py           pipeline 3D em software
  model.py              modelos OBJ, simplificação, LOD e modelos animados
  ui.py                 botões, sliders, diálogos e painéis
  assets.py             sprites e fontes
  scenery.py            montagem dos cenários 2D
scenes/
  menu.py, intro.py, ending.py
  fase1_raster.py ... fase9_camera.py
tools/
  bake_gltf.py          leitor de glTF/GLB + skinning: pré-calcula as animações e simplifica a vegetação
assets/                 sprites, fontes, modelos (fontes .glb em assets/models/src) e licenças
```

## Créditos dos assets (todos de licença livre)

- **Kenney** (www.kenney.nl), *Tiny Dungeon*, *Tiny Town* e *Pixel Platformer*, licença CC0: cavaleiro, mago,
  vilarejo, castelo e masmorra
- **Cethiel**, *Dragon - Fully Animated* (OpenGameArt.org), licença CC0: o dragão Vorax
- **Vorax 3D**: MattBas, *Simple 3D Dragon Model* (OpenGameArt.org), licença **CC-BY-SA 4.0**: modelo glTF com
  esqueleto e voo. Recolorido em vermelho-sangue e com as animações de ataque, dano e morte criadas por
  `tools/bake_gltf.py` (adaptação distribuída sob a mesma licença; ver `assets/licencas/MattBas_CC-BY-SA.txt`)
- **Demais modelos 3D** (CC0), lidos de OBJ/MTL e simplificados por `engine/model.py`:
  - Volumar: Quaternius, *RPG Characters* (Wizard), com o manto tingido de roxo e um chapéu modelado no jogo
  - Castelo, moinho, torre, casas, poço, rochas e montanhas: Kay Lousberg, *KayKit Medieval Builder Pack*
  - Árvores e arbustos: Quaternius (*Tree*, *Autumn Tree*, *Pine Tree Autumn*, *Tree Spiral*, *Dead Tree* e
    *Bush*, via Poly Pizza), recoloridos e simplificados por `tools/bake_gltf.py`
- **Músicas** (CC0, OpenGameArt.org). A trilha acompanha a evolução do mundo: chiptune 8-bit, depois medieval acústico, depois orquestra e coral no 3D.
  - RandomMind: *Kings Feast* (menu), *The Bard's Tale* (Fase I), *The Old Tower Inn* (II), *Medieval Exploration* (III), *Market Day* (IV–V), *Rejoicing* (final)
  - cesisco: *Fantasy Choir 1 e 2* (VI e IX)
  - legoluft: *Atmospheric Puzzles* (VII–VIII)
  - cynicmusic: *Dramatic Boss Encounter* (batalha contra Vorax)
- **Efeitos sonoros** (CC0, mais de 100 arquivos em `assets/sfx`, recortados e normalizados para o jogo):
  - Kenney: *RPG Audio*, *Impact Sounds*, *Interface Sounds*, *UI Audio*, *Music Jingles*, *Digital Audio* e *Sci-fi Sounds*
  - OpenGameArt: rubberduck (*80 CC0 RPG SFX*, *100 CC0 SFX*), Julien Matthey (bola de fogo), AntumDeluge (fogo crepitando, bater de asas), Almitory (feitiço), Ogrebane (teletransporte), IgnasD (portal), themightyglider (martelo na bigorna), VishwaJai (asas do dragão), StarNinjas (rosnados), Darsycho (rugidos), Thimras (ambientes de pássaros, rio e vento), isaiah658 (pássaros), JaggedStone (ambiente de masmorra), SketchMan3 (vento), pyranostudios (whoosh)
  - Bipes 8-bit dos pixels e fanfarra final sintetizados com numpy (`engine/audio.py`)
- Fontes **MedievalSharp** e **Press Start 2P**, SIL Open Font License (Google Fonts)
