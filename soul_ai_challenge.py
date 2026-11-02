import copy
import hashlib
import http.client
import json
import math
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

try:
    import oracledb
except ImportError:
    oracledb = None


ARQUIVO_DADOS = "soulai_dados.json"
SIM = "S"
NAO = "N"
TIPOS_ACESSORIO = ["roupa", "acessorio"]
RARIDADES = ["comum", "raro", "epico", "lendario"]
EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

# acesso ao mesmo banco usado no java
# as credenciais vem de variaveis de ambiente pra nao ficar senha escrita no codigo
# (as instrucoes de como configurar estao no README e no documento de entrega)
CONFIGURACAO_ORACLE = {
    "usuario": os.getenv("ORACLE_USER", ""),
    "senha": os.getenv("ORACLE_PASSWORD", ""),
    "dsn": os.getenv("ORACLE_DSN", "oracle.fiap.com.br:1521/ORCL"),
}
URL_QUALIDADE_AR = "https://air-quality-api.open-meteo.com/v1/air-quality"
ENERGIA_PADRAO_MISSAO = 20

RECOMPENSAS_POR_NIVEL = {
    1: 1,
    2: 2,
    3: 4,
}

DADOS_INICIAIS = {
    "usuarios": [],
    "missoes": [
        {
            "id": 1,
            "titulo": "Curtir um conteúdo sustentável",
            "descricao": "Interagir com uma publicação sobre sustentabilidade na SoulUp.",
            "valor_moedas": 10,
            "energia": 15,
            "ativo": SIM,
        },
        {
            "id": 2,
            "titulo": "Comentar uma dica ecológica",
            "descricao": "Comentar uma ação simples para economizar recursos no dia a dia.",
            "valor_moedas": 15,
            "energia": 20,
            "ativo": SIM,
        },
        {
            "id": 3,
            "titulo": "Participar de uma comunidade verde",
            "descricao": "Entrar em uma comunidade de pessoas interessadas em hábitos sustentáveis.",
            "valor_moedas": 25,
            "energia": 30,
            "ativo": SIM,
        },
        {
            "id": 4,
            "titulo": "Postar uma ação sustentável",
            "descricao": "Registrar uma prática real, como reciclagem ou economia de energia.",
            "valor_moedas": 35,
            "energia": 40,
            "ativo": SIM,
        },
        {
            "id": 5,
            "titulo": "Economizar energia durante o dia",
            "descricao": "Simular a redução do consumo elétrico em casa ou na faculdade.",
            "valor_moedas": 30,
            "energia": 35,
            "ativo": SIM,
        },
    ],
    "acoes_sustentaveis": [
        {
            "id": 1,
            "titulo": "Separar lixo reciclável",
            "categoria": "reciclagem",
            "valor_moedas": 20,
            "energia": 25,
            "ativo": SIM,
        },
        {
            "id": 2,
            "titulo": "Usar transporte coletivo",
            "categoria": "mobilidade",
            "valor_moedas": 30,
            "energia": 30,
            "ativo": SIM,
        },
        {
            "id": 3,
            "titulo": "Reduzir tempo de banho",
            "categoria": "água",
            "valor_moedas": 25,
            "energia": 25,
            "ativo": SIM,
        },
    ],
    "acessorios": [
        {
            "id": 1,
            "nome": "Chapéu Verde",
            "tipo": "acessorio",
            "raridade": "comum",
            "preco": 30,
        },
        {
            "id": 2,
            "nome": "Camiseta Eco",
            "tipo": "roupa",
            "raridade": "comum",
            "preco": 45,
        },
        {
            "id": 3,
            "nome": "Mochila Sustentável",
            "tipo": "acessorio",
            "raridade": "raro",
            "preco": 70,
        },
        {
            "id": 4,
            "nome": "Jaqueta Solar",
            "tipo": "roupa",
            "raridade": "epico",
            "preco": 100,
        },
    ],
    "usuario_missoes": [],
    "usuario_acoes": [],
    "inventario": [],
    "conversas": [],
    "energia_missoes": [],
}



def obter_caminho_dados():
    pasta_atual = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(pasta_atual, ARQUIVO_DADOS)


def criar_dados_iniciais():
    dados = copy.deepcopy(DADOS_INICIAIS)
    dados["missoes"] = []
    return dados


def normalizar_estrutura_dados(dados):
    padrao = criar_dados_iniciais()

    for chave in padrao:
        if chave not in dados or not isinstance(dados[chave], list):
            dados[chave] = padrao[chave]

    for usuario in dados["usuarios"]:
        if usuario.get("avatar_roupa") == "Padrao":
            usuario["avatar_roupa"] = "Padrão"

    for acessorio in dados["acessorios"]:
        acessorio["tipo"] = normalizar_tipo_acessorio(acessorio.get("tipo", ""))
        acessorio["raridade"] = normalizar_raridade(acessorio.get("raridade", ""))

    # separa os ids locais antigos dos ids do banco
    for historico in dados["usuario_missoes"]:
        if "origem" not in historico:
            historico["origem"] = "json"
            missao = buscar_por_id(dados["missoes"], historico.get("missao_id"))
            if missao is not None:
                historico["titulo"] = missao["titulo"]

    dados["missoes"] = []
    return dados


def carregar_dados():
    caminho = obter_caminho_dados()

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        print("\n[INFO] Nenhum arquivo salvo encontrado. A base padrão será usada.")
        dados = criar_dados_iniciais()
    except json.JSONDecodeError:
        print("\n[AVISO] O arquivo JSON está corrompido. A base padrão será usada.")
        dados = criar_dados_iniciais()
    except OSError as erro:
        print("\n[ERRO] Erro de acesso ao arquivo de dados:", erro)
        dados = criar_dados_iniciais()
    else:
        dados = normalizar_estrutura_dados(dados)
    finally:
        pass

    return dados


def salvar_dados(dados):
    # salva só os dados locais; as missões ficam no oracle
    caminho = obter_caminho_dados()
    salvou = False
    dados_locais = dados.copy()
    dados_locais.pop("missoes", None)

    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(dados_locais, arquivo, ensure_ascii=False, indent=4)
    except OSError as erro:
        mostrar_feedback("erro", "Não foi possível salvar os dados: " + str(erro))
    else:
        salvou = True
    finally:
        pass

    return salvou



def abrir_conexao_oracle():
    if oracledb is None:
        mostrar_feedback("erro", "Instale a dependência: python -m pip install -r requirements.txt")
        return None
    if not CONFIGURACAO_ORACLE["usuario"] or not CONFIGURACAO_ORACLE["senha"]:
        mostrar_feedback("aviso", "Preencha usuario e senha em CONFIGURACAO_ORACLE, no início do código.")
        return None

    conexao = None
    try:
        conexao = oracledb.connect(
            user=CONFIGURACAO_ORACLE["usuario"],
            password=CONFIGURACAO_ORACLE["senha"],
            dsn=CONFIGURACAO_ORACLE["dsn"],
            tcp_connect_timeout=10,
            retry_count=0,
        )
        conexao.call_timeout = 10000
    except oracledb.Error:
        mostrar_feedback("erro", "Não foi possível conectar ao Oracle. Confira acesso, rede e DSN.")
        fechar_recursos_oracle(None, conexao)
        return None
    else:
        return conexao


def fechar_recursos_oracle(cursor, conexao):
    for recurso in [cursor, conexao]:
        if recurso is not None:
            try:
                recurso.close()
            except oracledb.Error:
                mostrar_feedback("aviso", "Não foi possível encerrar um recurso do Oracle.")


def desfazer_operacao_oracle(conexao):
    try:
        conexao.rollback()
    except oracledb.Error:
        mostrar_feedback("aviso", "Falha ao desfazer a operação. Confira o banco antes de repetir.")


def mostrar_erro_oracle(erro):
    # alguns erros vem sem argumentos, entao conferimos antes de pegar o primeiro
    detalhe = erro.args[0] if erro.args else None
    codigo = getattr(detalhe, "code", None)
    mensagens = {
        1: "Já existe um registro com estes dados.",
        1400: "O banco exige um campo obrigatório que não foi informado. Confira o DDL.",
        2291: "O administrador informado não existe no banco.",
        2292: "Esta missão tem registros vinculados no banco. Desative a missão para preservar o histórico.",
        12899: "Um texto ultrapassa o tamanho permitido pelo banco. Confira o DDL.",
        942: "A tabela não foi encontrada. Confira o schema usado pelo Java.",
        904: "Uma coluna não foi encontrada. Confira os nomes no DDL do projeto.",
    }
    mensagem = mensagens.get(codigo, "A operação no Oracle falhou. Confira a conexão e o esquema do projeto.")
    mostrar_feedback("erro", mensagem)


def consultar_oracle(sql, parametros=()):
    conexao = abrir_conexao_oracle()
    if conexao is None:
        return None
    cursor = None
    linhas = None

    try:
        cursor = conexao.cursor()
        cursor.execute(sql, parametros)
        linhas = cursor.fetchall()
    except oracledb.Error as erro:
        mostrar_erro_oracle(erro)
    finally:
        fechar_recursos_oracle(cursor, conexao)

    return linhas


