from flask import Flask, request, jsonify, send_file, render_template_string
import requests
import threading
import time
import os

app = Flask(__name__)

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

ARQUIVO = "config_te.txt"

# Se estiver testando no mesmo computador:
SERVIDOR = "http://127.0.0.1:5000"

# Quando colocar o site na internet, troque para:
# SERVIDOR = "https://seu-site.com"

INTERVALO = 1

# Pedido para atualizar o arquivo
atualizacao_solicitada = False


# ==========================================================
# PÁGINA
# ==========================================================

HTML = """

<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>Sitekey</title>

<style>

* {
    box-sizing: border-box;
    font-family: Arial, Helvetica, sans-serif;
}

body {

    margin: 0;

    min-height: 100vh;

    background: #f2f2f2;

    display: flex;

    justify-content: center;

    align-items: center;

}

.container {

    width: 90%;

    max-width: 450px;

    background: white;

    padding: 30px;

    border-radius: 15px;

    box-shadow:
        0 10px 30px
        rgba(0,0,0,0.15);

    text-align: center;

}

h1 {

    margin-top: 0;

    margin-bottom: 25px;

}

.arquivo {

    background: #f5f5f5;

    padding: 20px;

    border-radius: 10px;

    margin-bottom: 20px;

}

.nome {

    font-size: 18px;

    font-weight: bold;

}

.status {

    margin-top: 8px;

    color: #666;

    font-size: 14px;

}

.botoes {

    display: flex;

    flex-direction: column;

    gap: 10px;

}

button,
.botao {

    width: 100%;

    padding: 14px;

    border: none;

    border-radius: 8px;

    font-size: 16px;

    cursor: pointer;

    text-decoration: none;

    display: block;

}

.atualizar {

    background: #4CAF50;

    color: white;

}

.baixar {

    background: #2196F3;

    color: white;

}

.excluir {

    background: #f44336;

    color: white;

}

button:hover,
.botao:hover {

    opacity: 0.85;

}

#mensagem {

    margin-top: 20px;

    font-weight: bold;

}

</style>

</head>


<body>


<div class="container">


<h1>📁 Sitekey</h1>


<div class="arquivo">

{% if existe %}

<div class="nome">

📄 config_te.txt

</div>

<div class="status">

Arquivo disponível

</div>

{% else %}

<div class="nome">

📄 config_te.txt

</div>

<div class="status">

Nenhum arquivo disponível

</div>

{% endif %}

</div>


<div class="botoes">


<button
class="atualizar"
onclick="atualizar()">

🔄 Atualizar arquivo

</button>


{% if existe %}

<a
class="botao baixar"
href="/baixar">

📥 Baixar arquivo

</a>


<form
action="/excluir"
method="POST"
onsubmit="return confirm(
'Tem certeza que deseja excluir o arquivo?'
);">

<button
class="excluir"
type="submit">

🗑️ Excluir

</button>

</form>

{% endif %}


</div>


<div id="mensagem"></div>


</div>


<script>


async function atualizar() {


const mensagem =
document.getElementById("mensagem");


mensagem.innerText =
"⏳ Solicitando atualização...";


try {


const resposta =
await fetch(
"/atualizar",
{
method: "POST"
}
);


const dados =
await resposta.json();


if (dados.sucesso) {


mensagem.innerText =
"📡 Pedido enviado. Aguardando arquivo...";


esperarArquivo();


}


}

catch (erro) {


mensagem.innerText =
"❌ Erro de conexão.";

}

}


// ========================================================
// ESPERAR O ARQUIVO SER ATUALIZADO
// ========================================================

function esperarArquivo() {


let tentativas = 0;


const intervalo =
setInterval(
async function() {


tentativas++;


try {


const resposta =
await fetch("/status");


const dados =
await resposta.json();


if (dados.atualizado) {


clearInterval(intervalo);


mensagem.innerText =
"✅ Arquivo atualizado!";


setTimeout(
function() {

location.reload();

},
1000
);


}


}

catch (erro) {

console.log(erro);

}


// Espera no máximo 30 segundos

if (tentativas >= 30) {


clearInterval(intervalo);


mensagem.innerText =
"⚠️ O dispositivo não respondeu.";

}


},
1000
);

}


</script>


</body>

</html>

"""


