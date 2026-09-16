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

MODO = os.environ.get(
    "MODE",
    "servidor"
).lower()

SERVER_URL = os.environ.get(
    "SERVER_URL",
    ""
).rstrip("/")


# ==========================================================
# TEMPO
# ==========================================================

INTERVALO = 5

TIMEOUT_ONLINE = 20

# Horário de Brasília / GMT-3
FUSO_BRASIL = timezone(
    timedelta(hours=-3)
)

# Envio automático todos os dias às 13:00
HORA_ENVIO = 13
MINUTO_ENVIO = 0


# ==========================================================
# LIMITE DE ARQUIVOS
# ==========================================================

MAXIMO_ARQUIVOS = 25


# ==========================================================
# ESTADO DO SERVIDOR
# ==========================================================

ultimo_heartbeat = 0

atualizacao_solicitada = False

ultimo_upload_manual = 0


# ==========================================================
# HORÁRIO DO BRASIL
# ==========================================================

def agora_brasil():

    return datetime.now(
        FUSO_BRASIL
    )


# ==========================================================
# CORS
# ==========================================================

@app.after_request
def adicionar_cors(resposta):

    resposta.headers[
        "Access-Control-Allow-Origin"
    ] = "*"

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
# STATUS DO PC SECUNDÁRIO
# ==========================================================

@app.route("/pc_status")
def pc_status():

    if ultimo_heartbeat == 0:

        online = False

        ultimo_contato = None

    else:

        tempo_desde_heartbeat = (
            time.time()
            - ultimo_heartbeat
        )

        online = (
            tempo_desde_heartbeat
            <= TIMEOUT_ONLINE
        )

        data_heartbeat = (
            datetime.fromtimestamp(
                ultimo_heartbeat,
                timezone.utc
            ).astimezone(
                FUSO_BRASIL
            )
        )

        ultimo_contato = (
            data_heartbeat.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )

    return jsonify({

        "online": online,

        "ultimo_contato":
            ultimo_contato,

        "modo":
            "secundario"

    })


# ==========================================================
# HEARTBEAT
# ==========================================================

@app.route(
    "/heartbeat",
    methods=["POST"]
)
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
                ).astimezone(
                    FUSO_BRASIL
                )
            )

            arquivos.append({

                "id":
                    arquivo.name,

                "nome":
                    ARQUIVO,

                "data":
                    data.strftime(
                        "%d/%m/%Y"
                    ),

                "hora":
                    data.strftime(
                        "%H:%M:%S"
                    ),

                "timestamp":
                    dados.st_mtime

            })

        except Exception:

            continue

    arquivos.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({

        "sucesso": True,

        "arquivos":
            arquivos

    })


# ==========================================================
# SOLICITAR ATUALIZAÇÃO MANUAL
# ==========================================================

@app.route(
    "/atualizar",
    methods=["POST"]
)
def atualizar():

    global atualizacao_solicitada

    atualizacao_solicitada = True

    print()
    print(
        "======================================"
    )
    print(
        "Pedido de atualização recebido."
    )
    print(
        "Aguardando PC secundário..."
    )
    print(
        "======================================"
    )
    print()

    return jsonify({

        "sucesso": True,

        "mensagem":
            "Pedido enviado ao PC secundário."

    })


# ==========================================================
# VERIFICAR PEDIDO
# ==========================================================

@app.route("/verificar")
def verificar():

    global atualizacao_solicitada

    pedido = atualizacao_solicitada

    # O pedido é consumido imediatamente.
    # Assim ele não fica esperando um arquivo
    # que possa ser criado futuramente.

    atualizacao_solicitada = False

    return jsonify({

        "atualizar":
            pedido

    })


# ==========================================================
# INFORMAR QUE NÃO EXISTE ARQUIVO
# ==========================================================