def escrever_oracle(sql, parametros, retornar_id=False):
    # commit confirma a escrita; rollback desfaz se der erro
    conexao = abrir_conexao_oracle()
    if conexao is None:
        return False
    cursor = None
    resultado = False

    try:
        cursor = conexao.cursor()
        valores = list(parametros)
        if retornar_id:
            id_gerado = cursor.var(int)
            valores.append(id_gerado)
        cursor.execute(sql, valores)
        if cursor.rowcount != 1:
            raise LookupError("Missão não encontrada ou removida por outra pessoa.")
        novo_id = id_gerado.getvalue()[0] if retornar_id else True
        conexao.commit()
    except oracledb.Error as erro:
        desfazer_operacao_oracle(conexao)
        mostrar_erro_oracle(erro)
    except LookupError as erro:
        desfazer_operacao_oracle(conexao)
        mostrar_feedback("erro", str(erro))
    else:
        resultado = novo_id
    finally:
        fechar_recursos_oracle(cursor, conexao)

    return resultado


def consultar_missoes_oracle(dados):
    # a energia fica local porque não existe essa coluna em missao
    linhas = consultar_oracle(
        """SELECT ID_MISSAO, TITULO_MISSAO, DESCRICAO_MISSAO, ATIVO,
                  VALOR_MOEDAS_MISSAO, ADMINISTRADOR_ID_ADMINISTRADOR
           FROM MISSAO ORDER BY ID_MISSAO"""
    )
    if linhas is None:
        return None

    missoes = []
    for linha in linhas:
        energia_local = buscar_por_id(dados["energia_missoes"], int(linha[0]))
        energia = ENERGIA_PADRAO_MISSAO
        if energia_local is not None:
            energia = energia_local["energia"]
        # usa 0 quando o banco devolve nulo, pra nao quebrar o int()
        missoes.append({
            "id": int(linha[0]),
            "titulo": linha[1],
            "descricao": linha[2],
            "ativo": linha[3],
            "valor_moedas": int(linha[4]) if linha[4] is not None else 0,
            "administrador_id": int(linha[5]) if linha[5] is not None else 0,
            "energia": energia,
        })

    return missoes


def atualizar_missoes_oracle(dados):
    missoes = consultar_missoes_oracle(dados)
    dados["missoes"] = [] if missoes is None else missoes
    return missoes is not None


def guardar_energia_missao(dados, id_missao, energia):
    registro = buscar_por_id(dados["energia_missoes"], id_missao)
    if registro is None:
        dados["energia_missoes"].append({"id": id_missao, "energia": energia})
    else:
        registro["energia"] = energia


def buscar_conclusao_missao(dados, usuario_id, missao_id):
    for historico in dados["usuario_missoes"]:
        if (historico.get("origem") == "oracle" and historico["usuario_id"] == usuario_id
                and historico["missao_id"] == missao_id):
            return historico
    return None


def listar_missoes_oracle(dados):
    if not atualizar_missoes_oracle(dados):
        return False
    listar_registros(
        "MISSÕES CADASTRADAS NO ORACLE", dados["missoes"],
        [("titulo", "Título"), ("descricao", "Descrição"), ("valor_moedas", "Moedas"),
         ("energia", "Energia local"), ("ativo", "Ativo"), ("administrador_id", "ID do administrador")],
    )
    return True


def exportar_missoes_json(dados):
    if not atualizar_missoes_oracle(dados):
        return False
    nome = "relatorio_missoes_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json"
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), nome)
    relatorio = {"gerado_em": data_atual_texto(), "origem": "Oracle - MISSAO", "missoes": []}
    for missao in dados["missoes"]:
        relatorio["missoes"].append({
            "ID_MISSAO": missao["id"], "TITULO_MISSAO": missao["titulo"],
            "DESCRICAO_MISSAO": missao["descricao"], "ATIVO": missao["ativo"],
            "VALOR_MOEDAS_MISSAO": missao["valor_moedas"],
            "ADMINISTRADOR_ID_ADMINISTRADOR": missao["administrador_id"],
        })
    salvou = False
    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(relatorio, arquivo, ensure_ascii=False, indent=4)
    except OSError:
        mostrar_feedback("erro", "Não foi possível escrever o relatório. Confira a permissão da pasta.")
    else:
        salvou = True
        mostrar_feedback("sucesso", "Relatório gerado em " + caminho)
    finally:
        pass
    return salvou


def data_atual_texto():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")



def gerar_proximo_id(registros):
    if len(registros) == 0:
        return 1

    maior_id = 0
    for registro in registros:
        if registro.get("id", 0) > maior_id:
            maior_id = registro.get("id", 0)

    return maior_id + 1


def buscar_por_id(registros, id_registro):
    for registro in registros:
        if registro.get("id") == id_registro:
            return registro

    return None


def filtrar_por_campo(registros, campo, termo):
    filtrados = []
    termo = termo.lower().strip()

    for registro in registros:
        valor = str(registro.get(campo, "")).lower()
        if termo in valor:
            filtrados.append(registro)

    return filtrados


def buscar_usuario_por_email(usuarios, email):
    email = email.lower().strip()

    for usuario in usuarios:
        if usuario.get("email", "").lower() == email:
            return usuario

    return None


def criar_hash_senha(senha):
    salt = secrets.token_hex(8)
    senha_hash = hashlib.sha256((salt + senha).encode("utf-8")).hexdigest()
    return salt + "$" + senha_hash


def conferir_senha(senha_digitada, senha_salva):
    try:
        salt, senha_hash = senha_salva.split("$")
    except ValueError:
        return False

    hash_digitado = hashlib.sha256((salt + senha_digitada).encode("utf-8")).hexdigest()
    return hash_digitado == senha_hash



def ler_texto(mensagem, minimo=1, maximo=100, permitir_vazio=False):
    while True:
        texto = input(mensagem).strip()

        if permitir_vazio and texto == "":
            return texto

        if len(texto) < minimo:
            mostrar_feedback("erro", "Entrada inválida. Digite pelo menos " + str(minimo) + " caracteres.")
        elif len(texto) > maximo:
            mostrar_feedback("erro", "Entrada inválida. Digite no máximo " + str(maximo) + " caracteres.")
        else:
            return texto


def ler_inteiro(mensagem, minimo=None, maximo=None):
    while True:
        try:
            valor = int(input(mensagem).strip())
        except ValueError:
            mostrar_feedback("erro", "Entrada inválida. Digite apenas números inteiros.")
        else:
            if minimo is not None and valor < minimo:
                mostrar_feedback("erro", "Valor inválido. O mínimo permitido é " + str(minimo) + ".")
            elif maximo is not None and valor > maximo:
                mostrar_feedback("erro", "Valor inválido. O máximo permitido é " + str(maximo) + ".")
            else:
                return valor
        finally:
            pass


def ler_opcao(opcoes_validas, mensagem="Escolha uma opção: "):
    while True:
        opcao = input(mensagem).strip()

        if opcao in opcoes_validas:
            return opcao

        mostrar_feedback("erro", "Opção inválida. Tente novamente.")


def mostrar_feedback(tipo, mensagem):
    rotulos = {
        "sucesso": "[OK]",
        "erro": "[ERRO]",
        "aviso": "[AVISO]",
        "info": "[INFO]",
    }
    rotulo = rotulos.get(tipo, "[INFO]")
    print("\n" + rotulo, mensagem)


def montar_barra_progresso(percentual, largura=24):
    percentual = max(0, min(100, int(percentual)))
    preenchidos = round((percentual / 100) * largura)
    vazios = largura - preenchidos
    return "[" + "#" * preenchidos + "-" * vazios + "] " + str(percentual) + "%"


def mostrar_variacao_progresso(rotulo, valor_anterior, valor_atual):
    print(rotulo + ":")
    print("Antes :", montar_barra_progresso(valor_anterior))
    print("Depois:", montar_barra_progresso(valor_atual))


def validar_email(email):
    email = email.strip().lower()

    if re.match(EMAIL_REGEX, email) is None:
        return False
    if ".." in email:
        return False

    dominio = email.split("@")[1]
    if dominio[0] == "." or dominio[len(dominio) - 1] == ".":
        return False

    return True


def ler_email(usuarios, email_atual=None):
    while True:
        email = ler_texto("E-mail: ", 6, 120).lower()

        if not validar_email(email):
            mostrar_feedback("erro", "Formato de e-mail inválido. Exemplo aceito: nome@email.com")
            continue

        usuario_existente = buscar_usuario_por_email(usuarios, email)
        if usuario_existente is not None and email != email_atual:
            mostrar_feedback("erro", "Este e-mail já está cadastrado. Use outro e-mail ou faça login.")
            continue

        return email


def ler_senha():
    while True:
        senha = ler_texto("Senha (mínimo 6 caracteres): ", 6, 40)
        confirmar = ler_texto("Confirme a senha: ", 6, 40)

        if senha != confirmar:
            mostrar_feedback("erro", "As senhas não conferem.")
        else:
            return senha


def confirmar_operacao(mensagem):
    resposta = input(mensagem + " (S/N): ").strip().upper()

    while resposta not in [SIM, NAO]:
        print("Resposta inválida. Digite S ou N.")
        resposta = input(mensagem + " (S/N): ").strip().upper()

    return resposta == SIM


def pausar():
    input("\nPressione Enter para continuar...")


def mostrar_titulo(titulo):
    largura = 68
    print("\n" + "-" * largura)
    print(titulo.center(largura))
    print("-" * largura)


def normalizar_tipo_acessorio(tipo):
    tipo = str(tipo).strip().lower()

    if tipo == "acessório":
        return "acessorio"

    return tipo


