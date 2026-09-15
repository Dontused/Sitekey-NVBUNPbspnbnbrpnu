from flask import Flask, request, jsonify, send_file
import requests
import time
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

ARQUIVO = "config_te.txt"

# Pasta onde o Render guarda as cópias recebidas
PASTA_ARQUIVOS = Path("arquivos")
PASTA_ARQUIVOS.mkdir(parents=True, exist_ok=True)

# ==========================================================
# MODO
# ==========================================================

# Render:
# MODE=servidor
#
# PC que possui config_te.txt:
# MODE=secundario

MODO = os.environ.get("MODE", "servidor").lower()

# ==========================================================
# SERVIDOR
# ==========================================================

SERVER_URL = os.environ.get(
    "SERVER_URL",
    ""
).rstrip("/")

# 6 horas em segundos
SEIS_HORAS = 6 * 60 * 60

# Intervalo de verificação
INTERVALO = 2

# Pedido manual de atualização
atualizacao_solicitada = False

# ==========================================================
# CONTROLE CORS
# ==========================================================

@app.after_request
def adicionar_cors(resposta):

    resposta.headers["Access-Control-Allow-Origin"] = "*"

    resposta.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, DELETE, OPTIONS"
    )

    resposta.headers["Access-Control-Allow-Headers"] = (
        "Content-Type"
    )

    return resposta


# ==========================================================
# ROTA PRINCIPAL
# ==========================================================

@app.route("/")
def index():

    return jsonify({
        "servidor": "Sitekey",
        "status": "online",
        "modo": MODO
    })


# ==========================================================
# LISTAR ARQUIVOS
# ==========================================================

@app.route("/arquivos")
def listar_arquivos():

    arquivos = []

    if not PASTA_ARQUIVOS.exists():

        return jsonify({
            "sucesso": True,
            "arquivos": []
        })

    for arquivo in PASTA_ARQUIVOS.iterdir():

        if not arquivo.is_file():
            continue

        try:

            dados = arquivo.stat()

            data = datetime.fromtimestamp(
                dados.st_mtime
            )

            arquivos.append({

                "id": arquivo.name,

                "nome": ARQUIVO,

                "data": data.strftime(
                    "%d/%m/%Y"
                ),

                "hora": data.strftime(
                    "%H:%M:%S"
                ),

                "timestamp": dados.st_mtime

            })

        except Exception:

            continue

    arquivos.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({

        "sucesso": True,

        "arquivos": arquivos

    })


# ==========================================================
# PEDIR ATUALIZAÇÃO MANUAL
# ==========================================================

@app.route(
    "/atualizar",
    methods=["POST"]
)
def atualizar():

    global atualizacao_solicitada

    atualizacao_solicitada = True

    print(
        "Pedido de atualização recebido."
    )

    return jsonify({

        "sucesso": True,

        "mensagem":
            "Pedido enviado ao computador."

    })


# ==========================================================
# COMPUTADOR VERIFICA SE EXISTE PEDIDO
# ==========================================================

@app.route("/verificar")
def verificar():

    return jsonify({

        "atualizar":
            atualizacao_solicitada

    })


# ==========================================================
# STATUS
# ==========================================================

@app.route("/status")
def status():

    quantidade = 0

    if PASTA_ARQUIVOS.exists():

        quantidade = len([

            x for x in
            PASTA_ARQUIVOS.iterdir()

            if x.is_file()

        ])

    return jsonify({

        "online": True,

        "arquivos": quantidade

    })


# ==========================================================
# RECEBER ARQUIVO
# ==========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    global atualizacao_solicitada

    if "arquivo" not in request.files:

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo não enviado."

        }), 400

    arquivo = request.files["arquivo"]

    if not arquivo.filename:

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo inválido."

        }), 400

    # ======================================================
    # CRIA NOME ÚNICO
    # ======================================================

    agora = datetime.now()

    nome = (
        "config_te_"
        + agora.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".txt"
    )

    caminho = (
        PASTA_ARQUIVOS /
        nome
    )

    contador = 1

    while caminho.exists():

        nome = (
            "config_te_"
            + agora.strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
            + f"_{contador}.txt"
        )

        caminho = (
            PASTA_ARQUIVOS /
            nome
        )

        contador += 1

    # ======================================================
    # SALVA
    # ======================================================

    arquivo.save(caminho)

    # Pedido foi atendido
    atualizacao_solicitada = False

    print(
        f"Arquivo recebido: {nome}"
    )

    return jsonify({

        "sucesso": True,

        "arquivo": nome,

        "data":
            agora.strftime(
                "%d/%m/%Y"
            ),

        "hora":
            agora.strftime(
                "%H:%M:%S"
            )

    })


# ==========================================================
# DOWNLOAD
# ==========================================================

@app.route(
    "/baixar/<nome>"
)
def baixar(nome):

    # Impede caminhos externos
    nome = os.path.basename(nome)

    caminho = (
        PASTA_ARQUIVOS /
        nome
    )

    if not caminho.exists():

        return jsonify({

            "erro":
                "Arquivo não encontrado."

        }), 404

    return send_file(

        caminho,

        as_attachment=True,

        download_name=ARQUIVO

    )


# ==========================================================
# COMPUTADOR SECUNDÁRIO
# ==========================================================

