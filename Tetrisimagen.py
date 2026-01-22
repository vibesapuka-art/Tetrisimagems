import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO PARA GERAR TEXTO COMO IMAGEM ---
def texto_para_imagem(texto, cor_hex):
    # Criamos uma tela larga para o texto com alta resolução
    img_texto = Image.new("RGBA", (2500, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_texto)
    
    try:
        # Usa a fonte padrão (em ambiente local, você pode apontar para um .ttf)
        font = ImageFont.load_default() 
    except:
        font = ImageFont.load_default()

    draw.text((20, 20), texto, fill=cor_hex, font=font)
    
    bbox = img_texto.getbbox()
    if bbox:
        img_texto = img_texto.crop(bbox)
        # Aumentamos o texto para que ele tenha a mesma densidade de pixels que um PNG
        img_texto = img_texto.resize((img_texto.width * 6, img_texto.height * 6), Image.LANCZOS)
    
    return img_texto

# --- MOTOR DE PROCESSAMENTO (O CORAÇÃO DO APP) ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade, espessura_linha_mm):
    # Limpa bordas vazias do PNG
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    # Cálculo da Sangria (Distância da borda branca)
    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
    # Cálculo da Linha Preta (Stroke)
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    
    # Reduzimos a escala temporariamente para suavizar as curvas (Anti-aliasing)
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    l_px_s = int(linha_px * fator)
    
    respiro = (p_px_s + l_px_s) * 2 + 150
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    # 1. Cria a máscara da Sangria (Branca)
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # 2. Cria a máscara da Linha Preta (Stroke Externo)
    mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px_s if l_px_s > 0 else 1)))

    # 3. Volta ao tamanho original (300 DPI)
    mask_f = mask.resize((img.width + distancia_px*2 + 200, img.height + distancia_px*2 + 200), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)
    mask_l_f = mask_linha.resize(mask_f.size, Image.LANCZOS)
    mask_l_f = mask_l_f.point(lambda p: 255 if p > 128 else 0)

    # 4. Montagem das Camadas (Composto Final)
    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Camada da Sangria (Fundo Branco)
    if tipo_contorno == "Com Sangria":
        final_rgba.paste((255, 255, 255, 255), (0, 0), mask_f)
    
    # Camada da Linha Preta
    if linha_ativa:
        final_rgba.paste((0, 0, 0, 255), (0, 0), mask_l_f)
        # Limpa o interior para a linha preta não vazar para dentro do desenho
        interior_vazio = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior_vazio)
    
    # Coloca a imagem original no topo de tudo
    pos_x = (mask_f.width - img.width) // 2
    pos_y = (mask_f.height - img.height) // 2
    img_top = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_top.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_top)

    return final_rgba.crop(final_rgba.getbbox()), mask_f.crop(final_rgba.getbbox())

# --- MONTAGEM DA FOLHA A4 ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.20 * CM_TO_PX) # Espaço entre adesivos
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        # Redimensiona mantendo a proporção
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        pv, _ = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha)
        for _ in range(item['quantidade']): 
            all_pieces.append(pv)

    folhas = []
    pecas_restantes = all_pieces.copy()
    while pecas_restantes and len(folhas) < 30:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        cx, cy, lh = m_px, m_px, 0
        ainda_cabem = []
        for p in pecas_restantes:
            iw, ih = p.size
            if cx + iw > A4_WIDTH - m_px:
                cx, cy, lh = m_px, cy + lh + e_px, 0
            if cy + ih <= A4_HEIGHT - m_px:
                temp_canvas.paste(p, (cx, cy), p)
                cx, lh = cx + iw + e_px, max(lh, ih)
            else: ainda_cabem.append(p)

        if temp_canvas.getbbox():
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            final_page.paste(temp_canvas, (0, 0), temp_canvas)
            folhas.append(final_page)
        pecas_restantes = ainda_cabem
    return folhas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="ScanNCut Studio Pro v3", layout="wide")

if 'lista_imgs' not in st.session_state:
    st.session_state.lista_imgs = []

st.title("✂️ ScanNCut Pro - App Completo")

with st.sidebar:
    st.header("🔡 Criar Texto")
    txt_input = st.text_input("Nome ou Frase")
    cor_txt = st.color_picker("Cor do Texto", "#000000")
    if st.button("➕ Adicionar Texto"):
        if txt_input:
            st.session_state.lista_imgs.append({"img": texto_para_imagem(txt_input, cor_txt), "name": f"Texto: {txt_input}"})

    st.divider()
    st.header("⚙️ Ajustes de Corte")
    # CONFIGURAÇÃO PADRÃO CONFORME PEDIDO
    espessura_linha = st.slider("Espessura da Linha (mm)", 0.1, 10.0, 0.3, step=0.1)
    suavidade = st.slider("Arredondamento (30 é o máx)", 0, 30, 30)
    margem = st.slider("Margem Papel (cm)", 0.5, 2.5, 1.0)

    if st.button("🗑️ Limpar Tudo"):
        st.session_state.lista_imgs = []
        st.rerun()

# Upload de imagens
u = st.file_uploader("Upload de PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if not any(d.get('name') == f.name for d in st.session_state.lista_imgs):
            st.session_state.lista_imgs.append({"img": Image.open(f), "name": f.name})

# Área de Edição e Pré-visualização
if st.session_state.lista_imgs:
    confs = []
    st.subheader("Configurar Itens")
    for i, item in enumerate(st.session_state.lista_imgs):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=100)
            with c2:
                med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                # PADRÃO 1 UNIDADE
                qtd = st.number_input(f"Quantidade", 1, 100, 1, key=f"q{i}")
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                sang = st.selectbox("Sangria", ["2mm", "3mm", "5mm", "7mm", "9mm"], index=0, key=f"s{i}")
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            confs.append({'img': item['img'], 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PDF FINAL"):
        with st.spinner("A processar as imagens e a organizar o layout..."):
            folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
            if folhas:
                for idx, f in enumerate(folhas): 
                    st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                
                pdf_output = io.BytesIO()
                folhas[0].save(pdf_output, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF para ScanNCut", pdf_output.getvalue(), "scanncut_projeto.pdf", use_container_width=True)