def normalizar_raridade(raridade):
    raridade = str(raridade).strip().lower()

    if raridade == "épico":
        return "epico"
    if raridade == "lendário":
        return "lendario"

    return raridade


def formatar_tipo_acessorio(tipo):
    if tipo == "acessorio":
        return "acessório"

    return tipo


def formatar_raridade(raridade):
    if raridade == "epico":
        return "épico"
    if raridade == "lendario":
        return "lendário"

    return raridade


def formatar_valor_campo(chave, valor):
    if chave == "tipo":
        return formatar_tipo_acessorio(valor)
    if chave == "raridade":
        return formatar_raridade(valor)

    return valor


def mostrar_registro(registro, campos):
    for chave, rotulo in campos:
        print(rotulo + ":", formatar_valor_campo(chave, registro.get(chave)))


def listar_registros(titulo, registros, campos):
    mostrar_titulo(titulo)

    if len(registros) == 0:
        print("Nenhum registro encontrado.")
        return

    for registro in registros:
        print("\nID:", registro.get("id"))
        mostrar_registro(registro, campos)


def criar_registro(lista, registro, nome_entidade):
    inseriu = False

    try:
        if "id" not in registro:
            raise ValueError("Registro sem ID.")
        if buscar_por_id(lista, registro["id"]) is not None:
            raise ValueError("ID já existente.")
        lista.append(registro)
    except ValueError as erro:
        mostrar_feedback("erro", "Erro ao inserir " + nome_entidade + ": " + str(erro))
    except TypeError as erro:
        mostrar_feedback("erro", "Erro de tipo ao inserir " + nome_entidade + ": " + str(erro))
    else:
        inseriu = True
        mostrar_feedback("sucesso", nome_entidade + " cadastrado(a) com sucesso.")
    finally:
        pass

    return inseriu


