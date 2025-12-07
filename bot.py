# bot.py
from time import sleep
import discord
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import os
import uuid

# ---------------- CONFIG / TOKEN ----------------
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise SystemExit("TOKEN não encontrado. Crie .env com TOKEN=seu_token")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- RECURSOS ----------------
IMAGENS = {
    "lanches": "lanches.png",
    "pizzas": "pizzas.png",
    "porcoes": "porcoes.png",
    "bebidas": "bebidas.png"
}

ITENS = {
    "lanches": ["Hambúrguer", "X-Bacon", "X-Burguer", "X-Calabresa", "X-Egg", "MC bacon"],
    "pizzas": ["Pepperoni", "Portuguesa", "Napolitana", "Tropical", "Calabresa"],
    "porcoes": ["Mandioca","Batata ou Polenta","Croquete","Frango à Passarinho","Torresmo","Frango c/ Polenta | Batata | Mandioca","Pastel de Jabá c/ Mussarela"],
    "bebidas": ["Água", "Refrigerante", "Sucos", "Cerveja", "Chopp", "Café", "Capuccino"]
}

SABORES = {
    "Refrigerante": ["Coca-Cola", "Pepsi", "Guaraná"],
    "Sucos": ["Laranja", "Uva", "Maracujá"]
}
# ---------------- PREÇOS REAIS ----------------

PRECOS = {
    "lanches": {
        "Hambúrguer": 22,
        "X-Bacon": 18,
        "X-Burguer": 22,
        "X-Calabresa": 24,
        "X-Egg": 23,
        "MC bacon": 26
    },
    "porcoes": {
        "Mandioca": {"G": 35, "P": 22},
        "Batata ou Polenta": {"G": 35, "P": 22},
        "Croquete": {"G": 47, "M": 35, "P": 20},
        "Frango à Passarinho": {"G": 49, "P": 31},
        "Frango c/ Polenta | Batata | Mandioca": {"G": 43, "P": 28},
        "Torresmo": 32,
        "Pastel de Jabá c/ Mussarela": 24
    },
    "bebidas": {
        "Água": 4,
        "Refrigerante": 5,
        "Sucos": 8,
        "Cerveja": 9,
        "Chopp": 10,
        "Café": 4,
        "Capuccino": 8
    },
    "pizzas": {
        "P": 34,
        "M": 40,
        "G": 50
    }
}



# ---------------- MEMÓRIA (somente enquanto o bot roda) ----------------
usuarios_atendidos = set()   # marca quem já recebeu a saudação nesta execução
carrinhos = {}               # { user_id: [ {"categoria":..., "item":..., "preco":...}, ... ] }
checkout_flow = {}           # { user_id: {"etapa": "nome"/"endereco"/"pagamento", "pedido_meta": {...}} }

# Função simples que estima preço (pode trocar por preços reais)
def preco_real(categoria: str, item: str, extra: str = None) -> float:
    categoria = categoria.lower()

    # --- PIZZAS (dependem do tamanho) ---
    if categoria == "pizzas":
        # extra = tamanho
        if extra in PRECOS["pizzas"]:
            return PRECOS["pizzas"][extra]
        return 0.0

    # --- PORÇÕES (algumas têm tamanhos, outras não) ---
    if categoria == "porcoes":
        tabela = PRECOS["porcoes"].get(item)

        if isinstance(tabela, dict):  # porção pequena/média/grande
            return tabela.get(extra, 0.0)

        return tabela or 0.0  # porção com preço fixo

    # --- LANCHES E BEBIDAS (preço fixo) ---
    if categoria in PRECOS:
        return PRECOS[categoria].get(item, 0.0)

    return 0.0



def formatar_carrinho_list(cart):
    if not cart:
        return "Seu carrinho está vazio."

    lines = []
    total = 0.0

    for i, it in enumerate(cart, start=1):
        preco = it["preco"]  # agora usa SEMPRE o preço real que já foi salvo
        lines.append(f"{i}. {it['item']} ({it['categoria']}) — R$ {preco:.2f}")
        total += preco

    lines.append(f"\nTotal: R$ {total:.2f}")
    return "\n".join(lines)


# ---------------- VIEWS ----------------