# ==========================================================
# PÁGINA PRINCIPAL
# ==========================================================

@app.route("/")
def index():

    return render_template_string(
        HTML,
        existe=os.path.exists(ARQUIVO)
    )


# ==========================================================
# PEDIR ATUALIZAÇÃO
# ==========================================================

@app.route("/atualizar", methods=["POST"])
def atualizar():

    global atualizacao_solicitada

    atualizacao_solicitada = True

    return jsonify({
        "sucesso": True
    })


# ==========================================================
# STATUS DA ATUALIZAÇÃO
# ==========================================================

@app.route("/status")
def status():

    global atualizacao_solicitada

    return jsonify({

        "atualizado":
            os.path.exists(ARQUIVO)
            and not atualizacao_solicitada

    })


# ==========================================================
# VERIFICAR SE EXISTE PEDIDO
# ==========================================================

@app.route("/verificar")
def verificar():

    global atualizacao_solicitada

    if atualizacao_solicitada:

        return jsonify({
            "atualizar": True
        })

    return jsonify({
        "atualizar": False
    })


# ==========================================================
# RECEBER ARQUIVO
# ==========================================================

@app.route("/upload", methods=["POST"])
def upload():

    global atualizacao_solicitada

    if "arquivo" not in request.files:

        return jsonify({
            "erro": "Arquivo não enviado"
        }), 400


    arquivo = request.files["arquivo"]


    arquivo.save(ARQUIVO)


    atualizacao_solicitada = False


    return jsonify({
        "sucesso": True
    })


# ==========================================================
# BAIXAR
# ==========================================================

@app.route("/baixar")
def baixar():

    if not os.path.exists(ARQUIVO):

        return "Arquivo não encontrado.", 404


    return send_file(
        ARQUIVO,
        as_attachment=True,
        download_name="config_te.txt"
    )


# ==========================================================
# EXCLUIR
# ==========================================================

@app.route("/excluir", methods=["POST"])
def excluir():

    global atualizacao_solicitada

    if os.path.exists(ARQUIVO):

        os.remove(ARQUIVO)


    atualizacao_solicitada = False


    return """
    <script>
        window.location.href = "/";
    </script>
    """


# ==========================================================
# PROGRAMA QUE ENVIA O ARQUIVO
# ==========================================================

def verificar_servidor():

    global atualizacao_solicitada

    while True:

        try:

            resposta = requests.get(
                SERVIDOR + "/verificar",
                timeout=5
            )


            dados = resposta.json()


            if dados.get("atualizar"):


                if os.path.exists(ARQUIVO):


                    print(
                        "Atualização solicitada."
                    )


                    with open(
                        ARQUIVO,
                        "rb"
                    ) as arquivo:


                        requests.post(

                            SERVIDOR + "/upload",

                            files={
                                "arquivo": arquivo
                            },

                            timeout=10

                        )


                    print(
                        "config_te.txt enviado!"
                    )


        except Exception as erro:

            print(
                "Aguardando servidor..."
            )


        time.sleep(INTERVALO)


# ==========================================================
# INICIAR
# ==========================================================

if __name__ == "__main__":


    # Inicia o sistema que verifica
    # pedidos em segundo plano

    thread = threading.Thread(
        target=verificar_servidor,
        daemon=True
    )

    thread.start()


    print("")
    print("==============================")
    print("        SITEKEY")
    print("==============================")
    print("")
    print(
        "Site: http://127.0.0.1:5000"
    )
    print("")
    print(
        "Aguardando pedidos..."
    )
    print("")


    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )