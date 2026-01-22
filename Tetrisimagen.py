import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw, ImageFont
import io
import random
import time

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO DE CONTORNO COM ALTA SUAVIZAÇÃO E SANGRIA +1MM ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    # Foca na área visível do desenho (remove transparências inúteis)
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)

    # Define a espessura em pixels
    if tipo_contorno == "Sangria de Segurança (+1mm)":
        p_px = int(0.1 * CM_TO_PX) # +1mm para fora
    elif tipo_contorno == "Corte no Desenho (0mm)":
        p_px = 6
    elif tipo_contorno == "Sem Contorno":
        return img, img.split()[3].point(lambda p: 255 if p > 100 else 0)
    else:
        valor_cm = float(sangria_escolhida.replace('mm', '')) / 10
        p_px = int(valor_cm * CM_TO_PX)
    
    # Processamento em escala reduzida para suavização rápida e sem degraus
    fator = 0.5
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(p_px * fator)
    respiro = p_px_s * 2 + 100
    
    img_exp = Image.new("RGBA", (img_s.width + respiro, img_s.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img_s, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Gera a máscara expandida (Sangria externa)
    mask = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    # Suavização Crítica (Arredonda as quinas dos píxeis)
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Redimensiona para tamanho original com alta qualidade
    mask_f = mask.resize((img.width + p_px*2 + 120, img.height + p_px*2 + 120), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Linha preta de corte (guia para o sensor da ScanNCut)
    if linha_ativa:
        borda_guia = mask_f.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda_guia)
    
    # Preenchimento branco (Sangria) e centralização da imagem original
    nova_img.paste((255,255,255,255), (0,0), mask_f)
    pos_x = (nova_img.width - img.width) // 2
    pos_y = (nova_img.height - img.height) // 2
    nova_img.paste(img, (pos_x, pos_y), img)
    
    final_bbox = nova_img.getbbox()
    return nova_img.crop(final_bbox), mask_f.crop(final_bbox)

# --- LÓGICA DE MONTAGEM COM CENTRALIZAÇÃO AUTOMÁTICA ---
def montar_projeto(lista_config, margem_cm, modo_layout, nivel_suavidade):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX)
    
    progresso = st.progress(0)
    status_text = st.empty()
    all_pieces = []
    
    status_text.text("🎨 A processar suavização e contornos...")
    for i, item in enumerate(lista_config):
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        # Redimensionamento proporcional
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        pv, pm = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade)
        for _ in range(item['quantidade']): 
            all_pieces.append({'img': pv, 'mask': pm})
        progresso.progress(int((i+1)/len(lista_config)*30))

    folhas = []
    pecas_restantes = all_pieces.copy()

    status_text.text("📏 A organizar peças e a centralizar folha...")
    while pecas_restantes and len(folhas) < 20:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        temp_mask = Image.new("L", (A4_WIDTH, A4_HEIGHT), 0)
        ainda_cabem = []
        
        if modo_layout == "Modo Linhas":
            cx, cy, lh = m_px, m_px, 0
            for p in pecas_restantes:
                iw, ih = p['img'].size
                if cx + iw > A4_WIDTH - m_px:
                    cx = m_px
                    cy += lh + e_px
                    lh = 0
                if cy + ih <= A4_HEIGHT - m_px:
                    temp_canvas.paste(p['img'], (cx, cy), p['img'])
                    temp_mask.paste(p['mask'], (cx, cy), p['mask'])
                    cx += iw + e_px
                    lh = max(lh, ih)
                else: ainda_cabem.append(p)
        else: # MODO TETRIS
            pecas_restantes.sort(key=lambda x: x['img'].size[0]*x['img'].size[1], reverse=True)
            for p in pecas_restantes:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(300):
                    tx, ty = random.randint(m_px, A4_WIDTH-iw-m_px), random.randint(m_px, A4_HEIGHT-ih-m_px)
                    if not ImageChops.multiply(temp_mask.crop((tx, ty, tx+iw, ty+ih)), p['mask']).getbbox():
                        temp_canvas.paste(p['img'], (tx, ty), p['img'])
                        temp_mask.paste(p['mask'], (tx, ty), p['mask'])
                        encaixou = True; break
                if not encaixou: ainda_cabem.append(p)

        # CENTRALIZAÇÃO REAL NA FOLHA
        bbox_conteudo = temp_canvas.getbbox()
        if bbox_conteudo:
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            l_real = bbox_conteudo[2] - bbox_conteudo[0]
            a_real = bbox_conteudo[3] - bbox_conteudo[1]
            off_x = (A4_WIDTH - l_real) // 2 - bbox_conteudo[0]
            off_y = (A4_HEIGHT - a_real) // 2 - bbox_conteudo[1]
            final_page.paste(temp_canvas, (off_x, off_y), temp_canvas)
            folhas.append(final_page)
        
        pecas_restantes = ainda_cabem
        progresso.progress(min(95, 30 + (len(folhas)*10)))

    status_text.empty()
    progresso.empty()
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")
tab1, tab2 = st.tabs(["📋 Montagem Automática", "🎂 Editor de Topo & Nomes"])

