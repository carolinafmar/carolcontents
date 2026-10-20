# CarolContents

As stories que partilhas transformam-se, todas as semanas, numa edição:
um reel vertical com os achados numerados e uma página de links com os mesmos números.

**Como funciona**
1. Todas as manhãs, o robô procura stories novas nas exportações do Instagram que estão no teu Google Drive.
   Ignora as stories repetidas entre exportações e as exportações de outras contas, como a do Sabores D'Itália.
2. Para cada story, o Claude identifica o achado e procura o link oficial (marca, produto, restaurante, lugar).
   As stories sem achado, como selfies ou momentos pessoais, ficam de fora.
   Quando a identificação não é segura, a story fica numa lista "por rever" e não entra no reel.
3. Ao domingo ao fim da tarde, monta a edição: capa "CarolContents, Edição Nº X", os achados com o número e o nome em cada um, e um cartão final "Todos os links na bio".
4. O reel, a legenda e a lista por rever ficam no Drive, em `CarolContents/Edições/Edição Nº X`.
   A página de links é atualizada com a nova edição no topo.
5. Modo `rascunho` (por omissão): publicas tu o reel e escolhes o áudio no Instagram. O reel sai sem som de propósito: a música das stories tem muitas vezes direitos de autor.
   Modo `automatico`: publica sozinho.

## Instalação (uma vez, cerca de 20 minutos)

**1. GitHub.** Já está feito: o repositório é github.com/carolinafmar/carolcontents e a página de links fica em https://carolinafmar.github.io/carolcontents

**2. Acesso ao Google Drive.**
- Abre console.cloud.google.com, cria um projeto e ativa a **Google Drive API**.
- Em *IAM e administração → Contas de serviço*, cria uma conta e gera uma chave **JSON**.
- No Drive, partilha a pasta **CarolContents** com o e-mail dessa conta (termina em `iam.gserviceaccount.com`) como **Editor**.
- Põe as exportações do Instagram (`instagram-carolcontents-...`) dentro dessa pasta.
  Neste momento estão espalhadas por várias pastas do Drive.

**3. Chave do Claude.** Cria uma chave em console.anthropic.com.

**4. Segredos.** No GitHub, vai a *Settings → Secrets and variables → Actions → New repository secret* e cria:
| Nome | Valor |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | o conteúdo inteiro do ficheiro JSON |
| `ANTHROPIC_API_KEY` | a chave do passo 3 |
| `IG_ACCESS_TOKEN`, `IG_USER_ID` | só para o modo automático |

**5. Página de links.** Já está ativa em https://carolinafmar.github.io/carolcontents. Põe esse endereço na bio do Instagram.
Se aparecer um erro 404, vai a *Settings → Pages* e confirma *Deploy from a branch → main → /docs*.

**6. Primeiro teste.** Em *Actions → CarolContents → Run workflow*:
- `recolher` processa as stories que já estão no Drive;
- `forcar` monta já uma edição, mesmo com menos de 3 achados.

## Ajustes no `config.yaml`
- `start_month: "202610"`: ignora as stories anteriores a outubro de 2026.
  Se o deixares vazio, todo o arquivo entra e vai saindo em edições de 10 achados, uma por semana.
- `max_items`, `min_items`, `min_confidence`: o tamanho das edições e o rigor da identificação.
- `publish_mode: "automatico"`: publica sozinho. Precisa de uma conta profissional do Instagram ligada a uma página do Facebook e de um token com `instagram_content_publish`.

## Corrigir um achado
Em `data/state.json`, procura o ID da story (é o nome do ficheiro no Drive), corrige o `url` ou o `name` e muda `status` para `pendente`.
Para retirar um achado, muda o `status` para `ignorada`.

## Custos
- GitHub Actions e Pages: gratuitos.
- Claude: alguns cêntimos por story, porque cada uma inclui a análise da imagem e uma pesquisa web.