class CategoriaView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🍔 Lanches", style=discord.ButtonStyle.primary)
    async def lanches(self, interaction: discord.Interaction, button: discord.ui.Button):
        await enviar_cardapio_categoria(interaction, "lanches")

    @discord.ui.button(label="🍕 Pizzas", style=discord.ButtonStyle.primary)
    async def pizzas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await enviar_cardapio_categoria(interaction, "pizzas")

    @discord.ui.button(label="🍟 Porções", style=discord.ButtonStyle.primary)
    async def porcoes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await enviar_cardapio_categoria(interaction, "porcoes")

    @discord.ui.button(label="🥤 Bebidas", style=discord.ButtonStyle.primary)
    async def bebidas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await enviar_cardapio_categoria(interaction, "bebidas")


class AcoesAposAdicionar(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

        # Ver carrinho
        btn_ver = Button(label="🛒 Ver carrinho", style=discord.ButtonStyle.secondary)
        async def ver_cb(interaction: discord.Interaction):
            await mostrar_carrinho_interaction(interaction, self.user_id)
        btn_ver.callback = ver_cb
        self.add_item(btn_ver)

        # Continuar comprando
        btn_cont = Button(label="🍴 Continuar comprando", style=discord.ButtonStyle.primary)
        async def cont_cb(interaction: discord.Interaction):
            await interaction.response.send_message("Escolha outra categoria:", view=CategoriaView(), ephemeral=True)
        btn_cont.callback = cont_cb
        self.add_item(btn_cont)


class CarrinhoView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

        btn_checkout = Button(label="✅ Finalizar (checkout)", style=discord.ButtonStyle.success)
        async def checkout_cb(interaction: discord.Interaction):
            await iniciar_checkout_por_interaction(interaction, self.user_id)
        btn_checkout.callback = checkout_cb
        self.add_item(btn_checkout)

        btn_cont = Button(label="🍴 Continuar comprando", style=discord.ButtonStyle.primary)
        async def cont_cb(interaction: discord.Interaction):
            await interaction.response.send_message("Escolha outra categoria:", view=CategoriaView(), ephemeral=True)
        btn_cont.callback = cont_cb
        self.add_item(btn_cont)

        btn_limpar = Button(label="🗑️ Esvaziar carrinho", style=discord.ButtonStyle.danger)
        async def limpar_cb(interaction: discord.Interaction):
            carrinhos.pop(self.user_id, None)
            await interaction.response.send_message("🗑️ Carrinho esvaziado.", ephemeral=True)
        btn_limpar.callback = limpar_cb
        self.add_item(btn_limpar)


class AvaliacaoView(View):
    def __init__(self):
        super().__init__(timeout=None)

        # Criar 5 botões iguais, cada um com 1 estrela
        for posicao in range(1, 6):
            btn = Button(
                label="⭐",
                style=discord.ButtonStyle.secondary,
                custom_id=f"star_{posicao}"
            )
            btn.callback = self.receber_avaliacao
            self.add_item(btn)

    async def receber_avaliacao(self, interaction: discord.Interaction):
        # Descobre qual botão foi clicado
        posicao = int(interaction.data["custom_id"].split("_")[1])

        # Confirma para o usuário (somente para ele)
        await interaction.response.send_message(
            f"Obrigado pela avaliação! Você deu **{posicao} estrela(s)** ⭐",
            ephemeral=True
        )

        # Desativa os botões após avaliar
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)