with tab1:
    with st.sidebar:
        st.header("Configurações de Corte")
        suavidade = st.slider("Arredondamento (Suavizar)", 0, 30, 15, help="Elimina o efeito 'escadinha' (quadrados).")
        modo_layout = st.radio("Organização", ["Modo Linhas", "Modo Tetris"])
        margem = st.slider("Margem Papel (cm)", 0.3, 2.0, 1.0)
        
        st.divider()
        st.header("Sincronizar Tudo")
        b_size = st.number_input("Tamanho Geral (cm)", 1.0, 25.0, 5.0)
        b_qtd = st.number_input("Qtd Geral", 1, 100, 10)
        if st.button("🪄 Aplicar em Todos"):
            for i in range(50):
                if f"m{i}" in st.session_state: st.session_state[f"m{i}"] = b_size
                if f"q{i}" in st.session_state: st.session_state[f"q{i}"] = b_qtd

    u = st.file_uploader("Suba as suas imagens PNG", type="png", accept_multiple_files=True)
    if u:
        confs = []
        for i, f in enumerate(u):
            with st.expander(f"⚙️ Configurar: {f.name}", expanded=False):
                c1, c2, c3 = st.columns([1, 2, 2])
                img = Image.open(f)
                with c1: st.image(img, width=80)
                with c2:
                    med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                    qtd = st.number_input(f"Qtd", 1, 100, 10, key=f"q{i}")
                with c3:
                    tipo = st.selectbox("Tipo de Corte", ["Com Sangria", "Corte no Desenho (0mm)", "Sangria de Segurança (+1mm)", "Sem Contorno"], key=f"t{i}")
                    sang = st.selectbox("Sangria (mm)", ["3mm", "5mm", "7mm", "9mm"], key=f"s{i}")
                    lin = st.checkbox("Linha Preta de Corte", True, key=f"l{i}")
                confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

        if st.button("🚀 GERAR PROJETO FINAL CENTRALIZADO"):
            folhas = montar_projeto(confs, margem, modo_layout, suavidade)
            if folhas:
                for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
                out = io.BytesIO()
                folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF para ScanNCut", out.getvalue(), "projeto_scanncut.pdf", use_container_width=True)

with tab2:
    st.subheader("🎂 Editor de Topos")
    col_ed, col_pre = st.columns([1, 1])
    with col_ed:
        texto = st.text_input("Nome/Idade", "Parabéns")
        cor_letra = st.color_picker("Cor do Texto", "#FF007F")
        tipo_c = st.selectbox("Estilo", ["Com Sangria", "Sangria de Segurança (+1mm)"])
        st.info("💡 Brevemente: Seleção de fontes personalizadas (.ttf).")
    with col_pre:
        # Gerador básico de prévia para o topo
        img_t = Image.new("RGBA", (1000, 300), (0,0,0,0))
        d = ImageDraw.Draw(img_t)
        d.text((50, 50), texto, fill=cor_letra)
        peca_t, _ = gerar_contorno_individual(img_t, tipo_c, "5mm", True, 15)
        st.image(peca_t, caption="Prévia do Nome")