def alterar_registro(lista, id_registro, novos_dados, nome_entidade):
    alterou = False

    try:
        registro = buscar_por_id(lista, id_registro)
        if registro is None:
            raise LookupError("Registro não encontrado.")
        if len(novos_dados) == 0:
            raise ValueError("Nenhum campo foi alterado.")

        for chave in novos_dados:
            registro[chave] = novos_dados[chave]
    except LookupError as erro:
        mostrar_feedback("erro", "Erro ao alterar " + nome_entidade + ": " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Erro ao alterar " + nome_entidade + ": " + str(erro))
    else:
        alterou = True
        mostrar_feedback("sucesso", nome_entidade + " alterado(a) com sucesso.")
    finally:
        pass

    return alterou


def excluir_registro(lista, id_registro, nome_entidade):
    excluiu = False

    try:
        registro = buscar_por_id(lista, id_registro)
        if registro is None:
            raise LookupError("Registro não encontrado.")

        lista.remove(registro)
    except LookupError as erro:
        mostrar_feedback("erro", "Erro ao excluir " + nome_entidade + ": " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Erro ao excluir " + nome_entidade + ": " + str(erro))
    else:
        excluiu = True
        mostrar_feedback("sucesso", nome_entidade + " excluído(a) com sucesso.")
    finally:
        pass

    return excluiu


def montar_usuario(dados):
    nome = ler_texto("Nome do usuário: ", 3, 80)
    email = ler_email(dados["usuarios"])
    senha = ler_senha()

    return {
        "id": gerar_proximo_id(dados["usuarios"]),
        "nome": nome,
        "email": email,
        "senha_hash": criar_hash_senha(senha),
        "saldo_moedas": 0,
        "nivel_ofensiva": 0,
        "energia_ofensiva": 0,
        "avatar_nome": "SoulAI",
        "avatar_roupa": "Padrão",
        "avatar_acessorio": "Nenhum",
        "criado_em": data_atual_texto(),
    }



def cadastrar_usuario(dados, retornar_usuario=False):
    mostrar_titulo("CADASTRO DE USUÁRIO")
    usuario = montar_usuario(dados)
    cadastrou = criar_registro(dados["usuarios"], usuario, "Usuário")

    if retornar_usuario and cadastrou:
        return usuario
    if retornar_usuario:
        return None

    return cadastrou


def realizar_login(dados):
    mostrar_titulo("LOGIN")

    email = ler_texto("E-mail: ", 6, 120).lower()
    if not validar_email(email):
        mostrar_feedback("erro", "E-mail em formato inválido. Digite algo como nome@email.com.")
        return None

    senha = ler_texto("Senha: ", 1, 40)
    usuario = buscar_usuario_por_email(dados["usuarios"], email)

    if usuario is None:
        mostrar_feedback("erro", "Não encontramos usuário com esse e-mail.")
        return None

    if not conferir_senha(senha, usuario.get("senha_hash", "")):
        mostrar_feedback("erro", "Usuário encontrado, mas a senha está incorreta.")
        return None

    mostrar_feedback("sucesso", "Login realizado com sucesso. Bem-vindo(a), " + usuario["nome"] + "!")
    return usuario


def menu_acesso(dados):
    usuario_logado = None

    while usuario_logado is None:
        mostrar_titulo("SOULAI - ACESSO")
        print("1 - Entrar com usuário existente")
        print("2 - Cadastrar novo usuário")
        print("0 - Sair")

        opcao = ler_opcao(["1", "2", "0"])

        if opcao == "1":
            usuario_logado = realizar_login(dados)
            if usuario_logado is None:
                pausar()
        elif opcao == "2":
            usuario_criado = cadastrar_usuario(dados, True)
            if usuario_criado is not None:
                salvar_dados(dados)
                usuario_logado = usuario_criado
                mostrar_feedback("sucesso", "Cadastro concluído. Você já está logado(a).")
            pausar()
        elif opcao == "0":
            return None

    return usuario_logado


def obter_usuario_atualizado(dados, usuario):
    if usuario is None:
        return None

    return buscar_por_id(dados["usuarios"], usuario["id"])


def contar_historico(registros, usuario_id):
    contador = 0

    for registro in registros:
        if registro.get("usuario_id") == usuario_id:
            contador += 1

    return contador


def calcular_beneficio_conta_luz(saldo_moedas):
    return saldo_moedas * 0.10


def mostrar_status_usuario(usuario, dados):
    mostrar_titulo("STATUS DO USUÁRIO")
    print("Nome:", usuario["nome"])
    print("E-mail:", usuario["email"])
    print("Moedas disponíveis:", usuario["saldo_moedas"])
    print("Ofensiva:", montar_barra_progresso(usuario["energia_ofensiva"]))
    print("Nível de ofensiva:", usuario["nivel_ofensiva"])
    print("Avatar:", usuario["avatar_nome"])
    print("Roupa equipada:", usuario["avatar_roupa"])
    print("Acessório equipado:", usuario["avatar_acessorio"])
    print("Missões concluídas:", contar_historico(dados["usuario_missoes"], usuario["id"]))
    print("Ações sustentáveis registradas:", contar_historico(dados["usuario_acoes"], usuario["id"]))
    print("Benefício estimado na conta de luz: R$ {:.2f}".format(calcular_beneficio_conta_luz(usuario["saldo_moedas"])))


def listar_missoes_disponiveis(dados, usuario):
    if not atualizar_missoes_oracle(dados):
        return False
    mostrar_titulo("MISSÕES DISPONÍVEIS")
    # se nao tem missao, mostra so o aviso e sai (sem imprimir o cabecalho vazio)
    if len(dados["missoes"]) == 0:
        print("Nenhuma missão cadastrada no Oracle.")
        return True
    print("{:<4} {:<36} {:>7} {:>9} {:<12} {:<12}".format("ID", "Missão", "Moedas", "Energia", "Catálogo", "Usuário"))
    print("-" * 88)

    for missao in dados["missoes"]:
        status = "inativa"
        if missao["ativo"] == SIM:
            status = "ativa"

        concluida = buscar_conclusao_missao(dados, usuario["id"], missao["id"])
        status_usuario = "pendente"
        if concluida is not None:
            status_usuario = "concluída"

        print(
            "{:<4} {:<36} {:>7} {:>8}% {:<12} {:<12}".format(
                missao["id"],
                missao["titulo"][:36],
                missao["valor_moedas"],
                missao["energia"],
                status,
                status_usuario,
            )
        )
    return True



def listar_acoes_disponiveis(dados, usuario):
    mostrar_titulo("AÇÕES SUSTENTÁVEIS")
    print("{:<4} {:<32} {:<14} {:>7} {:>9} {:<12}".format("ID", "Ação", "Categoria", "Moedas", "Energia", "Usuário"))
    print("-" * 88)

    for acao in dados["acoes_sustentaveis"]:
        status = "inativa"
        if acao["ativo"] == SIM:
            status = "ativa"

        concluida = buscar_relacao_usuario_item(
            dados["usuario_acoes"],
            usuario["id"],
            "acao_id",
            acao["id"],
        )
        status_usuario = "pendente"
        if concluida is not None:
            status_usuario = "registrada"

        print(
            "{:<4} {:<32} {:<14} {:>7} {:>8}% {:<12}".format(
                acao["id"],
                acao["titulo"][:32],
                acao["categoria"][:14],
                acao["valor_moedas"],
                acao["energia"],
                status_usuario + "/" + status,
            )
        )


def buscar_relacao_usuario_item(registros, usuario_id, campo_item, item_id):
    for registro in registros:
        if registro.get("usuario_id") == usuario_id and registro.get(campo_item) == item_id:
            return registro

    return None


def conceder_recompensa_por_nivel(dados, usuario, mensagens):
    nivel = usuario["nivel_ofensiva"]
    acessorio_id = RECOMPENSAS_POR_NIVEL.get(nivel)

    if acessorio_id is None:
        return

    acessorio = buscar_por_id(dados["acessorios"], acessorio_id)
    if acessorio is None:
        return

    item_existente = buscar_relacao_usuario_item(
        dados["inventario"],
        usuario["id"],
        "acessorio_id",
        acessorio_id,
    )

    if item_existente is not None:
        return

    dados["inventario"].append(
        {
            "id": gerar_proximo_id(dados["inventario"]),
            "usuario_id": usuario["id"],
            "acessorio_id": acessorio_id,
            "adquirido": SIM,
            "equipado": NAO,
            "origem": "recompensa de nível",
            "data": data_atual_texto(),
        }
    )
    mensagens.append("Recompensa desbloqueada: " + acessorio["nome"])


def avaliar_ofensiva(dados, usuario):
    mensagens = []

    while usuario["energia_ofensiva"] >= 100:
        usuario["energia_ofensiva"] -= 100
        usuario["nivel_ofensiva"] += 1
        usuario["saldo_moedas"] += 5
        mensagens.append("Ofensiva completa! Nível aumentado e 5 moedas extras recebidas.")
        conceder_recompensa_por_nivel(dados, usuario, mensagens)

    return mensagens


def concluir_missao(dados, usuario, missao_id):
    concluiu = False
    if not atualizar_missoes_oracle(dados):
        return False

    try:
        missao = buscar_por_id(dados["missoes"], missao_id)
        if missao is None:
            raise LookupError("Missão não encontrada.")
        if missao["ativo"] != SIM:
            raise ValueError("Missão indisponível no momento.")

        historico = buscar_conclusao_missao(dados, usuario["id"], missao_id)
        if historico is not None:
            raise ValueError("Esta missão já foi concluída por este usuário.")

        energia_anterior = usuario["energia_ofensiva"]
        dados["usuario_missoes"].append(
            {
                "id": gerar_proximo_id(dados["usuario_missoes"]),
                "usuario_id": usuario["id"],
                "missao_id": missao_id,
                "origem": "oracle",
                "titulo": missao["titulo"],
                "concluida": SIM,
                "progresso": 100,
                "moedas_ganhas": missao["valor_moedas"],
                "energia_ganha": missao["energia"],
                "data": data_atual_texto(),
            }
        )
        usuario["saldo_moedas"] += missao["valor_moedas"]
        usuario["energia_ofensiva"] += missao["energia"]
        mensagens = avaliar_ofensiva(dados, usuario)
    except LookupError as erro:
        mostrar_feedback("erro", "Não foi possível concluir a missão: " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Não foi possível concluir a missão: " + str(erro))
    else:
        concluiu = True
        mostrar_feedback("sucesso", "Missão concluída: " + missao["titulo"])
        print("Moedas recebidas:", missao["valor_moedas"])
        print("Energia recebida:", str(missao["energia"]) + "%")
        mostrar_variacao_progresso("Ofensiva", energia_anterior, usuario["energia_ofensiva"])
        for mensagem in mensagens:
            mostrar_feedback("info", mensagem)
    finally:
        pass

    return concluiu


def registrar_acao_sustentavel(dados, usuario, acao_id):
    registrou = False

    try:
        acao = buscar_por_id(dados["acoes_sustentaveis"], acao_id)
        if acao is None:
            raise LookupError("Ação sustentável não encontrada.")
        if acao["ativo"] != SIM:
            raise ValueError("Ação sustentável indisponível no momento.")

        historico = buscar_relacao_usuario_item(
            dados["usuario_acoes"],
            usuario["id"],
            "acao_id",
            acao_id,
        )
        if historico is not None:
            raise ValueError("Esta ação já foi registrada por este usuário.")

        energia_anterior = usuario["energia_ofensiva"]
        dados["usuario_acoes"].append(
            {
                "id": gerar_proximo_id(dados["usuario_acoes"]),
                "usuario_id": usuario["id"],
                "acao_id": acao_id,
                "concluida": SIM,
                "moedas_ganhas": acao["valor_moedas"],
                "energia_ganha": acao["energia"],
                "data": data_atual_texto(),
            }
        )
        usuario["saldo_moedas"] += acao["valor_moedas"]
        usuario["energia_ofensiva"] += acao["energia"]
        mensagens = avaliar_ofensiva(dados, usuario)
    except LookupError as erro:
        mostrar_feedback("erro", "Não foi possível registrar a ação: " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Não foi possível registrar a ação: " + str(erro))
    else:
        registrou = True
        mostrar_feedback("sucesso", "Ação sustentável registrada: " + acao["titulo"])
        print("Moedas recebidas:", acao["valor_moedas"])
        print("Energia recebida:", str(acao["energia"]) + "%")
        mostrar_variacao_progresso("Ofensiva", energia_anterior, usuario["energia_ofensiva"])
        for mensagem in mensagens:
            mostrar_feedback("info", mensagem)
    finally:
        pass

    return registrou



def listar_loja(dados, usuario):
    mostrar_titulo("LOJA DO AVATAR")
    print("Saldo atual:", usuario["saldo_moedas"], "moedas")
    print()
    print("{:<4} {:<26} {:<11} {:<10} {:>7} {:<14}".format("ID", "Item", "Tipo", "Raridade", "Preço", "Status"))
    print("-" * 82)

    for acessorio in dados["acessorios"]:
        inventario = buscar_relacao_usuario_item(
            dados["inventario"],
            usuario["id"],
            "acessorio_id",
            acessorio["id"],
        )

        status = "não adquirido"
        if inventario is not None and inventario.get("adquirido") == SIM:
            status = "adquirido"
        if inventario is not None and inventario.get("equipado") == SIM:
            status = "equipado"

        print(
            "{:<4} {:<26} {:<11} {:<10} {:>7} {:<14}".format(
                acessorio["id"],
                acessorio["nome"][:26],
                formatar_tipo_acessorio(acessorio["tipo"]),
                formatar_raridade(acessorio["raridade"]),
                acessorio["preco"],
                status,
            )
        )


def comprar_acessorio(dados, usuario, acessorio_id):
    comprou = False

    try:
        acessorio = buscar_por_id(dados["acessorios"], acessorio_id)
        if acessorio is None:
            raise LookupError("Acessório não encontrado.")

        inventario = buscar_relacao_usuario_item(
            dados["inventario"],
            usuario["id"],
            "acessorio_id",
            acessorio_id,
        )
        if inventario is not None and inventario.get("adquirido") == SIM:
            raise ValueError("Este acessório já está no inventário.")

        preco = acessorio["preco"]
        if usuario["saldo_moedas"] < preco:
            faltam = preco - usuario["saldo_moedas"]
            raise ValueError("Saldo insuficiente. Faltam " + str(faltam) + " moedas.")

        usuario["saldo_moedas"] -= preco
        dados["inventario"].append(
            {
                "id": gerar_proximo_id(dados["inventario"]),
                "usuario_id": usuario["id"],
                "acessorio_id": acessorio_id,
                "adquirido": SIM,
                "equipado": NAO,
                "origem": "compra",
                "data": data_atual_texto(),
            }
        )
    except LookupError as erro:
        mostrar_feedback("erro", "Compra não realizada: " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Compra não realizada: " + str(erro))
    else:
        comprou = True
        mostrar_feedback("sucesso", "Compra realizada com sucesso: " + acessorio["nome"])
        print("Saldo restante:", usuario["saldo_moedas"])
    finally:
        pass

    return comprou


def equipar_acessorio(dados, usuario, acessorio_id):
    equipou = False

    try:
        acessorio = buscar_por_id(dados["acessorios"], acessorio_id)
        if acessorio is None:
            raise LookupError("Acessório não encontrado.")

        inventario = buscar_relacao_usuario_item(
            dados["inventario"],
            usuario["id"],
            "acessorio_id",
            acessorio_id,
        )
        if inventario is None or inventario.get("adquirido") != SIM:
            raise ValueError("Você ainda não adquiriu este acessório.")

        for item in dados["inventario"]:
            if item.get("usuario_id") == usuario["id"]:
                outro_acessorio = buscar_por_id(dados["acessorios"], item["acessorio_id"])
                if outro_acessorio is not None and outro_acessorio["tipo"] == acessorio["tipo"]:
                    item["equipado"] = NAO

        inventario["equipado"] = SIM

        if acessorio["tipo"] == "roupa":
            usuario["avatar_roupa"] = acessorio["nome"]
        else:
            usuario["avatar_acessorio"] = acessorio["nome"]
    except LookupError as erro:
        mostrar_feedback("erro", "Não foi possível equipar: " + str(erro))
    except ValueError as erro:
        mostrar_feedback("erro", "Não foi possível equipar: " + str(erro))
    else:
        equipou = True
        mostrar_feedback("sucesso", "Item equipado com sucesso: " + acessorio["nome"])
    finally:
        pass

    return equipou


def listar_inventario_usuario(dados, usuario):
    mostrar_titulo("INVENTÁRIO DO AVATAR")
    print("{:<4} {:<26} {:<11} {:<18} {:<9}".format("ID", "Item", "Tipo", "Origem", "Equipado"))
    print("-" * 74)

    encontrou = False
    for item in dados["inventario"]:
        if item.get("usuario_id") == usuario["id"] and item.get("adquirido") == SIM:
            acessorio = buscar_por_id(dados["acessorios"], item["acessorio_id"])
            if acessorio is not None:
                encontrou = True
                print(
                    "{:<4} {:<26} {:<11} {:<18} {:<9}".format(
                        acessorio["id"],
                        acessorio["nome"][:26],
                        formatar_tipo_acessorio(acessorio["tipo"]),
                        item["origem"][:18],
                        item["equipado"],
                    )
                )

    if not encontrou:
        print("Inventário vazio. Complete missões ou compre itens na loja.")


def mensagem_avatar(usuario):
    energia = usuario["energia_ofensiva"]

    if energia < 30:
        return "Comece com uma missão simples para aquecer sua ofensiva sustentável."
    if energia < 70:
        return "Você está evoluindo bem. Mais uma ação pode aproximar seu foguinho de 100%."
    if energia < 100:
        return "Falta pouco para completar a ofensiva e subir de nível."

    return "Ofensiva completa. Continue usando a plataforma para manter o ritmo."


def interagir_com_avatar(usuario):
    mostrar_titulo("AVATAR SOULAI")
    print("Olá,", usuario["nome"] + "!")
    print("Avatar:", usuario["avatar_nome"])
    print("Roupa:", usuario["avatar_roupa"])
    print("Acessório:", usuario["avatar_acessorio"])
    print("Mensagem:", mensagem_avatar(usuario))



def classificar_intencao(texto):
    texto_minusculo = texto.lower()
    entidades = {}

    if "missao" in texto_minusculo or "missão" in texto_minusculo:
        return "CONSULTAR_MISSAO", entidades
    if "acao" in texto_minusculo or "ação" in texto_minusculo or "sustentavel" in texto_minusculo or "sustentável" in texto_minusculo:
        entidades["tema"] = "sustentabilidade"
        return "CONSULTAR_ACAO", entidades
    if "loja" in texto_minusculo or "item" in texto_minusculo or "avatar" in texto_minusculo:
        return "CONSULTAR_AVATAR", entidades
    if "ofensiva" in texto_minusculo or "foguinho" in texto_minusculo:
        return "CONSULTAR_OFENSIVA", entidades

    return "CONVERSA_GERAL", entidades


def gerar_resposta_soulai(usuario, dados, intencao):
    if intencao == "CONSULTAR_MISSAO":
        if not atualizar_missoes_oracle(dados):
            return "Não consegui consultar as missões agora. Tente novamente mais tarde."
        total = len(dados["missoes"])
        feitas = 0
        for missao in dados["missoes"]:
            if buscar_conclusao_missao(dados, usuario["id"], missao["id"]) is not None:
                feitas += 1
        return "Você concluiu {} de {} missões cadastradas.".format(feitas, total)

    if intencao == "CONSULTAR_ACAO":
        total = len(dados["acoes_sustentaveis"])
        feitas = contar_historico(dados["usuario_acoes"], usuario["id"])
        return "Você registrou {} de {} ações sustentáveis.".format(feitas, total)

    if intencao == "CONSULTAR_AVATAR":
        return "Seu avatar está usando roupa '{}' e acessório '{}'.".format(
            usuario["avatar_roupa"],
            usuario["avatar_acessorio"],
        )

    if intencao == "CONSULTAR_OFENSIVA":
        return "Sua ofensiva está em {}% e seu nível atual é {}.".format(
            usuario["energia_ofensiva"],
            usuario["nivel_ofensiva"],
        )

    return mensagem_avatar(usuario)


def registrar_mensagem_conversa(dados, usuario, remetente, texto, intencao, entidades):
    try:
        if remetente not in ["USUARIO", "SOULAI"]:
            raise ValueError("Remetente inválido.")
        if len(texto.strip()) == 0:
            raise ValueError("Mensagem vazia.")

        dados["conversas"].append(
            {
                "id": gerar_proximo_id(dados["conversas"]),
                "usuario_id": usuario["id"],
                "remetente": remetente,
                "mensagem": texto,
                "intencao": intencao,
                "entidades_json": json.dumps(entidades, ensure_ascii=False),
                "data": data_atual_texto(),
            }
        )
    except ValueError as erro:
        print("Erro ao registrar mensagem:", erro)
        return False
    else:
        return True
    finally:
        pass


def menu_conversa_soulai(dados, usuario):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("CONVERSA COM SOULAI")
        print("Digite uma pergunta sobre missão, ação, loja, avatar ou ofensiva.")
        print("0 - Voltar")

        texto = input("Você: ").strip()
        if texto == "0":
            opcao = "0"
        elif texto == "":
            print("Mensagem vazia.")
        else:
            intencao, entidades = classificar_intencao(texto)
            registrar_mensagem_conversa(dados, usuario, "USUARIO", texto, intencao, entidades)
            resposta = gerar_resposta_soulai(usuario, dados, intencao)
            registrar_mensagem_conversa(dados, usuario, "SOULAI", resposta, intencao, entidades)
            print("SoulAI:", resposta)
            salvar_dados(dados)
            pausar()



def menu_missoes(dados, usuario):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("MENU DE MISSÕES")
        print("1 - Listar missões")
        print("2 - Concluir missão")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "0"])

        if opcao == "1":
            listar_missoes_disponiveis(dados, usuario)
            pausar()
        elif opcao == "2":
            fluxo_concluir_missoes(dados, usuario)
            pausar()


def menu_acoes(dados, usuario):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("MENU DE AÇÕES SUSTENTÁVEIS")
        print("1 - Listar ações sustentáveis")
        print("2 - Registrar ação concluída")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "0"])

        if opcao == "1":
            listar_acoes_disponiveis(dados, usuario)
            pausar()
        elif opcao == "2":
            fluxo_registrar_acoes(dados, usuario)
            pausar()


def fluxo_concluir_missoes(dados, usuario):
    continuar = True

    while continuar:
        if not listar_missoes_disponiveis(dados, usuario):
            return
        if len(dados["missoes"]) == 0:
            return
        print("\n0 - Voltar para o menu de missões")
        missao_id = ler_inteiro("Digite o ID da missão que deseja concluir: ", 0)

        if missao_id == 0:
            continuar = False
        else:
            if concluir_missao(dados, usuario, missao_id):
                salvar_dados(dados)

            print("\n1 - Concluir outra missão")
            print("0 - Voltar para o menu de missões")
            opcao = ler_opcao(["1", "0"], "Próximo passo: ")
            continuar = opcao == "1"


def fluxo_registrar_acoes(dados, usuario):
    continuar = True

    while continuar:
        listar_acoes_disponiveis(dados, usuario)
        print("\n0 - Voltar para o menu de ações")
        acao_id = ler_inteiro("Digite o ID da ação realizada: ", 0)

        if acao_id == 0:
            continuar = False
        else:
            if registrar_acao_sustentavel(dados, usuario, acao_id):
                salvar_dados(dados)

            print("\n1 - Registrar outra ação")
            print("0 - Voltar para o menu de ações")
            opcao = ler_opcao(["1", "0"], "Próximo passo: ")
            continuar = opcao == "1"


def fluxo_equipar_acessorios(dados, usuario):
    continuar = True

    while continuar:
        listar_inventario_usuario(dados, usuario)
        print("\n0 - Voltar para avatar, loja e inventário")
        acessorio_id = ler_inteiro("Digite o ID do item para equipar: ", 0)

        if acessorio_id == 0:
            continuar = False
        else:
            if equipar_acessorio(dados, usuario, acessorio_id):
                salvar_dados(dados)

            print("\n1 - Equipar outro item")
            print("0 - Voltar para avatar, loja e inventário")
            opcao = ler_opcao(["1", "0"], "Próximo passo: ")
            continuar = opcao == "1"


def fluxo_comprar_acessorios(dados, usuario):
    continuar = True

    while continuar:
        listar_loja(dados, usuario)
        print("\n0 - Voltar para avatar, loja e inventário")
        acessorio_id = ler_inteiro("Digite o ID do item que deseja comprar: ", 0)

        if acessorio_id == 0:
            continuar = False
        else:
            comprou = comprar_acessorio(dados, usuario, acessorio_id)
            if comprou:
                salvar_dados(dados)

                if confirmar_operacao("Deseja equipar esse item agora"):
                    if equipar_acessorio(dados, usuario, acessorio_id):
                        salvar_dados(dados)

            print("\n1 - Comprar outro item")
            print("2 - Equipar item do inventário")
            print("0 - Voltar para avatar, loja e inventário")
            opcao = ler_opcao(["1", "2", "0"], "Próximo passo: ")

            if opcao == "1":
                continuar = True
            elif opcao == "2":
                fluxo_equipar_acessorios(dados, usuario)
                continuar = False
            else:
                continuar = False


def menu_avatar_loja(dados, usuario):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("AVATAR, LOJA E INVENTÁRIO")
        print("1 - Interagir com avatar")
        print("2 - Ver loja")
        print("3 - Comprar acessório")
        print("4 - Ver inventário")
        print("5 - Equipar item")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "5", "0"])

        if opcao == "1":
            interagir_com_avatar(usuario)
            pausar()
        elif opcao == "2":
            listar_loja(dados, usuario)
            pausar()
        elif opcao == "3":
            fluxo_comprar_acessorios(dados, usuario)
            pausar()
        elif opcao == "4":
            listar_inventario_usuario(dados, usuario)
            pausar()
        elif opcao == "5":
            fluxo_equipar_acessorios(dados, usuario)
            pausar()