def verificar_servidor():

    if not SERVER_URL:

        print()
        print(
            "ERRO: SERVER_URL não configurado."
        )
        print()

        return

    print()
    print("==============================")
    print("    SITEKEY - COMPUTADOR")
    print("==============================")
    print()

    print(
        "Servidor:",
        SERVER_URL
    )

    print(
        "Arquivo:",
        ARQUIVO
    )

    print(
        "Envio automático:",
        "6 horas após criação/alteração"
    )

    print()

    caminho_arquivo = Path(ARQUIVO)

    # ======================================================
    # CONTROLE LOCAL DO ÚLTIMO ENVIO
    # ======================================================

    arquivo_controle = Path(
        ".sitekey_ultimo_envio"
    )

    ultimo_envio = None

    if arquivo_controle.exists():

        try:

            texto = arquivo_controle.read_text().strip()

            if texto:

                ultimo_envio = float(texto)

        except Exception:

            ultimo_envio = None

    print(
        "Aguardando pedidos..."
    )

    print()

    # ======================================================
    # LOOP PRINCIPAL
    # ======================================================

    while True:

        try:

            # ------------------------------------------------
            # VERIFICA SE O ARQUIVO EXISTE
            # ------------------------------------------------

            if not caminho_arquivo.exists():

                time.sleep(INTERVALO)

                continue

            # ------------------------------------------------
            # INFORMAÇÕES DO ARQUIVO
            # ------------------------------------------------

            dados_arquivo = caminho_arquivo.stat()

            momento_criacao_ou_alteracao = (
                dados_arquivo.st_mtime
            )

            tamanho = dados_arquivo.st_size

            # Criamos uma identificação da versão
            # usando data de alteração + tamanho.

            versao_atual = (
                momento_criacao_ou_alteracao,
                tamanho
            )

            # ------------------------------------------------
            # VERIFICA PEDIDO DO SITE
            # ------------------------------------------------

            resposta = requests.get(

                SERVER_URL + "/verificar",

                timeout=10

            )

            if resposta.status_code == 200:

                dados = resposta.json()

                if dados.get("atualizar"):

                    print()
                    print(
                        "Pedido de atualização recebido."
                    )

                    print(
                        "Enviando última versão..."
                    )

                    sucesso = enviar_arquivo(
                        caminho_arquivo
                    )

                    if sucesso:

                        # Guarda que essa versão
                        # já foi enviada.

                        ultimo_envio = (
                            momento_criacao_ou_alteracao
                        )

                        arquivo_controle.write_text(
                            str(ultimo_envio)
                        )

                        print(
                            "Arquivo enviado automaticamente!"
                        )

            # ------------------------------------------------
            # ENVIO AUTOMÁTICO APÓS 6 HORAS
            # ------------------------------------------------

            agora = time.time()

            idade = (
                agora -
                momento_criacao_ou_alteracao
            )

            seis_horas_passaram = (
                idade >= SEIS_HORAS
            )

            # Verifica se essa versão já foi enviada.
            versao_ja_enviada = (

                ultimo_envio is not None

                and
                ultimo_envio ==
                momento_criacao_ou_alteracao

            )

            if (
                seis_horas_passaram
                and
                not versao_ja_enviada
            ):

                print()
                print(
                    "6 horas se passaram."
                )

                print(
                    "Enviando config_te.txt automaticamente..."
                )

                sucesso = enviar_arquivo(
                    caminho_arquivo
                )

                if sucesso:

                    ultimo_envio = (
                        momento_criacao_ou_alteracao
                    )

                    arquivo_controle.write_text(
                        str(ultimo_envio)
                    )

                    print(
                        "Envio automático concluído!"
                    )

            # ------------------------------------------------
            # PEQUENA PAUSA
            # ------------------------------------------------

            time.sleep(INTERVALO)

        except requests.exceptions.RequestException:

            print(
                "Servidor indisponível..."
            )

            time.sleep(INTERVALO)

        except Exception as erro:

            print(
                "Erro:",
                erro
            )

            time.sleep(INTERVALO)


# ==========================================================
# ENVIAR ARQUIVO PARA O RENDER
# ==========================================================

def enviar_arquivo(caminho_arquivo):

    try:

        with open(
            caminho_arquivo,
            "rb"
        ) as arquivo:

            resposta = requests.post(

                SERVER_URL + "/upload",

                files={

                    "arquivo": (

                        ARQUIVO,

                        arquivo,

                        "text/plain"

                    )

                },

                timeout=30

            )

        if resposta.status_code == 200:

            return True

        print(
            "Erro no upload:"
        )

        print(
            resposta.text
        )

        return False

    except Exception as erro:

        print(
            "Erro ao enviar:",
            erro
        )

        return False


# ==========================================================
# INICIAR
# ==========================================================

if __name__ == "__main__":

    # ======================================================
    # COMPUTADOR SECUNDÁRIO
    # ======================================================

    if MODO == "secundario":

        verificar_servidor()

    # ======================================================
    # RENDER
    # ======================================================

    else:

        print()
        print("==============================")
        print("          SITEKEY")
        print("==============================")
        print()

        print(
            "Servidor iniciado."
        )

        print()

        porta = int(
            os.environ.get(
                "PORT",
                "5000"
            )
        )

        app.run(

            host="0.0.0.0",

            port=porta,

            debug=False

        )
