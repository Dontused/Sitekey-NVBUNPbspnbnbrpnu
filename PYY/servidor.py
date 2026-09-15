from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
from datetime import datetime
import argparse
import threading
import time
import requests
import os
import sys


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ARQUIVO_ORIGINAL = "config_te.txt"

# Pasta onde os arquivos recebidos ficarão acumulados
PASTA_ARQUIVOS = Path(__file__).parent / "arquivos"

# Endereço padrão do servidor
PORTA = 5000

# Intervalo que o computador secundário verifica
# se existe uma solicitação de atualização
INTERVALO_VERIFICACAO = 2


# ============================================================
# SERVIDOR FLASK
# ============================================================

app = Flask(__name__)

# Permite que o index.html do GitHub Pages
# faça requisições para este servidor.
CORS(app)


# Garante que a pasta exista
PASTA_ARQUIVOS.mkdir(parents=True, exist_ok=True)


# Indica se existe uma solicitação de atualização
update_solicitado = False

# Protege a variável acima contra acessos simultâneos
lock = threading.Lock()


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():
    return jsonify({
        "status": "online",
        "servidor": "Sitekey"
    })


# ============================================================
# LISTAR TODOS OS ARQUIVOS
# ============================================================

@app.route("/arquivos", methods=["GET"])
def listar_arquivos():

    arquivos = []

    for arquivo in PASTA_ARQUIVOS.iterdir():

        if not arquivo.is_file():
            continue

        try:
            estatisticas = arquivo.stat()

            data_envio = datetime.fromtimestamp(
                estatisticas.st_mtime
            )

            arquivos.append({
                "id": arquivo.name,
                "nome": "config_te.txt",
                "data": data_envio.strftime("%d/%m/%Y"),
                "hora": data_envio.strftime("%H:%M:%S"),
                "timestamp": estatisticas.st_mtime
            })

        except Exception:
            continue

    # Mais recentes primeiro
    arquivos.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return jsonify({
        "sucesso": True,
        "arquivos": arquivos
    })


# ============================================================
# SOLICITAR UPDATE
# ============================================================

@app.route("/update", methods=["POST"])
def solicitar_update():

    global update_solicitado

    with lock:
        update_solicitado = True

    return jsonify({
        "sucesso": True,
        "mensagem": "Atualização solicitada. Aguardando o computador secundário."
    })


# ============================================================
# VERIFICAR SE EXISTE UPDATE
# ============================================================

@app.route("/verificar-update", methods=["GET"])
def verificar_update():

    global update_solicitado

    with lock:

        if update_solicitado:

            return jsonify({
                "update": True
            })

        return jsonify({
            "update": False
        })


# ============================================================
# UPLOAD DE NOVO ARQUIVO
# ============================================================

@app.route("/upload", methods=["POST"])
def receber_arquivo():

    global update_solicitado

    if "arquivo" not in request.files:

        return jsonify({
            "sucesso": False,
            "mensagem": "Nenhum arquivo foi enviado."
        }), 400

    arquivo = request.files["arquivo"]

    if arquivo.filename == "":

        return jsonify({
            "sucesso": False,
            "mensagem": "Nome de arquivo inválido."
        }), 400


    # ========================================================
    # CRIA UM NOME ÚNICO
    # ========================================================

    agora = datetime.now()

    nome_arquivo = (
        "config_te_"
        + agora.strftime("%Y-%m-%d_%H-%M-%S")
        + ".txt"
    )

    caminho = PASTA_ARQUIVOS / nome_arquivo


    # Evita colisão caso dois arquivos sejam enviados
    contador = 1

    while caminho.exists():

        nome_arquivo = (
            "config_te_"
            + agora.strftime("%Y-%m-%d_%H-%M-%S")
            + f"_{contador}"
            + ".txt"
        )

        caminho = PASTA_ARQUIVOS / nome_arquivo

        contador += 1


    # Salva a cópia
    arquivo.save(caminho)


    # ========================================================
    # REMOVE A SOLICITAÇÃO DE UPDATE
    # ========================================================

    with lock:
        update_solicitado = False


    return jsonify({
        "sucesso": True,
        "mensagem": "Arquivo recebido com sucesso.",
        "arquivo": nome_arquivo,
        "data": agora.strftime("%d/%m/%Y"),
        "hora": agora.strftime("%H:%M:%S")
    })


# ============================================================
# DOWNLOAD
# ============================================================

@app.route("/download/<nome_arquivo>", methods=["GET"])
def baixar_arquivo(nome_arquivo):

    # Segurança: não permite caminhos como ../
    nome_arquivo = os.path.basename(nome_arquivo)

    caminho = PASTA_ARQUIVOS / nome_arquivo

    if not caminho.exists() or not caminho.is_file():

        return jsonify({
            "sucesso": False,
            "mensagem": "Arquivo não encontrado."
        }), 404


    return send_file(
        caminho,
        as_attachment=True,
        download_name="config_te.txt"
    )


# ============================================================
# DELETE
# ============================================================

@app.route("/delete/<nome_arquivo>", methods=["DELETE"])
def excluir_arquivo(nome_arquivo):

    # Segurança
    nome_arquivo = os.path.basename(nome_arquivo)

    caminho = PASTA_ARQUIVOS / nome_arquivo

    if not caminho.exists():

        return jsonify({
            "sucesso": False,
            "mensagem": "Arquivo não encontrado."
        }), 404


    try:

        caminho.unlink()

        return jsonify({
            "sucesso": True,
            "mensagem": "Arquivo excluído."
        })

    except Exception as erro:

        return jsonify({
            "sucesso": False,
            "mensagem": f"Erro ao excluir: {erro}"
        }), 500


# ============================================================
# STATUS DO SERVIDOR
# ============================================================

@app.route("/status", methods=["GET"])
def status():

    quantidade = len([
        x for x in PASTA_ARQUIVOS.iterdir()
        if x.is_file()
    ])

    return jsonify({
        "online": True,
        "arquivos": quantidade
    })


# ============================================================
# COMPUTADOR SECUNDÁRIO
# ============================================================

def iniciar_secundario(endereco_servidor):

    print()
    print("=" * 55)
    print("     SITEKEY - COMPUTADOR SECUNDÁRIO")
    print("=" * 55)
    print()
    print("Servidor:", endereco_servidor)
    print("Arquivo:", ARQUIVO_ORIGINAL)
    print()
    print("Aguardando solicitações de atualização...")
    print()


    caminho_arquivo = Path(__file__).parent / ARQUIVO_ORIGINAL


    while True:

        try:

            # ------------------------------------------------
            # Verifica se o servidor solicitou atualização
            # ------------------------------------------------

            resposta = requests.get(
                endereco_servidor.rstrip("/") + "/verificar-update",
                timeout=10
            )


            if resposta.status_code == 200:

                dados = resposta.json()

                if dados.get("update") is True:

                    print("Update solicitado!")


                    # ----------------------------------------
                    # Verifica se o arquivo existe
                    # ----------------------------------------

                    if not caminho_arquivo.exists():

                        print(
                            "ERRO: config_te.txt não encontrado."
                        )

                        time.sleep(INTERVALO_VERIFICACAO)

                        continue


                    # ----------------------------------------
                    # Envia o arquivo
                    # ----------------------------------------

                    with open(
                        caminho_arquivo,
                        "rb"
                    ) as arquivo:

                        arquivos = {
                            "arquivo": (
                                ARQUIVO_ORIGINAL,
                                arquivo,
                                "text/plain"
                            )
                        }

                        envio = requests.post(
                            endereco_servidor.rstrip("/")
                            + "/upload",
                            files=arquivos,
                            timeout=30
                        )


                    if envio.status_code == 200:

                        dados_envio = envio.json()

                        print(
                            "Arquivo enviado com sucesso!"
                        )

                        print(
                            "Data:",
                            dados_envio.get("data")
                        )

                        print(
                            "Hora:",
                            dados_envio.get("hora")
                        )

                    else:

                        print(
                            "Erro ao enviar:",
                            envio.text
                        )


        except requests.exceptions.RequestException as erro:

            print(
                "Servidor indisponível:",
                erro
            )

        except Exception as erro:

            print(
                "Erro:",
                erro
            )


        time.sleep(INTERVALO_VERIFICACAO)


# ============================================================
# INICIALIZAÇÃO
# ============================================================

def iniciar_servidor():

    print()
    print("=" * 55)
    print("             SITEKEY - SERVIDOR")
    print("=" * 55)
    print()
    print("Servidor iniciado.")
    print(f"Porta: {PORTA}")
    print()
    print("Aguardando conexões...")
    print()

    app.run(
        host="0.0.0.0",
        port=PORTA,
        debug=False,
        threaded=True
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--secundario",
        action="store_true",
        help="Executa como computador secundário."
    )

    parser.add_argument(
        "--servidor",
        type=str,
        help="Endereço do servidor principal."
    )

    args = parser.parse_args()


    # --------------------------------------------------------
    # MODO SECUNDÁRIO
    # --------------------------------------------------------

    if args.secundario:

        if not args.servidor:

            print(
                "ERRO: informe o endereço do servidor."
            )

            print()
            print(
                "Exemplo:"
            )

            print(
                "python servidor.py --secundario "
                "--servidor http://SEU_SERVIDOR:5000"
            )

            sys.exit(1)


        iniciar_secundario(
            args.servidor
        )


    # --------------------------------------------------------
    # MODO SERVIDOR
    # --------------------------------------------------------

    else:

        iniciar_servidor()