# ---------------- LÓGICA: enviar cardápio e criar botões dinâmicos ----------------
async def enviar_cardapio_categoria(interaction: discord.Interaction, categoria: str):
    # envia imagem (se existir)
    img = IMAGENS.get(categoria)
    if img and os.path.exists(img):
        await interaction.response.send_message(file=discord.File(img))
    else:
        await interaction.response.send_message(f"Cardápio: {categoria.capitalize()} (imagem não encontrada)")

    # cria view com botões de item (cada botão adiciona ao carrinho)
    view = View()
    for item in ITENS[categoria]:
        btn = Button(label=item, style=discord.ButtonStyle.success)

        async def make_cb(inter: discord.Interaction, item_local=item, categoria_local=categoria):
            uid = inter.user.id
            carrinhos.setdefault(uid, [])

            # ------------------- PIZZAS -------------------
            if categoria_local == "pizzas":
                view_tamanho = View()
                for tamanho in ["P", "M", "G"]:
                    b = Button(
                        label=f"{tamanho} — R$ {PRECOS['pizzas'][tamanho]}",
                        style=discord.ButtonStyle.secondary,
                    )

                    async def tamanho_cb(inter2, tam=tamanho):
                        nome_item = f"{item_local} ({tam})"
                        preco = preco_real("pizzas", item_local, tam)

                        carrinhos[uid].append({
                            "categoria": "pizzas",
                            "item": nome_item,
                            "preco": preco
                        })

                        await inter2.response.send_message(
                            f"🍕 **{nome_item}** adicionada ao carrinho! (R$ {preco:.2f})",
                            view=AcoesAposAdicionar(uid),
                            ephemeral=True
                        )

                    b.callback = tamanho_cb
                    view_tamanho.add_item(b)

                await inter.response.send_message(
                    f"Escolha o **tamanho da pizza {item_local}**:",
                    view=view_tamanho,
                    ephemeral=True
                )
                return

            # ------------------- PORÇÕES -------------------
            if categoria_local == "porcoes":
                preco_tabela = PRECOS["porcoes"].get(item_local)

                # porção com tamanho
                if isinstance(preco_tabela, dict):
                    view_tam = View()
                    for tam, preco in preco_tabela.items():
                        b = Button(label=f"{tam} — R$ {preco}", style=discord.ButtonStyle.secondary)

                        async def tam_cb(inter2, tam=tam, preco=preco):
                            nome_item = f"{item_local} ({tam})"

                            carrinhos[uid].append({
                                "categoria": "porções",
                                "item": nome_item,
                                "preco": float(preco)
                            })

                            await inter2.response.send_message(
                                f"🍟 **{nome_item}** adicionada ao carrinho! (R$ {preco:.2f})",
                                view=AcoesAposAdicionar(uid),
                                ephemeral=True
                            )

                        b.callback = tam_cb
                        view_tam.add_item(b)

                    await inter.response.send_message(
                        f"Escolha o tamanho de **{item_local}**:",
                        view=view_tam,
                        ephemeral=True
                    )
                    return

                # porção SEM tamanho (preço fixo)
                preco = float(preco_tabela)

                carrinhos[uid].append({
                    "categoria": "porções",
                    "item": item_local,
                    "preco": preco
                })

                await inter.response.send_message(
                    f"🍟 **{item_local}** adicionada ao carrinho! (R$ {preco:.2f})",
                    view=AcoesAposAdicionar(uid),
                    ephemeral=True
                )
                return

            # ------------------- LANCHES -------------------
            if categoria_local == "lanches":
                preco = preco_real("lanches", item_local)
                carrinhos[uid].append({
                    "categoria": "lanches",
                    "item": item_local,
                    "preco": preco
                })

                await inter.response.send_message(
                    f"🍔 **{item_local}** adicionado ao carrinho! (R$ {preco:.2f})",
                    view=AcoesAposAdicionar(uid),
                    ephemeral=True
                )
                return

            # ------------------- BEBIDAS -------------------
            if categoria_local == "bebidas":

                # Caso tenha sabores (Refrigerante, Sucos)
                if item_local in SABORES:
                    view_sabores = View()

                    for sabor in SABORES[item_local]:

                        b = Button(
                            label=f"{sabor} — R$ {preco_real('bebidas', item_local)}",
                            style=discord.ButtonStyle.secondary
                        )

                        async def sabor_cb(inter2, sabor_local=sabor):
                            nome_item = f"{item_local} ({sabor_local})"
                            preco = preco_real("bebidas", item_local)

                            carrinhos[uid].append({
                                "categoria": "bebidas",
                                "item": nome_item,
                                "preco": preco
                            })

                            await inter2.response.send_message(
                                f"🥤 **{nome_item}** adicionado ao carrinho! (R$ {preco:.2f})",
                                view=AcoesAposAdicionar(uid),
                                ephemeral=True
                            )

                        b.callback = sabor_cb
                        view_sabores.add_item(b)

                    await inter.response.send_message(
                        f"Escolha o **sabor de {item_local}**:",
                        view=view_sabores,
                        ephemeral=True
                    )
                    return

                # Bebidas SEM sabor (água, cerveja, chopp...)
                preco = preco_real("bebidas", item_local)
                carrinhos[uid].append({
                    "categoria": "bebidas",
                    "item": item_local,
                    "preco": preco
                })

                await inter.response.send_message(
                    f"🥤 **{item_local}** adicionada ao carrinho! (R$ {preco:.2f})",
                    view=AcoesAposAdicionar(uid),
                    ephemeral=True
                )
                return



        btn.callback = make_cb
        view.add_item(btn)

    await interaction.followup.send(f"Escolha uma opção de **{categoria.capitalize()}**:", view=view)


# ---------------- MOSTRAR CARRINHO (por interaction) ----------------
async def mostrar_carrinho_interaction(interaction: discord.Interaction, user_id: int):
    cart = carrinhos.get(user_id, [])
    texto = formatar_carrinho_list(cart)
    # usa ephemeral para somente o usuário ver
    await interaction.response.send_message(f"🧺 Seu carrinho:\n\n{texto}", view=CarrinhoView(user_id), ephemeral=True)


# ---------------- INICIAR CHECKOUT (via comando ou botão) ----------------
async def iniciar_checkout_por_interaction(interaction: discord.Interaction, user_id: int):
    cart = carrinhos.get(user_id, [])

    if not cart:
        await interaction.response.send_message("Seu carrinho está vazio.", ephemeral=True)
        return

    # --- VERIFICAR SE NÃO TEM BEBIDA ---
    tem_bebida = any(i["categoria"] == "bebidas" for i in cart)

    if not tem_bebida:
        view = View()

        # botão adicionar bebida
        btn_add = Button(label="🥤 Quero adicionar bebida", style=discord.ButtonStyle.primary)

        async def add_cb(inter):
            # chama diretamente o cardápio de bebidas
            await enviar_cardapio_categoria(inter, "bebidas")

        btn_add.callback = add_cb
        view.add_item(btn_add)

        # botão continuar
        btn_cont = Button(label="Continuar sem bebida", style=discord.ButtonStyle.secondary)
        async def cont_cb(inter):
            checkout_flow[user_id] = {"etapa": "nome", "cart": cart.copy(), "nome": "", "endereco": "", "pagamento": ""}
            await inter.response.send_message("Ok! Vamos finalizar. Digite **seu nome completo**:", ephemeral=True)
        btn_cont.callback = cont_cb
        view.add_item(btn_cont)

        await interaction.response.send_message(
            "Você não adicionou nenhuma bebida. Deseja incluir algo pra beber?",
            view=view,
            ephemeral=True
        )
        return

    # --- SE JÁ TIVER BEBIDA, COMEÇAR CHECKOUT NORMAL ---
    checkout_flow[user_id] = {"etapa": "nome", "cart": cart.copy(), "nome": "", "endereco": "", "pagamento": ""}
    await interaction.response.send_message("Digite **seu nome completo** para finalizar o pedido.", ephemeral=True)