def criar_missao(dados):
    mostrar_titulo("CADASTRAR MISSÃO")
    titulo = ler_texto("Título: ", 3, 150)
    descricao = ler_texto("Descrição: ", 5, 1000)
    valor = ler_inteiro("Moedas da missão: ", 0, 1000)
    energia = ler_inteiro("Energia local da ofensiva (0 a 100): ", 0, 100)
    administrador_id = ler_inteiro("ID do administrador responsável no Oracle: ", 1, 99999)
    administradores = consultar_oracle(
        "SELECT ID_ADMINISTRADOR FROM ADMINISTRADOR WHERE ID_ADMINISTRADOR = :1",
        [administrador_id],
    )
    if administradores is None:
        return False
    if len(administradores) == 0:
        mostrar_feedback("erro", "Administrador não encontrado. Use um administrador já cadastrado no sistema web.")
        return False

    # o próprio banco gera o id da missão
    id_missao = escrever_oracle(
        """INSERT INTO MISSAO
           (TITULO_MISSAO, DESCRICAO_MISSAO, ATIVO, VALOR_MOEDAS_MISSAO,
            ADMINISTRADOR_ID_ADMINISTRADOR)
           VALUES (:1, :2, :3, :4, :5) RETURNING ID_MISSAO INTO :6""",
        [titulo, descricao, SIM, valor, administrador_id], True,
    )
    if id_missao is False:
        return False
    guardar_energia_missao(dados, id_missao, energia)
    atualizar_missoes_oracle(dados)
    mostrar_feedback("sucesso", "Missão cadastrada no Oracle com ID " + str(id_missao) + ".")
    return True