@app.route(
    "/sem_arquivo",
    methods=["POST"]
)
def sem_arquivo():

    print()
    print(
        "Pedido de atualização cancelado:"
    )
    print(
        "nenhum config_te.txt disponível."
    )
    print()

    return jsonify({

        "sucesso": True,

        "mensagem":
            "Nenhum arquivo disponível para enviar."

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
    global ultimo_upload_manual

    if "arquivo" not in request.files:

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo não enviado."

        }), 400

    arquivo = request.files[
        "arquivo"
    ]

    if not arquivo.filename:

        return jsonify({

            "sucesso": False,

            "erro":
                "Arquivo inválido."

        }), 400


    # ======================================================
    # DATA E HORA
    # ======================================================

    agora = agora_brasil()


    # ======================================================
    # NOME DO ARQUIVO
    # ======================================================

    nome = (
        "config_te_"
        + agora.strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".txt"
    )

    caminho = (
        PASTA_ARQUIVOS
        / nome
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
            PASTA_ARQUIVOS
            / nome
        )

        contador += 1


    # ======================================================
    # SALVAR ARQUIVO
    # ======================================================

    try:

        arquivo.save(
            caminho
        )

    except Exception as erro:

        print(
            "Erro ao salvar arquivo:"
        )

        print(
            erro
        )

        return jsonify({

            "sucesso": False,

            "erro":
                str(erro)

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

        for item
        in PASTA_ARQUIVOS.iterdir()

        if item.is_file()

    ]

    arquivos.sort(
        key=lambda item:
            item.stat().st_mtime
    )

    while len(arquivos) > MAXIMO_ARQUIVOS:

        arquivo_antigo = (
            arquivos.pop(0)
        )

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
    # LIMPAR PEDIDO
    # ======================================================

    atualizacao_solicitada = False

    ultimo_upload_manual = time.time()

    print(
        "Upload concluído com sucesso."
    )

    print()

    return jsonify({

        "sucesso": True,

        "arquivo":
            nome,

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
# BAIXAR ARQUIVO
# ==========================================================

@app.route(
    "/baixar/<nome>"
)
def baixar(nome):

    nome = os.path.basename(
        nome
    )

    caminho = (
        PASTA_ARQUIVOS
        / nome
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
# EXCLUIR ARQUIVO DO SERVIDOR
# ==========================================================

@app.route(
    "/excluir/<nome>",
    methods=["DELETE"]
)
def excluir(nome):

    nome = os.path.basename(
        nome
    )

    caminho = (
        PASTA_ARQUIVOS
        / nome
    )

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

            "erro":
                str(erro)

        }), 500


# ==========================================================
# ENVIAR ARQUIVO PARA O SERVIDOR
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


        # ==================================================
        # UPLOAD BEM-SUCEDIDO
        # ==================================================

        if resposta.status_code == 200:

            print(
                "config_te.txt enviado com sucesso."
            )


            # Excluir somente depois do servidor
            # confirmar o recebimento.

            try:

                caminho.unlink()

                print(
                    "config_te.txt excluído "
                    "do PC secundário."
                )

            except Exception as erro:

                print(
                    "Erro ao excluir "
                    "config_te.txt:"
                )

                print(
                    erro
                )

            return True


        # ==================================================
        # ERRO
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
# HEARTBEAT DO PC SECUNDÁRIO
# ==========================================================

def enviar_heartbeat():

    while True:

        try:

            resposta = requests.post(

                SERVER_URL
                + "/heartbeat",

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

        time.sleep(
            INTERVALO
        )


# ==========================================================
# COMPUTADOR SECUNDÁRIO
# ==========================================================

def executar_computador():

    if not SERVER_URL:

        print()
        print(
            "ERRO: SERVER_URL "
            "não configurado."
        )
        print()

        return


    caminho = Path(
        ARQUIVO
    )


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
        "Envio automático:"
        " todos os dias às 13:00"
    )

    print(
        "Horário: GMT-3 / Brasil"
    )

    print(
        "Máximo de arquivos:",
        MAXIMO_ARQUIVOS
    )

    print(
        "Excluir após envio: SIM"
    )

    print()


    # ======================================================
    # HEARTBEAT
    # ======================================================

    thread_heartbeat = threading.Thread(

        target=enviar_heartbeat,

        daemon=True

    )

    thread_heartbeat.start()


    # ======================================================
    # CONTROLE DO ÚLTIMO ENVIO AUTOMÁTICO
    # ======================================================

    arquivo_controle = Path(
        ".sitekey_controle"
    )

    ultimo_dia_automatico = ""


    if arquivo_controle.exists():

        try:

            ultimo_dia_automatico = (
                arquivo_controle
                .read_text()
                .strip()
            )

        except Exception:

            ultimo_dia_automatico = ""


    # ======================================================
    # LOOP
    # ======================================================

    while True:

        try:

            agora = agora_brasil()

            data_atual = (
                agora.strftime(
                    "%Y-%m-%d"
                )
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
                            "================================"
                        )
                        print(
                            "Pedido manual recebido."
                        )
                        print(
                            "================================"
                        )


                        # ------------------------------------------
                        # NÃO EXISTE ARQUIVO
                        # ------------------------------------------

                        if not caminho.exists():

                            print(
                                "Nenhum config_te.txt "
                                "disponível para enviar."
                            )

                            try:

                                requests.post(

                                    SERVER_URL
                                    + "/sem_arquivo",

                                    timeout=10

                                )

                            except Exception:

                                pass

                            time.sleep(2)

                            continue


                        # ------------------------------------------
                        # EXISTE ARQUIVO
                        # ------------------------------------------

                        print(
                            "Enviando config_te.txt..."
                        )

                        sucesso = (
                            enviar_arquivo(
                                caminho
                            )
                        )


                        if sucesso:

                            print(
                                "Atualização manual "
                                "concluída."
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
            # VERIFICAR ARQUIVO PARA ENVIO AUTOMÁTICO
            # ==================================================

            if caminho.exists():

                passou_do_horario = (

                    agora.hour > HORA_ENVIO

                    or (

                        agora.hour
                        == HORA_ENVIO

                        and agora.minute
                        >= MINUTO_ENVIO

                    )

                )


                # ==================================================
                # ENVIO AUTOMÁTICO
                # ==================================================

                if (

                    passou_do_horario

                    and
                    data_atual
                    != ultimo_dia_automatico

                ):

                    print()
                    print(
                        "================================"
                    )
                    print(
                        "Horário automático atingido."
                    )
                    print(
                        "Horário programado: 13:00"
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

                        ultimo_dia_automatico = (
                            data_atual
                        )


                        try:

                            arquivo_controle.write_text(
                                ultimo_dia_automatico
                            )

                        except Exception as erro:

                            print(
                                "Erro ao salvar "
                                "controle:"
                            )

                            print(
                                erro
                            )


                        print(
                            "Envio automático concluído."
                        )

                        print(
                            "Próximo envio: "
                            "amanhã às 13:00."
                        )


                    else:

                        print(
                            "Upload automático "
                            "falhou."
                        )

            time.sleep(
                INTERVALO
            )


        except Exception as erro:

            print()
            print(
                "Erro no computador:"
            )
            print(
                erro
            )

            time.sleep(
                INTERVALO
            )


# ==========================================================
# INICIALIZAÇÃO
# ==========================================================

if __name__ == "__main__":

    if MODO == "secundario":

        executar_computador()

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