# ---------------- ON_MESSAGE: saudação única por execução + captura do checkout ----------------
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    user_id = message.author.id

    # Se o usuário está em fluxo de checkout, processa as etapas aqui
    if user_id in checkout_flow:
        estado = checkout_flow[user_id]
        etapa = estado.get("etapa")

        # se for comando começando com "!" durante o checkout, avisa e ignora
        if message.content.startswith("!"):
            await message.channel.send("Você está no fluxo de checkout. Termine (ou cancele com `!cancelar`) antes de usar comandos.")
            return

        if etapa == "nome":
            estado["nome"] = message.content.strip()
            estado["etapa"] = "endereco"
            await message.channel.send("✅ Nome registrado. Agora envie **seu endereço completo**:")
            return
        elif etapa == "endereco":
            estado["endereco"] = message.content.strip()
            estado["etapa"] = "pagamento"
            await message.channel.send("✅ Endereço registrado.\nEscolha forma de pagamento: `pix`, `dinheiro` ou `cartao`")
            return
        elif etapa == "pagamento":
            escolha = message.content.strip().lower()
            if escolha not in ("pix", "dinheiro", "cartao"):
                await message.channel.send("Forma inválida. Digite `pix`, `dinheiro` ou `cartao`.")
                return
            estado["pagamento"] = escolha

            # monta resumo do pedido
            cart = estado["cart"]
            total = sum(i["preco"] for i in cart)
            codigo = str(uuid.uuid4())[:8].upper()
            resumo = (
                f"✅ **PEDIDO FINALIZADO!**\n\n"
                f"ID: `{codigo}`\n"
                f"Cliente: {estado['nome']}\n"
                f"Endereço: {estado['endereco']}\n"
                f"Pagamento: {estado['pagamento']}\n\n"
                "Itens:\n" + "\n".join(f"- {it['item']} — R$ {it['preco']:.2f}" for it in cart) +
                f"\n\nTotal: R$ {total:.2f}"
            )

            if escolha == "pix":
                pix_code = f"PIX-{uuid.uuid4().hex[:16].upper()}"
                resumo += f"\n\nCódigo PIX (fake): `{pix_code}`\n(Envie comprovante ou digite `ok` para confirmar.)"

            await message.channel.send(resumo)
            sleep(1)
            await message.channel.send(
                    "⏳ Seu pedido chegará em **até 45 minutos**!\n\n"
                    "⭐ Enquanto aguarda, deixe sua avaliação:",
                    view=AvaliacaoView()
                )
            # limpar estado e carrinho (já finalizado)
            checkout_flow.pop(user_id, None)
            carrinhos.pop(user_id, None)
            return

    # Se não está em fluxo de checkout, trata a saudação única por execução
    # se a mensagem for um comando, processa comandos normalmente
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    if user_id not in usuarios_atendidos:
        usuarios_atendidos.add(user_id)
        await message.channel.send(
            f"Olá {message.author.mention}! 👋\n"
            "Seja bem-vindo ao nosso restaurante!\n"
            "Escolha uma categoria abaixo para ver o cardápio 🍽️",
            view=CategoriaView()
        )
        return


    # usuário já foi atendido nesta execução: não responde novamente a mensagens comuns
    # mas deixamos comandos funcionar:
    await bot.process_commands(message)


# ---------------- COMANDO !cardapio ----------------
@bot.command(name="cardapio")
async def cmd_cardapio(ctx):
    await ctx.send("🍽️ Escolha uma categoria:", view=CategoriaView())


# ---------------- COMANDO !carrinho (mostra e oferece ações) ----------------
@bot.command(name="carrinho")
async def cmd_carrinho(ctx):
    uid = ctx.author.id
    cart = carrinhos.get(uid, [])
    texto = formatar_carrinho_list(cart)
    # usa view que oferece checkout/continuar/esvaziar
    await ctx.send(f"🧺 Seu carrinho:\n\n{texto}", view=CarrinhoView(uid))


# ---------------- COMANDO !checkout / !finalizar (inicia fluxo) ----------------
@bot.command(name="checkout")
async def cmd_checkout(ctx):
    uid = ctx.author.id
    cart = carrinhos.get(uid, [])
    if not cart:
        await ctx.send("Seu carrinho está vazio. Adicione itens antes de finalizar.")
        return
    checkout_flow[uid] = {"etapa": "nome", "cart": cart.copy(), "nome": "", "endereco": "", "pagamento": ""}
    await ctx.send("Iniciando finalização do pedido. Por favor, digite **seu nome completo**:")

@bot.command(name="finalizar")
async def cmd_finalizar(ctx):
    # alias para checkout
    await cmd_checkout(ctx)


@bot.command(name="cancelar")
async def cmd_cancelar(ctx):
    uid = ctx.author.id
    if uid in checkout_flow:
        checkout_flow.pop(uid, None)
        await ctx.send("Fluxo de checkout cancelado.")
    else:
        await ctx.send("Você não está em um fluxo de checkout.")


# ---------------- START ----------------
@bot.event
async def on_ready():
    print(f"Bot iniciado: {bot.user} (ID: {bot.user.id})")

bot.run(TOKEN)