def alterar_missao(dados):
    if not listar_missoes_oracle(dados):
        return False
    id_missao = ler_inteiro("ID da missão para alterar: ", 1)
    missao = buscar_por_id(dados["missoes"], id_missao)

    if missao is None:
        print("Missão não encontrada.")
        return False

    novos_dados = missao.copy()
    titulo = ler_texto("Novo título (Enter mantém): ", 3, 150, True)
    descricao = ler_texto("Nova descrição (Enter mantém): ", 5, 1000, True)
    ativo = input("Ativo? S/N (Enter mantém): ").strip().upper()
    while ativo not in [SIM, NAO, ""]:
        mostrar_feedback("erro", "Digite S, N ou pressione Enter para manter.")
        ativo = input("Ativo? S/N (Enter mantém): ").strip().upper()

    if titulo != "":
        novos_dados["titulo"] = titulo
    if descricao != "":
        novos_dados["descricao"] = descricao
    if ativo in [SIM, NAO]:
        novos_dados["ativo"] = ativo
    if confirmar_operacao("Deseja alterar moedas e energia"):
        novos_dados["valor_moedas"] = ler_inteiro("Novo valor de moedas: ", 0, 1000)
        novos_dados["energia"] = ler_inteiro("Nova energia local (0 a 100): ", 0, 100)

    if novos_dados == missao:
        mostrar_feedback("aviso", "Nenhum campo foi alterado.")
        return False
    alterou = escrever_oracle(
        """UPDATE MISSAO SET TITULO_MISSAO = :1, DESCRICAO_MISSAO = :2,
           ATIVO = :3, VALOR_MOEDAS_MISSAO = :4 WHERE ID_MISSAO = :5""",
        [novos_dados["titulo"], novos_dados["descricao"], novos_dados["ativo"],
         novos_dados["valor_moedas"], id_missao],
    )
    if alterou:
        guardar_energia_missao(dados, id_missao, novos_dados["energia"])
        atualizar_missoes_oracle(dados)
        mostrar_feedback("sucesso", "Missão alterada no Oracle.")
    return alterou


def excluir_missao(dados):
    if not listar_missoes_oracle(dados):
        return False
    id_missao = ler_inteiro("ID da missão para excluir: ", 1)
    if buscar_por_id(dados["missoes"], id_missao) is None:
        mostrar_feedback("erro", "Missão não encontrada.")
        return False

    for historico in dados["usuario_missoes"]:
        if historico.get("origem") == "oracle" and historico.get("missao_id") == id_missao:
            print("Não é possível excluir: existe histórico de usuário para esta missão.")
            return False

    if confirmar_operacao("Confirma a exclusão da missão"):
        excluiu = escrever_oracle("DELETE FROM MISSAO WHERE ID_MISSAO = :1", [id_missao])
        if excluiu:
            dados["energia_missoes"] = [item for item in dados["energia_missoes"] if item["id"] != id_missao]
            atualizar_missoes_oracle(dados)
            mostrar_feedback("sucesso", "Missão excluída do Oracle.")
        return excluiu

    print("Exclusão cancelada.")
    return False


def criar_acao(dados):
    mostrar_titulo("CADASTRAR AÇÃO SUSTENTÁVEL")
    titulo = ler_texto("Título: ", 3, 80)
    categoria = ler_texto("Categoria: ", 3, 50)
    valor = ler_inteiro("Moedas da ação: ", 0, 1000)
    energia = ler_inteiro("Energia da ofensiva (0 a 100): ", 0, 100)

    registro = {
        "id": gerar_proximo_id(dados["acoes_sustentaveis"]),
        "titulo": titulo,
        "categoria": categoria,
        "valor_moedas": valor,
        "energia": energia,
        "ativo": SIM,
    }

    return criar_registro(dados["acoes_sustentaveis"], registro, "Ação sustentável")


def alterar_acao(dados):
    listar_registros(
        "AÇÕES CADASTRADAS",
        dados["acoes_sustentaveis"],
        [("titulo", "Título"), ("categoria", "Categoria"), ("valor_moedas", "Moedas"), ("ativo", "Ativo")],
    )
    id_acao = ler_inteiro("ID da ação para alterar: ", 1)
    acao = buscar_por_id(dados["acoes_sustentaveis"], id_acao)

    if acao is None:
        print("Ação não encontrada.")
        return False

    novos_dados = {}
    titulo = ler_texto("Novo título (Enter mantém): ", 0, 80, True)
    categoria = ler_texto("Nova categoria (Enter mantém): ", 0, 50, True)
    ativo = input("Ativo? S/N (Enter mantém): ").strip().upper()

    if titulo != "":
        novos_dados["titulo"] = titulo
    if categoria != "":
        novos_dados["categoria"] = categoria
    if ativo in [SIM, NAO]:
        novos_dados["ativo"] = ativo
    elif ativo != "":
        print("Valor de ativo ignorado, pois deve ser S ou N.")

    if confirmar_operacao("Deseja alterar moedas e energia"):
        novos_dados["valor_moedas"] = ler_inteiro("Novo valor de moedas: ", 0, 1000)
        novos_dados["energia"] = ler_inteiro("Nova energia (0 a 100): ", 0, 100)

    return alterar_registro(dados["acoes_sustentaveis"], id_acao, novos_dados, "Ação sustentável")


def excluir_acao(dados):
    listar_registros(
        "AÇÕES CADASTRADAS",
        dados["acoes_sustentaveis"],
        [("titulo", "Título"), ("categoria", "Categoria"), ("valor_moedas", "Moedas"), ("ativo", "Ativo")],
    )
    id_acao = ler_inteiro("ID da ação para excluir: ", 1)

    for historico in dados["usuario_acoes"]:
        if historico.get("acao_id") == id_acao:
            print("Não é possível excluir: existe histórico de usuário para esta ação.")
            return False

    if confirmar_operacao("Confirma a exclusão da ação"):
        return excluir_registro(dados["acoes_sustentaveis"], id_acao, "Ação sustentável")

    print("Exclusão cancelada.")
    return False


def criar_acessorio(dados):
    mostrar_titulo("CADASTRAR ACESSÓRIO")
    nome = ler_texto("Nome: ", 3, 80)

    print("Tipos aceitos: roupa, acessório")
    tipo = normalizar_tipo_acessorio(ler_texto("Tipo: ", 3, 20))
    while tipo not in TIPOS_ACESSORIO:
        print("Tipo inválido.")
        tipo = normalizar_tipo_acessorio(ler_texto("Tipo: ", 3, 20))

    print("Raridades aceitas: comum, raro, épico, lendário")
    raridade = normalizar_raridade(ler_texto("Raridade: ", 3, 20))
    while raridade not in RARIDADES:
        print("Raridade inválida.")
        raridade = normalizar_raridade(ler_texto("Raridade: ", 3, 20))

    preco = ler_inteiro("Preço em moedas: ", 0, 10000)

    registro = {
        "id": gerar_proximo_id(dados["acessorios"]),
        "nome": nome,
        "tipo": tipo,
        "raridade": raridade,
        "preco": preco,
    }

    return criar_registro(dados["acessorios"], registro, "Acessório")


