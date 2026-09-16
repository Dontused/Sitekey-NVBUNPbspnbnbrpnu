from flask import Flask, request, jsonify, send_file
import requests
import time
import os
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone

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


# ==========================================================
# TEMPO
# ==========================================================

# 24 horas
VINTE_QUATRO_HORAS = 24 * 60 * 60

# Intervalo das verificações
INTERVALO = 5

# Considera o PC online se houver comunicação
# dentro deste período
TIMEOUT_ONLINE = 20

# Horário de Brasília / GMT-3
FUSO_BRASIL = timezone(timedelta(hours=-3))


# ==========================================================
# LIMITE DE ARQUIVOS
# ==========================================================

MAXIMO_ARQUIVOS = 25


# ==========================================================
# ESTADO DO PC
# ==========================================================

ultimo_heartbeat = 0

# Pedido de atualização manual
atualizacao_solicitada = False

# Controle do último upload manual
ultimo_upload_manual = 0


# ==========================================================
# DATA/HORA DO BRASIL
# ==========================================================

def agora_brasil():

    return datetime.now(FUSO_BRASIL)


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

        data_heartbeat = (
            datetime.fromtimestamp(
                ultimo_heartbeat,
                timezone.utc
            ).astimezone(FUSO_BRASIL)
        )

        ultimo_contato = (
            data_heartbeat.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )

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

        "mensagem":
            "PC secundário conectado."

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

            data = (
                datetime.fromtimestamp(
                    dados.st_mtime,
                    timezone.utc
                ).astimezone(FUSO_BRASIL)
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

    print()
    print("======================================")
    print("Pedido de atualização recebido.")
    print("Aguardando PC secundário...")
    print("======================================")
    print()

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

    # ======================================================
    # DATA/HORA DO BRASIL
    # ======================================================

    agora = agora_brasil()

    # ======================================================
    # CRIA NOME DO ARQUIVO
    # ======================================================

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

    # ======================================================
    # SALVAR ARQUIVO
    # ======================================================

    try:

        arquivo.save(caminho)

    except Exception as erro:

        print()
        print(
            "Erro ao salvar arquivo:"
        )
        print(
            erro
        )

        return jsonify({

            "sucesso": False,

            "erro": str(erro)

        }), 500

    print()
    print(
        f"Arquivo recebido: {nome}"
    )

    # ======================================================
    # MANTER NO MÁXIMO 25 ARQUIVOS
    # ======================================================

    arquivos = [

        item

        for item in PASTA_ARQUIVOS.iterdir()

        if item.is_file()

    ]

    arquivos.sort(
        key=lambda item: item.stat().st_mtime
    )

    while len(arquivos) > MAXIMO_ARQUIVOS:

        arquivo_antigo = arquivos.pop(0)

        try:

            arquivo_antigo.unlink()

            print(
                "Arquivo antigo excluído:"
            )

            print(
                arquivo_antigo.name
            )

        except Exception as erro:

            print(
                "Erro ao excluir arquivo antigo:"
            )

            print(
                erro
            )

    # ======================================================
    # LIMPAR PEDIDO MANUAL
    # ======================================================

    atualizacao_solicitada = False

    ultimo_upload_manual = time.time()

    print(
        "Upload concluído com sucesso."
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

        # ==================================================
        # UPLOAD BEM-SUCEDIDO
        # ==================================================

        if resposta.status_code == 200:

            print(
                "config_te.txt enviado com sucesso."
            )

            # ==================================================
            # EXCLUIR ARQUIVO ORIGINAL
            # SOMENTE APÓS O SERVIDOR CONFIRMAR O UPLOAD
            # ==================================================

            try:

                caminho.unlink()

                print(
                    "config_te.txt excluído do PC secundário."
                )

            except Exception as erro:

                print(
                    "Erro ao excluir config_te.txt:"
                )

                print(
                    erro
                )

            return True

        # ==================================================
        # ERRO NO UPLOAD
        # ==================================================

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
        "Envio automático: 24 horas"
    )

    print(
        "Horário: GMT-3 / Brasil"
    )

    print(
        "Máximo de arquivos no servidor:",
        MAXIMO_ARQUIVOS
    )

    print(
        "Excluir arquivo após envio: SIM"
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

            # ==================================================
            # VERIFICA SE CONFIG_TE EXISTE
            # ==================================================

            if not caminho.exists():

                time.sleep(INTERVALO)

                continue

            # ==================================================
            # INFORMAÇÕES DO ARQUIVO
            # ==================================================

            dados = caminho.stat()

            modificacao = dados.st_mtime

            tamanho = dados.st_size

            # Identifica a versão do arquivo
            versao = (
                f"{modificacao}_{tamanho}"
            )

            # ==================================================
            # VERIFICA PEDIDO MANUAL SEMPRE
            # ==================================================

            try:

                resposta = requests.get(

                    SERVER_URL + "/verificar",

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
                            "================================"
                        )

                        print(
                            "Pedido manual recebido."
                        )

                        print(
                            "Enviando config_te.txt..."
                        )

                        print(
                            "================================"
                        )

                        sucesso = (
                            enviar_arquivo(
                                caminho
                            )
                        )

                        if sucesso:

                            # O arquivo foi excluído
                            # dentro de enviar_arquivo()
                            ultima_versao_enviada = (
                                versao
                            )

                            try:

                                arquivo_controle.write_text(
                                    ultima_versao_enviada
                                )

                            except Exception as erro:

                                print(
                                    "Erro ao salvar controle:"
                                )

                                print(
                                    erro
                                )

                            print(
                                "Atualização manual concluída."
                            )

                        else:

                            print(
                                "Falha no envio manual."
                            )

                        time.sleep(2)

                        continue

            except requests.exceptions.RequestException:

                pass

            # ==================================================
            # VERIFICA ARQUIVO NOVO OU ALTERADO
            # ==================================================

            if versao != ultima_versao_enviada:

                # ==================================================
                # TEMPO DESDE A MODIFICAÇÃO
                # ==================================================

                tempo_desde_modificacao = (
                    time.time() - modificacao
                )

                # ==================================================
                # ENVIO AUTOMÁTICO APÓS 24 HORAS
                # ==================================================

                if (
                    tempo_desde_modificacao
                    >= VINTE_QUATRO_HORAS
                ):

                    print()
                    print(
                        "24 horas desde a última alteração."
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

                        try:

                            arquivo_controle.write_text(
                                ultima_versao_enviada
                            )

                        except Exception as erro:

                            print(
                                "Erro ao salvar controle:"
                            )

                            print(
                                erro
                            )

                        print(
                            "Envio automático concluído."
                        )

                    else:

                        print(
                            "Upload automático falhou."
                        )

            time.sleep(INTERVALO)

        except Exception as erro:

            print()
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
