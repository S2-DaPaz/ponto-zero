# Ponto Zero

Mira fixa externa para FiveM e outros jogos no Windows. Desenha a mira no centro da tela, por cima do jogo, sem ler nem alterar nada dele.

## Baixar e usar

1. Baixe o `PontoZero.exe` na página de [Releases](../../releases) e abra. Não precisa instalar.
2. No FiveM, vá em Configurações → Gráficos e coloque o modo de exibição em **Janela sem bordas** (Borderless). Em tela cheia exclusiva o Windows não deixa nenhum programa desenhar por cima do jogo.
3. Clique em **Ativar mira** ou aperte **F9** (o atalho pode ser trocado em Configurações).

Para a mira continuar na tela, deixe o programa aberto ou minimizado. Fechar a janela desliga a mira.

## O que dá para fazer

- Seis estilos: cruz com espaço, ponto, mais, X, círculo com ponto e cantos.
- O preset **GTA V (ponto)** reproduz o ponto branco com contorno escuro do GTA V.
- Ajuste de tamanho, espessura, espaçamento, ponto central (redondo ou quadrado), estilo T, cor, opacidade, contorno (espessura, cor e opacidade) e deslocamento para o caso de o centro do jogo não bater com o da tela.
- A pré-visualização tem zoom de 1x, 2x e 4x. Em 1x ela mostra o tamanho real que aparece no jogo.
- Presets salvos em **Minhas miras**, com exportação e importação em `.json` e um código de texto (`PZ1:...`) para mandar no Discord.

## Importar a mira que você usava no F8 do FiveM

Em **Minhas miras → Importar do FiveM (F8)**, cole os comandos `cl_crosshair...` que você usava, do jeito que estiverem:

```
cl_crosshairalpha "255";cl_crosshaircolor "5";cl_crosshaircolor_r "255";cl_crosshaircolor_g "255";cl_crosshaircolor_b "255";cl_crosshairdot "1";cl_crosshairgap "-4";cl_crosshairsize "0";cl_crosshairstyle "4";cl_crosshairusealpha "1";cl_crosshairthickness "1.6";cl_crosshair_outlinethickness "1";cl_crosshair_drawoutline "1"
```

Funciona com ou sem aspas, tudo numa linha separado por `;` ou um comando por linha.

O manual da Cfx diz que o crosshair do FiveM imita o do CS:GO, então a conversão usa as regras do CS:GO: tamanho e espessura medidos em 1/480 da altura da tela, e o espaço até cada linha é `4 + cl_crosshairgap` pixels. O código que desenha a mira no FiveM não é público, então não há como garantir o mesmo pixel em todos os casos. Se a mira importada ficar 1 px diferente da que você tinha, ajuste no editor com os botões − e +.

Comandos aceitos: `cl_crosshairsize`, `cl_crosshairthickness`, `cl_crosshairgap`, `cl_fixedcrosshairgap`, `cl_crosshairdot`, `cl_crosshairstyle`, `cl_crosshaircolor` (0 a 5), `cl_crosshaircolor_r/g/b`, `cl_crosshairusealpha`, `cl_crosshairalpha`, `cl_crosshair_drawoutline`, `cl_crosshair_outlinethickness`, `cl_crosshair_t` e `cl_customCrosshair`. Os `cl_crosshair_dynamic_*` não têm efeito no FiveM e são ignorados.

## Regras do servidor

O Ponto Zero só mostra uma imagem numa janela transparente. Não injeta nada no jogo nem lê a memória dele. Alguns servidores desligam a mira de propósito (`setr cl_customCrosshair false`) e podem proibir mira externa nas regras. Confira as regras do servidor antes de usar.

## Onde ficam os dados

Configurações e presets ficam em `%APPDATA%\PontoZero\config.json`. O botão **Abrir pasta de dados** em Configurações abre essa pasta.

## Compilar do código

Requer Python 3.11 ou mais novo no Windows.

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

O exe sai em `dist\PontoZero.exe`. Para rodar sem compilar:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python run.py
```

Testes: `.\.venv\Scripts\pip install pytest` e depois `.\.venv\Scripts\python -m pytest`.

## Como funciona

| Arquivo | Papel |
|---|---|
| `pontozero/crosshair.py` | Modelo da mira, validação dos dados importados e o renderizador (Pillow, com antialiasing por supersampling). O mesmo desenho alimenta a pré-visualização e o overlay. |
| `pontozero/overlay.py` | Janela Win32 com transparência por pixel (`UpdateLayeredWindow`). Os cliques passam por ela, ela fica sempre no topo e não aparece no Alt+Tab. |
| `pontozero/fivem.py` | Conversão dos comandos `cl_crosshair*` do FiveM. |
| `pontozero/storage.py` | Configuração em `%APPDATA%` e importação/exportação de presets. |
| `pontozero/app.py` | Interface (CustomTkinter). |
