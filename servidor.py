from flask import Flask, request, jsonify, send_file
import requests
import threading
import time
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import quote


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

app = Flask(__name__)

ARQUIVO = "config_te.txt"

# Pasta para os arquivos recebidos
PASTA_ARQUIVOS = Path("arquivos")

PASTA_ARQUIVOS.mkdir(
    parents=True,
    exist_ok=True
)

# ==========================================================
# MODO DE EXECUÇÃO
# ==========================================================
#
# No Render:
#
#   MODE=servidor
#
# No computador secundário:
#
#   MODE=secundario
#
# ==========================================================

MODO = os.environ.get(
    "MODE",
    "servidor"
).lower()


# ==========================================================
# ENDEREÇO DO SERVIDOR
# ==========================================================
#
# No computador secundário você deverá configurar:
#
# SERVER_URL=https://seu-app.onrender.com
#
# ==========================================================

SERVER_URL = os.environ.get(
    "SERVER_URL",
    ""
).rstrip("/")


# Intervalo entre verificações do computador secundário
INTERVALO = 2


# Pedido de atualização
atualizacao_solicitada = False


# Momento da última atualização
ultima_atualizacao = None


# ==========================================================
# CORS
# ==========================================================

@app.after_request
def adicionar_cors(resposta):

    resposta.headers["Access-Control-Allow-Origin"] = "*"

    resposta.headers[
        "Access-Control-Allow-Methods"
    ] = "GET, POST, DELETE, OPTIONS"

    resposta.headers[
        "Access-Control-Allow-Headers"
    ] = "Content-Type"

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
# SOLICITAR ATUALIZAÇÃO
# ==========================================================

@app.route(
    "/atualizar",
    methods=["POST"]
)
def atualizar():

    global atualizacao_solicitada

    atualizacao_solicitada = True

    return jsonify({

        "sucesso": True,

        "mensagem":
            "Atualização solicitada."

    })


# ==========================================================
# VERIFICAR SOLICITAÇÃO
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

        "atualizado":
            ultima_atualizacao is not None,

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
    global ultima_atualizacao


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


    # Evita conflito de nomes
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


    # ======================================================
    # REGISTRA ATUALIZAÇÃO
    # ======================================================

    ultima_atualizacao = agora

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

    # Segurança contra caminhos externos
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
# EXCLUIR
# ==========================================================

@app.route(
    "/excluir/<nome>",
    methods=["DELETE"]
)
def excluir(nome):

    nome = os.path.basename(nome)


    caminho = (
        PASTA_ARQUIVOS /
        nome
    )


    if not caminho.exists():

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo não encontrado."

        }), 404


    try:

        caminho.unlink()


        return jsonify({

            "sucesso": True,

            "mensagem":
                "Arquivo excluído."

        })


    except Exception as erro:

        return jsonify({

            "sucesso": False,

            "erro": str(erro)

        }), 500


# ==========================================================
# COMPUTADOR SECUNDÁRIO
# ==========================================================

def verificar_servidor():

    global SERVER_URL


    if not SERVER_URL:

        print(
            "ERRO: SERVER_URL não configurado."
        )

        return


    print()
    print(
        "=============================="
    )
    print(
        "    SITEKEY - SECUNDÁRIO"
    )
    print(
        "=============================="
    )
    print()

    print(
        "Servidor:",
        SERVER_URL
    )

    print(
        "Arquivo:",
        ARQUIVO
    )

    print()
    print(
        "Aguardando pedidos..."
    )
    print()


    caminho_arquivo = Path(
        ARQUIVO
    )


    while True:

        try:

            resposta = requests.get(

                SERVER_URL
                + "/verificar",

                timeout=10

            )


            if resposta.status_code != 200:

                time.sleep(
                    INTERVALO
                )

                continue


            dados = resposta.json()


            # ==================================================
            # RECEBEU PEDIDO DE ATUALIZAÇÃO
            # ==================================================

            if dados.get("atualizar"):

                print(
                    "Atualização solicitada."
                )


                if not caminho_arquivo.exists():

                    print(
                        "ERRO: config_te.txt não encontrado."
                    )

                    time.sleep(
                        INTERVALO
                    )

                    continue


                try:

                    with open(
                        caminho_arquivo,
                        "rb"
                    ) as arquivo:

                        resposta_upload = requests.post(

                            SERVER_URL
                            + "/upload",

                            files={

                                "arquivo": (

                                    ARQUIVO,

                                    arquivo,

                                    "text/plain"

                                )

                            },

                            timeout=30

                        )


                    if resposta_upload.status_code == 200:

                        print(
                            "config_te.txt enviado!"
                        )

                    else:

                        print(
                            "Erro no upload:"
                        )

                        print(
                            resposta_upload.text
                        )


                except Exception as erro:

                    print(
                        "Erro ao enviar:",
                        erro
                    )


        except requests.exceptions.RequestException:

            print(
                "Servidor indisponível..."
            )


        except Exception as erro:

            print(
                "Erro:",
                erro
            )


        time.sleep(
            INTERVALO
        )


# ==========================================================
# INICIAR SERVIDOR
# ==========================================================

if __name__ == "__main__":


    # ======================================================
    # MODO SECUNDÁRIO
    # ======================================================

    if MODO == "secundario":

        verificar_servidor()


    # ======================================================
    # MODO SERVIDOR
    # ======================================================

    else:

        print()
        print(
            "=============================="
        )
        print(
            "          SITEKEY"
        )
        print(
            "=============================="
        )
        print()

        print(
            "Servidor iniciado."
        )

        print()


        # Render fornece a porta através
        # da variável PORT.

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
