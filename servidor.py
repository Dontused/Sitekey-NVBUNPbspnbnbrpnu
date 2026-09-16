from flask import Flask, request, jsonify, send_file
import requests
import time
import os
import threading
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

ARQUIVO = "config_te.txt"

PASTA_ARQUIVOS = Path("arquivos")
PASTA_ARQUIVOS.mkdir(parents=True, exist_ok=True)

MODO = os.environ.get("MODE", "servidor").lower()

SERVER_URL = os.environ.get(
    "SERVER_URL",
    ""
).rstrip("/")

# 6 horas
SEIS_HORAS = 6 * 60 * 60

# Intervalo das verificações
INTERVALO = 5

# Considera o PC online se houver comunicação
# dentro deste período
TIMEOUT_ONLINE = 20

# Estado do PC secundário
ultimo_heartbeat = 0

# Pedido de atualização manual
atualizacao_solicitada = False

# Controle para evitar vários uploads
ultimo_upload_manual = 0


# ==========================================================
# CORS
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
# STATUS DO PC SECUNDÁRIO
# ==========================================================

@app.route("/pc_status")
def pc_status():

    if ultimo_heartbeat == 0:

        online = False
        ultimo_contato = None

    else:

        tempo_desde_heartbeat = (
            time.time() - ultimo_heartbeat
        )

        online = (
            tempo_desde_heartbeat <= TIMEOUT_ONLINE
        )

        ultimo_contato = datetime.fromtimestamp(
            ultimo_heartbeat
        ).strftime("%d/%m/%Y %H:%M:%S")

    return jsonify({

        "online": online,

        "ultimo_contato": ultimo_contato,

        "modo": "secundario"

    })


# ==========================================================
# HEARTBEAT
# ==========================================================

@app.route("/heartbeat", methods=["POST"])
def heartbeat():

    global ultimo_heartbeat

    ultimo_heartbeat = time.time()

    return jsonify({

        "sucesso": True,

        "online": True,

        "mensagem": "PC secundário conectado."

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
# PEDIR ATUALIZAÇÃO IMEDIATA
# ==========================================================

@app.route("/atualizar", methods=["POST"])
def atualizar():

    global atualizacao_solicitada

    atualizacao_solicitada = True

    print(
        "Pedido de atualização recebido."
    )

    return jsonify({

        "sucesso": True,

        "mensagem":
            "Pedido enviado ao PC secundário."

    })


# ==========================================================
# PC VERIFICA PEDIDO
# ==========================================================

@app.route("/verificar")
def verificar():

    return jsonify({

        "atualizar":
            atualizacao_solicitada

    })


# ==========================================================
# RECEBER ARQUIVO
# ==========================================================

@app.route("/upload", methods=["POST"])
def upload():

    global atualizacao_solicitada
    global ultimo_upload_manual

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

    agora = datetime.now()

    nome = (
        "config_te_"
        + agora.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".txt"
    )

    caminho = PASTA_ARQUIVOS / nome

    contador = 1

    while caminho.exists():

        nome = (
            "config_te_"
            + agora.strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
            + f"_{contador}.txt"
        )

        caminho = PASTA_ARQUIVOS / nome

        contador += 1

    arquivo.save(caminho)

    # Limpa o pedido manual
    atualizacao_solicitada = False

    ultimo_upload_manual = time.time()

    print()
    print(
        f"Arquivo recebido: {nome}"
    )
    print()

    return jsonify({

        "sucesso": True,

        "arquivo": nome,

        "data":
            agora.strftime("%d/%m/%Y"),

        "hora":
            agora.strftime("%H:%M:%S")

    })


# ==========================================================
# DOWNLOAD
# ==========================================================

@app.route("/baixar/<nome>")
def baixar(nome):

    nome = os.path.basename(nome)

    caminho = PASTA_ARQUIVOS / nome

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
# EXCLUIR ARQUIVO DO SERVIDOR
# ==========================================================

@app.route(
    "/excluir/<nome>",
    methods=["DELETE"]
)
def excluir(nome):

    nome = os.path.basename(nome)

    caminho = PASTA_ARQUIVOS / nome

    if not caminho.exists():

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo não encontrado."

        }), 404

    try:

        caminho.unlink()

        print(
            f"Arquivo excluído: {nome}"
        )

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
# ENVIAR ARQUIVO
# ==========================================================

