import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO PARA GERAR TEXTO ---
def texto_para_imagem(texto, cor_hex):
    # Criamos uma tela larga para o texto com alta resolução
    img_texto = Image.new("RGBA", (2500, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_texto)
    
    try:
        # Tenta carregar uma fonte padrão. 
        # Nota: Para fontes estilizadas, você precisaria carregar um arquivo .ttf
        font = ImageFont.load_default() 
    except:
        font = ImageFont.load_default()

    # Desenha o texto
    draw.text((20, 20), texto, fill=cor_hex, font=font)
    
    bbox = img_texto.getbbox()
    if bbox:
        img_texto = img_texto.crop(bbox)
        # Upscale para nitidez máxima no corte
        img_texto = img_texto.resize((img_texto.width * 8, img_texto.height * 8), Image.LANCZOS)
    
    return img_texto

# --- MOTOR DE PROCESSAMENTO (BORDA E CORTE) ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade, espessura_linha_mm):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    l_px_s = int(linha_px * fator)
    
    respiro = (p_px_s + l_px_s) * 2 + 150
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px_s if l_px_s > 0 else 1)))

    mask_f = mask.resize((img.width + distancia_px*2 + 200, img.height + distancia_px*2 + 200), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)
    mask_l_f = mask_linha.resize(mask_f.size, Image.LANCZOS)
    mask_l_f = mask_l_f.point(lambda p: 255 if p > 128 else 0)

    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    if tipo_contorno == "Com Sangria":
        final_rgba.paste((255, 255, 255, 255), (0, 0), mask_f)
    
    if linha_ativa:
        final_rgba.paste((0, 0, 0, 255), (0, 0), mask_l_f)
        interior_vazio = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior_vazio)
    
    pos_x = (mask_f.width - img.width) // 2
    pos_y = (mask_f.height - img.height) // 2
    img_top = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_top.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_top)

    return final_rgba.crop(final_rgba.getbbox()), mask_f.crop(final_rgba.getbbox())

# --- MONTAGEM DA FOLHA A4 ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.20 * CM_TO_PX)
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
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

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")

if 'lista_imgs' not in st.session_state:
    st.session_state.lista_imgs = []

st.title("✂️ ScanNCut Pro - v3.0")

# DEFINIÇÃO DAS ABAS PRINCIPAIS
tab_upload, tab_texto = st.tabs(["🖼️ Galeria & Upload", "🔠 Estúdio de Texto"])

with st.sidebar:
    st.header("⚙️ Configurações Globais")
    espessura_linha = st.slider("Espessura da Linha (mm)", 0.1, 5.0, 0.3, step=0.1)
    suavidade = st.slider("Arredondamento", 0, 30, 30)
    margem = st.slider("Margem Papel (cm)", 0.5, 2.5, 1.0)
    st.divider()
    if st.button("🗑️ Limpar Todo o Projeto"):
        st.session_state.lista_imgs = []
        st.rerun()

# --- ABA 1: UPLOAD E GALERIA ---
with tab_upload:
    u = st.file_uploader("Arraste seus PNGs (Imagens)", type="png", accept_multiple_files=True)
    if u:
        for f in u:
            if not any(d.get('name') == f.name for d in st.session_state.lista_imgs):
                st.session_state.lista_imgs.append({"img": Image.open(f), "name": f.name})
    
    if not st.session_state.lista_imgs:
        st.info("Sua galeria está vazia. Faça upload de imagens ou use a aba 'Estúdio de Texto'.")
    else:
        confs = []
        st.subheader("Itens na Galeria")
        for i, item in enumerate(st.session_state.lista_imgs):
            with st.expander(f"📦 {item['name']}", expanded=True):
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1: st.image(item['img'], width=120)
                with c2:
                    med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                    qtd = st.number_input(f"Quantidade", 1, 100, 1, key=f"q{i}")
                with c3:
                    tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                    sang = st.selectbox("Sangria", ["2mm", "3mm", "5mm", "7mm", "9mm"], index=0, key=f"s{i}")
                    lin = st.checkbox("Linha de Corte", True, key=f"l{i}")
                confs.append({'img': item['img'], 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

        if st.button("🚀 GERAR PDF FINAL", use_container_width=True):
            folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
            if folhas:
                for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                pdf_output = io.BytesIO()
                folhas[0].save(pdf_output, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF", pdf_output.getvalue(), "projeto.pdf", use_container_width=True)

# --- ABA 2: ESTÚDIO DE TEXTO ---
with tab_texto:
    st.subheader("🎨 Criador de Nomes e Frases")
    col_text, col_preview = st.columns([1, 1])
    
    with col_text:
        txt_input = st.text_area("Digite o texto", placeholder="Ex: Parabéns!", height=150)
        cor_txt = st.color_picker("Escolha a cor do preenchimento", "#FF0000")
        
        if st.button("➕ Adicionar à Galeria", use_container_width=True):
            if txt_input:
                img_gerada = texto_para_imagem(txt_input, cor_txt)
                st.session_state.lista_imgs.append({"img": img_gerada, "name": f"Texto: {txt_input[:10]}"})
                st.success("Adicionado com sucesso! Vá para a aba 'Galeria' para ajustar o tamanho.")
    
    with col_preview:
        st.markdown("**Pré-visualização Simples:**")
        if txt_input:
            preview = texto_para_imagem(txt_input, cor_txt)
            st.image(preview, use_container_width=True)
        else:
            st.write("Digite algo ao lado para ver aqui.")