def alterar_acessorio(dados):
    listar_registros(
        "ACESSÓRIOS CADASTRADOS",
        dados["acessorios"],
        [("nome", "Nome"), ("tipo", "Tipo"), ("raridade", "Raridade"), ("preco", "Preço")],
    )
    id_acessorio = ler_inteiro("ID do acessório para alterar: ", 1)
    acessorio = buscar_por_id(dados["acessorios"], id_acessorio)

    if acessorio is None:
        print("Acessório não encontrado.")
        return False

    novos_dados = {}
    nome = ler_texto("Novo nome (Enter mantém): ", 0, 80, True)
    tipo = normalizar_tipo_acessorio(input("Novo tipo roupa/acessório (Enter mantém): "))
    raridade = normalizar_raridade(input("Nova raridade comum/raro/épico/lendário (Enter mantém): "))

    if nome != "":
        novos_dados["nome"] = nome
    if tipo in TIPOS_ACESSORIO:
        novos_dados["tipo"] = tipo
    elif tipo != "":
        print("Tipo ignorado, pois é inválido.")
    if raridade in RARIDADES:
        novos_dados["raridade"] = raridade
    elif raridade != "":
        print("Raridade ignorada, pois é inválida.")

    if confirmar_operacao("Deseja alterar o preço"):
        novos_dados["preco"] = ler_inteiro("Novo preço: ", 0, 10000)

    return alterar_registro(dados["acessorios"], id_acessorio, novos_dados, "Acessório")


def excluir_acessorio(dados):
    listar_registros(
        "ACESSÓRIOS CADASTRADOS",
        dados["acessorios"],
        [("nome", "Nome"), ("tipo", "Tipo"), ("raridade", "Raridade"), ("preco", "Preço")],
    )
    id_acessorio = ler_inteiro("ID do acessório para excluir: ", 1)

    for item in dados["inventario"]:
        if item.get("acessorio_id") == id_acessorio:
            print("Não é possível excluir: existe usuário com este item no inventário.")
            return False

    if confirmar_operacao("Confirma a exclusão do acessório"):
        return excluir_registro(dados["acessorios"], id_acessorio, "Acessório")

    print("Exclusão cancelada.")
    return False


def alterar_usuario(dados):
    listar_registros(
        "USUÁRIOS CADASTRADOS",
        dados["usuarios"],
        [("nome", "Nome"), ("email", "E-mail"), ("saldo_moedas", "Moedas"), ("nivel_ofensiva", "Nível")],
    )
    id_usuario = ler_inteiro("ID do usuário para alterar: ", 1)
    usuario = buscar_por_id(dados["usuarios"], id_usuario)

    if usuario is None:
        print("Usuário não encontrado.")
        return False

    novos_dados = {}
    nome = ler_texto("Novo nome (Enter mantém): ", 0, 80, True)
    trocar_email = confirmar_operacao("Deseja alterar o e-mail")
    trocar_senha = confirmar_operacao("Deseja alterar a senha")

    if nome != "":
        novos_dados["nome"] = nome
    if trocar_email:
        novos_dados["email"] = ler_email(dados["usuarios"], usuario["email"])
    if trocar_senha:
        novos_dados["senha_hash"] = criar_hash_senha(ler_senha())

    return alterar_registro(dados["usuarios"], id_usuario, novos_dados, "Usuário")


def excluir_usuario(dados, usuario_logado):
    listar_registros(
        "USUÁRIOS CADASTRADOS",
        dados["usuarios"],
        [("nome", "Nome"), ("email", "E-mail"), ("saldo_moedas", "Moedas"), ("nivel_ofensiva", "Nível")],
    )
    id_usuario = ler_inteiro("ID do usuário para excluir: ", 1)
    excluiu = False

    try:
        usuario = buscar_por_id(dados["usuarios"], id_usuario)
        if usuario is None:
            raise LookupError("Usuário não encontrado.")
        if not confirmar_operacao("Confirma a exclusão do usuário e seus históricos"):
            raise ValueError("Exclusão cancelada pelo usuário.")

        dados["usuarios"].remove(usuario)
        dados["usuario_missoes"] = [
            item for item in dados["usuario_missoes"] if item.get("usuario_id") != id_usuario
        ]
        dados["usuario_acoes"] = [
            item for item in dados["usuario_acoes"] if item.get("usuario_id") != id_usuario
        ]
        dados["inventario"] = [
            item for item in dados["inventario"] if item.get("usuario_id") != id_usuario
        ]
        dados["conversas"] = [
            item for item in dados["conversas"] if item.get("usuario_id") != id_usuario
        ]
    except LookupError as erro:
        print("Erro ao excluir usuário:", erro)
    except ValueError as erro:
        print("Erro ao excluir usuário:", erro)
    else:
        excluiu = True
        print("Usuário excluído com sucesso.")
        if usuario_logado is not None and usuario_logado.get("id") == id_usuario:
            print("Atenção: o usuário logado foi excluído. Será necessário sair.")
    finally:
        print("Operação de exclusão de usuário finalizada.")

    return excluiu


def menu_crud_usuarios(dados, usuario_logado):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("CRUD - USUÁRIOS")
        print("1 - Listar usuários")
        print("2 - Cadastrar usuário")
        print("3 - Alterar usuário")
        print("4 - Excluir usuário")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "0"])

        if opcao == "1":
            listar_registros(
                "USUÁRIOS CADASTRADOS",
                dados["usuarios"],
                [("nome", "Nome"), ("email", "E-mail"), ("saldo_moedas", "Moedas"), ("nivel_ofensiva", "Nível")],
            )
            pausar()
        elif opcao == "2":
            if cadastrar_usuario(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "3":
            if alterar_usuario(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "4":
            if excluir_usuario(dados, usuario_logado):
                salvar_dados(dados)
            pausar()


def menu_crud_missoes(dados):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("CRUD - MISSÕES (ORACLE)")
        print("1 - Listar missões")
        print("2 - Cadastrar missão")
        print("3 - Alterar missão")
        print("4 - Excluir missão")
        print("5 - Exportar consulta para JSON")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "5", "0"])

        if opcao == "1":
            listar_missoes_oracle(dados)
            pausar()
        elif opcao == "2":
            if criar_missao(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "3":
            if alterar_missao(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "4":
            if excluir_missao(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "5":
            exportar_missoes_json(dados)
            pausar()


def menu_crud_acoes(dados):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("CRUD - AÇÕES SUSTENTÁVEIS")
        print("1 - Listar ações")
        print("2 - Cadastrar ação")
        print("3 - Alterar ação")
        print("4 - Excluir ação")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "0"])

        if opcao == "1":
            listar_registros(
                "AÇÕES CADASTRADAS",
                dados["acoes_sustentaveis"],
                [("titulo", "Título"), ("categoria", "Categoria"), ("valor_moedas", "Moedas"), ("energia", "Energia"), ("ativo", "Ativo")],
            )
            pausar()
        elif opcao == "2":
            if criar_acao(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "3":
            if alterar_acao(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "4":
            if excluir_acao(dados):
                salvar_dados(dados)
            pausar()


def menu_crud_acessorios(dados):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("CRUD - ACESSÓRIOS")
        print("1 - Listar acessórios")
        print("2 - Cadastrar acessório")
        print("3 - Alterar acessório")
        print("4 - Excluir acessório")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "0"])

        if opcao == "1":
            listar_registros(
                "ACESSÓRIOS CADASTRADOS",
                dados["acessorios"],
                [("nome", "Nome"), ("tipo", "Tipo"), ("raridade", "Raridade"), ("preco", "Preço")],
            )
            pausar()
        elif opcao == "2":
            if criar_acessorio(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "3":
            if alterar_acessorio(dados):
                salvar_dados(dados)
            pausar()
        elif opcao == "4":
            if excluir_acessorio(dados):
                salvar_dados(dados)
            pausar()


def menu_crud(dados, usuario_logado):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("MENU CRUD")
        print("1 - CRUD de usuários")
        print("2 - CRUD de missões")
        print("3 - CRUD de ações sustentáveis")
        print("4 - CRUD de acessórios")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "0"])

        if opcao == "1":
            menu_crud_usuarios(dados, usuario_logado)
        elif opcao == "2":
            menu_crud_missoes(dados)
        elif opcao == "3":
            menu_crud_acoes(dados)
        elif opcao == "4":
            menu_crud_acessorios(dados)



def relatorio_ranking_usuarios(dados):
    mostrar_titulo("RANKING DE USUÁRIOS POR MOEDAS")
    usuarios_ordenados = sorted(
        dados["usuarios"],
        key=lambda usuario: usuario["saldo_moedas"],
        reverse=True,
    )

    if len(usuarios_ordenados) == 0:
        print("Nenhum usuário cadastrado.")
        return

    posicao = 1
    for usuario in usuarios_ordenados:
        print(
            str(posicao) + ".",
            usuario["nome"],
            "-",
            usuario["saldo_moedas"],
            "moedas",
            "- nível",
            usuario["nivel_ofensiva"],
        )
        posicao += 1


def relatorio_historico_usuario(dados, usuario):
    mostrar_titulo("HISTÓRICO DO USUÁRIO")
    print("Usuário:", usuario["nome"])

    print("\nMissões concluídas:")
    encontrou = False
    for historico in dados["usuario_missoes"]:
        if historico.get("usuario_id") == usuario["id"]:
            encontrou = True
            titulo = historico.get("titulo", "Missão " + str(historico["missao_id"]))
            print("-", titulo, "|", historico["data"], "|", historico["moedas_ganhas"], "moedas")
    if not encontrou:
        print("Nenhuma missão concluída.")

    print("\nAções sustentáveis:")
    encontrou = False
    for historico in dados["usuario_acoes"]:
        if historico.get("usuario_id") == usuario["id"]:
            acao = buscar_por_id(dados["acoes_sustentaveis"], historico["acao_id"])
            encontrou = True
            if acao is not None:
                print("-", acao["titulo"], "|", historico["data"], "|", historico["moedas_ganhas"], "moedas")
    if not encontrou:
        print("Nenhuma ação sustentável registrada.")