def enviar_arquivo(caminho):

    if not SERVER_URL:

        print(
            "SERVER_URL não configurado."
        )

        return False

    try:

        with open(
            caminho,
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

            print(
                "config_te.txt enviado com sucesso."
            )

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
            "Erro ao enviar:"
        )

        print(
            erro
        )

        return False


# ==========================================================
# HEARTBEAT DO PC
# ==========================================================

def enviar_heartbeat():

    while True:

        try:

            resposta = requests.post(

                SERVER_URL + "/heartbeat",

                timeout=10

            )

            if resposta.status_code == 200:

                print(
                    "PC conectado ao servidor."
                )

        except Exception:

            print(
                "Servidor não disponível."
            )

        time.sleep(INTERVALO)


# ==========================================================
# COMPUTADOR SECUNDÁRIO
# ==========================================================

def executar_computador():

    if not SERVER_URL:

        print()
        print(
            "ERRO: SERVER_URL não configurado."
        )
        print()

        return

    caminho = Path(ARQUIVO)

    print()
    print(
        "=============================="
    )
    print(
        "       SITEKEY - PC"
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
        caminho.absolute()
    )

    print(
        "Envio automático: 6 horas"
    )

    print()

    # ======================================================
    # INICIA HEARTBEAT
    # ======================================================

    thread_heartbeat = threading.Thread(

        target=enviar_heartbeat,

        daemon=True

    )

    thread_heartbeat.start()

    # ======================================================
    # ARQUIVO DE CONTROLE
    # ======================================================

    arquivo_controle = Path(
        ".sitekey_controle"
    )

    ultima_versao_enviada = ""

    if arquivo_controle.exists():

        try:

            ultima_versao_enviada = (
                arquivo_controle
                .read_text()
                .strip()
            )

        except Exception:

            ultima_versao_enviada = ""

    # ======================================================
    # LOOP PRINCIPAL
    # ======================================================

    while True:

        try:

            if not caminho.exists():

                print(
                    "config_te.txt ainda não existe."
                )

                time.sleep(INTERVALO)

                continue

            dados = caminho.stat()

            modificacao = dados.st_mtime

            tamanho = dados.st_size

            # Identifica a versão
            versao = (
                f"{modificacao}_{tamanho}"
            )

            # ==================================================
            # VERIFICA SE É UM ARQUIVO NOVO OU ALTERADO
            # ==================================================

            if versao != ultima_versao_enviada:

                # Tempo real desde a última modificação
                tempo_desde_modificacao = (
                    time.time() - modificacao
                )

                # ==================================================
                # PEDIDO MANUAL
                # ==================================================

                try:

                    resposta = requests.get(

                        SERVER_URL
                        + "/verificar",

                        timeout=10

                    )

                    if resposta.status_code == 200:

                        dados_pedido = (
                            resposta.json()
                        )

                        if dados_pedido.get(
                            "atualizar"
                        ):

                            print()
                            print(
                                "Pedido manual recebido."
                            )

                            sucesso = (
                                enviar_arquivo(
                                    caminho
                                )
                            )

                            if sucesso:

                                ultima_versao_enviada = (
                                    versao
                                )

                                arquivo_controle.write_text(
                                    ultima_versao_enviada
                                )

                            time.sleep(2)

                            continue

                except requests.exceptions.RequestException:

                    pass

                # ==================================================
                # ENVIO AUTOMÁTICO APÓS 6 HORAS
                # ==================================================

                if (
                    tempo_desde_modificacao
                    >= SEIS_HORAS
                ):

                    print()
                    print(
                        "6 horas desde a última alteração."
                    )

                    print(
                        "Enviando automaticamente..."
                    )

                    sucesso = (
                        enviar_arquivo(
                            caminho
                        )
                    )

                    if sucesso:

                        ultima_versao_enviada = (
                            versao
                        )

                        arquivo_controle.write_text(
                            ultima_versao_enviada
                        )

                        print(
                            "Envio automático concluído."
                        )

                    else:

                        print(
                            "Upload falhou."
                        )

            time.sleep(INTERVALO)

        except Exception as erro:

            print(
                "Erro no computador:"
            )

            print(
                erro
            )

            time.sleep(INTERVALO)


# ==========================================================
# INICIALIZAÇÃO
# ==========================================================

if __name__ == "__main__":

    # ======================================================
    # PC SECUNDÁRIO
    # ======================================================

    if MODO == "secundario":

        executar_computador()

    # ======================================================
    # RENDER / SERVIDOR
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
