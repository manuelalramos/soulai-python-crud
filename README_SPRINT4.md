<h1 align="center">🌱 SoulAI — Python</h1>

<p align="center">
  <b>Computational Thinking Using Python</b> · Sprint 4 · FIAP Challenge 2026 · Turma 1TDSPF
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Oracle-Database-F80000?style=for-the-badge&logo=oracle&logoColor=white" alt="Oracle"/>
  <img src="https://img.shields.io/badge/API-Open--Meteo-00979D?style=for-the-badge" alt="API"/>
  <img src="https://img.shields.io/badge/Status-Sprint%204-6e4bff?style=for-the-badge" alt="Status"/>
</p>

---

## 💡 Sobre o projeto

O **SoulAI** faz parte da plataforma **SoulUp** e incentiva hábitos sustentáveis por meio
de gamificação: missões, moedas, ofensiva (foguinho) e um avatar personalizável.

Este repositório contém a parte em **Python** da solução — a camada de dados e
administração. Partindo da base da Sprint 3, esta sprint acrescenta:

- 🗄️ **CRUD de missões no banco Oracle** (inserir, consultar, alterar e excluir)
- 🌍 **Consumo de uma API pública** (qualidade do ar — Open-Meteo)
- 📄 **Exportação de consultas para JSON**
- 🔗 **Integração com o site:** o que o Python altera no banco reflete no front-end (e vice-versa)

---

## 👥 Integrantes

| Nome | RM |
|------|-----|
| Lena Haidar Halawi | 572258 |
| Lyvia Correa de Amorim | 569851 |
| Manuela de Lima Ramos | 572956 |
| Yasmin Souza Silva Martins | 572102 |

---

## 🔗 Links

| Recurso | Link |
|---------|------|
| 🎥 Vídeo (YouTube) | _preencher antes da entrega_ |
| 🌐 Site publicado | https://soul-ai-projeto.vercel.app/ |
| 💻 Repositório do front-end | https://github.com/manuelalramos/SoulAi_Projeto |
| ☕ API Java | https://soulai-api.onrender.com |

---

## ✨ Funcionalidades

- 👤 Cadastro e login de usuário (e-mail e senha)
- 🎯 Missões vindas do Oracle, com conclusão e recompensa
- ♻️ Registro de ações sustentáveis (moedas e energia)
- 🛍️ Loja e inventário do avatar (comprar e equipar)
- 📊 Ranking, histórico e filtros
- 💬 Conversa com o avatar por palavras-chave
- 🛠️ CRUD completo (usuários, missões, ações e acessórios)
- 📄 Exportação de consultas para JSON
- 🌬️ Consulta de qualidade do ar (API Open-Meteo)

---

## 🚀 Como executar

> Requer **Python 3** instalado (revisado com a versão 3.12).

**1. Instale a dependência:**

```bash
python -m pip install -r requirements.txt
```

**2. Configure o acesso ao banco por variáveis de ambiente.**

Por segurança, o usuário e a senha do Oracle **não ficam no código** — são lidos de
variáveis de ambiente. As credenciais de acesso ficam no **documento de entrega (PDF)**.

<details>
<summary><b>Windows (CMD)</b></summary>

```cmd
set ORACLE_USER=seu_usuario_oracle
set ORACLE_PASSWORD=sua_senha_oracle
set ORACLE_DSN=oracle.fiap.com.br:1521/ORCL
python soul_ai_challenge.py
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
$env:ORACLE_USER="seu_usuario_oracle"
$env:ORACLE_PASSWORD="sua_senha_oracle"
$env:ORACLE_DSN="oracle.fiap.com.br:1521/ORCL"
python soul_ai_challenge.py
```
</details>

<details>
<summary><b>Linux / macOS</b></summary>

```bash
export ORACLE_USER=seu_usuario_oracle
export ORACLE_PASSWORD=sua_senha_oracle
export ORACLE_DSN=oracle.fiap.com.br:1521/ORCL
python3 soul_ai_challenge.py
```
</details>

> As variáveis valem só para aquela janela do terminal. Também é possível preenchê-las
> direto no dicionário `CONFIGURACAO_ORACLE`, no início de `soul_ai_challenge.py`.
> É necessário estar na **rede da FIAP** para acessar o Oracle.

---

## 🗂️ Menus do sistema

| Opção | Função |
|-------|--------|
| 1 | Status do usuário (saldo, ofensiva, avatar, progresso) |
| 2 | Missões — listar e concluir |
| 3 | Ações sustentáveis — consultar e registrar |
| 4 | Avatar, loja e inventário |
| 5 | Conversa com o SoulAI |
| 6 | CRUD (usuários, missões, ações, acessórios) |
| 7 | Relatórios, filtros e exportação |
| 8 | Salvar dados locais |
| 9 | Qualidade do ar (API pública) |
| 0 | Voltar / sair |

---

## 🗄️ Banco de dados e integração

O CRUD no Oracle usa a entidade **`MISSAO`**, com as colunas do DDL do grupo
(`ID_MISSAO`, `TITULO_MISSAO`, `DESCRICAO_MISSAO`, `ATIVO`, `VALOR_MOEDAS_MISSAO`,
`ADMINISTRADOR_ID_ADMINISTRADOR`).

- O banco gera o ID automaticamente; o cadastro usa o **administrador de ID 1** (admin@soulup.com).
- A conexão usa `oracledb` com **consultas parametrizadas** (bind variables).
- Escritas são confirmadas com **`commit`** e desfeitas com **`rollback`** em caso de erro.
- As missões criadas/alteradas/excluídas no Python **refletem no site**, pois ambos usam
  o mesmo schema Oracle.

---

## 🌬️ API pública — Open-Meteo

A opção **9** consulta a [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api)
(dados do Copernicus CAMS, **sem necessidade de chave**). Mostra o índice de qualidade do
ar e as partículas PM2,5 e PM10 de uma cidade, com tratamento de erros de rede e resposta.
Conecta com o tema do projeto ao trazer uma condição ambiental real.

---

## 🧩 Organização do código

Arquivo único, dividido em funções com comentários curtos. Usa **listas de dicionários**,
laços `for`/`while`, condições, uma função **`lambda`** no ranking, escrita de **JSON** e
**tratamento de erros** (`try`/`except`/`else`/`finally`) nas operações sensíveis.

```text
soul_ai_challenge.py     # programa principal
requirements.txt         # dependências (oracledb)
README_SPRINT4.md        # este arquivo
```

---

## ⚠️ Limitações conhecidas

- O menu de **CRUD fica acessível a qualquer usuário logado** (sem separação de
  administrador nesta versão) — limitação assumida para o escopo da sprint.
- Apenas a entidade **Missão** é compartilhada com o site; as demais ficam em JSON local.
- O benefício na conta de luz é uma **simulação**, não aplica desconto real.

---

## 🤖 Uso de IA

A IA foi usada como **apoio** (uma "segunda mão"), e não como substituta do trabalho da
equipe — todo o conteúdo foi decidido, testado e compreendido pelo grupo. Ela auxiliou na
pesquisa da integração com o Oracle e a API, na **correção de bugs**, em **boas práticas de
segurança** (tirar a senha do código), no tratamento de erros e na organização/documentação.
As sugestões foram trabalhadas a partir do programa que já existia e revisadas pela equipe.
O registro completo do uso de IA, com os prompts, está no documento de entrega.

---

<p align="center"><i>Projeto acadêmico — FIAP Challenge 2026 · SoulAI (SoulUp)</i></p>