def menu_relatorios(dados, usuario):
    opcao = ""

    while opcao != "0":
        mostrar_titulo("RELATÓRIOS E FILTROS")
        print("1 - Filtrar usuários por nome")
        print("2 - Listar missões ativas")
        print("3 - Filtrar acessórios por tipo")
        print("4 - Ranking de usuários por moedas")
        print("5 - Histórico do usuário logado")
        print("6 - Exportar missões do Oracle para JSON")
        print("0 - Voltar")

        opcao = ler_opcao(["1", "2", "3", "4", "5", "6", "0"])

        if opcao == "1":
            termo = ler_texto("Digite parte do nome: ", 1, 80)
            resultado = filtrar_por_campo(dados["usuarios"], "nome", termo)
            listar_registros(
                "RESULTADO DO FILTRO",
                resultado,
                [("nome", "Nome"), ("email", "E-mail"), ("saldo_moedas", "Moedas")],
            )
            pausar()
        elif opcao == "2":
            if not atualizar_missoes_oracle(dados):
                pausar()
                continue
            resultado = [missao for missao in dados["missoes"] if missao.get("ativo") == SIM]
            listar_registros(
                "MISSÕES ATIVAS",
                resultado,
                [("titulo", "Título"), ("valor_moedas", "Moedas"), ("energia", "Energia")],
            )
            pausar()
        elif opcao == "3":
            print("Tipos aceitos: roupa, acessório")
            tipo = normalizar_tipo_acessorio(ler_texto("Tipo desejado: ", 3, 20))
            resultado = [item for item in dados["acessorios"] if item.get("tipo") == tipo]
            listar_registros(
                "ACESSÓRIOS FILTRADOS",
                resultado,
                [("nome", "Nome"), ("tipo", "Tipo"), ("raridade", "Raridade"), ("preco", "Preço")],
            )
            pausar()
        elif opcao == "4":
            relatorio_ranking_usuarios(dados)
            pausar()
        elif opcao == "5":
            relatorio_historico_usuario(dados, usuario)
            pausar()
        elif opcao == "6":
            exportar_missoes_json(dados)
            pausar()



def ler_decimal(mensagem, minimo, maximo):
    while True:
        try:
            valor = float(input(mensagem).strip().replace(",", "."))
            if not math.isfinite(valor) or valor < minimo or valor > maximo:
                raise ValueError
        except ValueError:
            mostrar_feedback("erro", "Digite um número entre " + str(minimo) + " e " + str(maximo) + ".")
        else:
            return valor


def classificar_qualidade_ar(indice):
    if indice is None:
        return "Indisponível"
    if indice <= 20:
        return "Boa"
    if indice <= 40:
        return "Razoável"
    if indice <= 60:
        return "Moderada"
    if indice <= 80:
        return "Ruim"
    if indice <= 100:
        return "Muito ruim"
    return "Extremamente ruim"


def consultar_qualidade_ar(latitude, longitude):
    # consulta a api pública de qualidade do ar
    resposta = None
    atual = None
    try:
        if (not math.isfinite(latitude) or not math.isfinite(longitude)
                or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
            raise ValueError("Coordenadas inválidas.")
        parametros = urllib.parse.urlencode({
            "latitude": latitude, "longitude": longitude,
            "current": "european_aqi,us_aqi,pm2_5,pm10", "timezone": "auto",
        })
        resposta = urllib.request.urlopen(URL_QUALIDADE_AR + "?" + parametros, timeout=15)
        conteudo = json.load(resposta)
        if not isinstance(conteudo, dict) or not isinstance(conteudo.get("current"), dict):
            raise ValueError("A API não retornou os dados atuais.")
        atual = conteudo["current"]
        for campo in ["european_aqi", "us_aqi", "pm2_5", "pm10"]:
            if campo not in atual:
                raise ValueError("A API retornou dados incompletos.")
            valor = atual[campo]
            if valor is not None and (type(valor) not in [int, float]
                                      or not math.isfinite(valor) or valor < 0):
                raise ValueError("A API retornou um valor inválido.")
        if not isinstance(atual.get("time"), str):
            raise ValueError("A API não informou o horário dos dados.")
        atual = atual.copy()
        atual["fuso"] = conteudo.get("timezone", "UTC")
    except urllib.error.HTTPError as erro:
        resposta = erro
        mostrar_feedback("erro", "O serviço de qualidade do ar está indisponível. Tente novamente mais tarde.")
        atual = None
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        mostrar_feedback("erro", "Não foi possível acessar a API. Confira sua conexão com a internet.")
        atual = None
    except (ValueError, TypeError, UnicodeError) as erro:
        mostrar_feedback("erro", "Não foi possível ler a qualidade do ar: " + str(erro))
        atual = None
    finally:
        if resposta is not None:
            try:
                resposta.close()
            except OSError:
                mostrar_feedback("aviso", "Não foi possível encerrar a resposta da API.")
    return atual


def mostrar_qualidade_ar(local, atual):
    mostrar_titulo("QUALIDADE DO AR - " + local)
    print("Horário dos dados:", atual["time"].replace("T", " "), "|", atual["fuso"])
    indice = atual["european_aqi"]
    print("Índice europeu:", indice if indice is not None else "Indisponível", "-", classificar_qualidade_ar(indice))
    print("Índice dos Estados Unidos:", atual["us_aqi"] if atual["us_aqi"] is not None else "Indisponível")
    for campo, rotulo in [("pm2_5", "Partículas PM2,5"), ("pm10", "Partículas PM10")]:
        valor = atual[campo]
        print(rotulo + ":", str(valor) + " µg/m³" if valor is not None else "Indisponível")
    print("\nFonte: Open-Meteo e Copernicus CAMS (dados estimados por modelo).")
    print("Usar transporte coletivo e evitar queimadas ajuda a reduzir a poluição do ar.")


def menu_qualidade_ar():
    cidades = {
        "1": ("São Paulo", -23.55, -46.63),
        "2": ("Rio de Janeiro", -22.91, -43.17),
        "3": ("Curitiba", -25.43, -49.27),
    }
    opcao = ""
    while opcao != "0":
        mostrar_titulo("QUALIDADE DO AR DA MINHA CIDADE")
        for chave, cidade in cidades.items():
            print(chave + " - " + cidade[0])
        print("4 - Informar latitude e longitude")
        print("0 - Voltar")
        opcao = ler_opcao(["1", "2", "3", "4", "0"])
        if opcao == "0":
            continue
        if opcao == "4":
            local = "Local informado"
            latitude = ler_decimal("Latitude (-90 a 90): ", -90, 90)
            longitude = ler_decimal("Longitude (-180 a 180): ", -180, 180)
        else:
            local, latitude, longitude = cidades[opcao]
        print("\nConsultando qualidade do ar...")
        atual = consultar_qualidade_ar(latitude, longitude)
        if atual is not None:
            mostrar_qualidade_ar(local, atual)
        pausar()


def mostrar_menu_principal(usuario):
    mostrar_titulo("SOULAI - MENU PRINCIPAL")
    print("Usuário logado:", usuario["nome"])
    print("1 - Ver status do usuário")
    print("2 - Missões")
    print("3 - Ações sustentáveis")
    print("4 - Avatar, loja e inventário")
    print("5 - Conversar com o SoulAI")
    print("6 - CRUD / administração dos dados")
    print("7 - Relatórios e filtros")
    print("8 - Salvar dados")
    print("9 - Qualidade do ar da minha cidade")
    print("0 - Sair")



def main():
    dados = carregar_dados()
    usuario_logado = menu_acesso(dados)

    if usuario_logado is None:
        print("Sistema encerrado.")
        return

    opcao = ""

    while opcao != "0":
        usuario_logado = obter_usuario_atualizado(dados, usuario_logado)
        if usuario_logado is None:
            print("Usuário logado não existe mais. Encerrando sessão.")
            break

        mostrar_menu_principal(usuario_logado)
        opcao = ler_opcao(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"])

        if opcao == "1":
            mostrar_status_usuario(usuario_logado, dados)
            pausar()
        elif opcao == "2":
            menu_missoes(dados, usuario_logado)
        elif opcao == "3":
            menu_acoes(dados, usuario_logado)
        elif opcao == "4":
            menu_avatar_loja(dados, usuario_logado)
        elif opcao == "5":
            menu_conversa_soulai(dados, usuario_logado)
        elif opcao == "6":
            menu_crud(dados, usuario_logado)
        elif opcao == "7":
            menu_relatorios(dados, usuario_logado)
        elif opcao == "8":
            if salvar_dados(dados):
                mostrar_feedback("sucesso", "Dados salvos em " + ARQUIVO_DADOS + ".")
            pausar()
        elif opcao == "9":
            menu_qualidade_ar()
        elif opcao == "0":
            salvar_dados(dados)
            mostrar_titulo("RESUMO FINAL")
            print("Até logo,", usuario_logado["nome"] + "!")
            print("Moedas finais:", usuario_logado["saldo_moedas"])
            print("Nível de ofensiva:", usuario_logado["nivel_ofensiva"])
            print("Energia restante:", str(usuario_logado["energia_ofensiva"]) + "%")
            print("Continue realizando ações sustentáveis na SoulUp.")


if __name__ == "__main__":
    main()