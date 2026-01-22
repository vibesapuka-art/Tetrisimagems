import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw
import io
import random

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO (IMAGEM NA FRENTE DA SANGRIA) ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)

    if tipo_contorno == "Sem Contorno":
        alpha = img.split()[3].point(lambda p: 255 if p > 100 else 0)
        return img, alpha

    # Lógica da espessura: 1mm tagredonda = 2.50mm total
    if tipo_contorno == "Corte no Desenho (0mm)":
        p_px = 6
    elif sangria_escolhida == "1mm tagredonda":
        p_px = int(0.25 * CM_TO_PX)
    else:
        num_mm = float(sangria_escolhida.split('mm')[0])
        p_px = int((num_mm / 10) * CM_TO_PX)
    
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(p_px * fator)
    respiro = p_px_s * 2 + 120
    
    img_exp = Image.new("RGBA", (img_s.width + respiro, img_s.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img_s, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    mask = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    mask_f = mask.resize((img.width + p_px*2 + 150, img.height + p_px*2 + 150), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)

    # MONTAGEM DAS CAMADAS (Imagem na frente)
    nova_img = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # 1. Coloca a Sangria (Branco) por baixo
    nova_img.paste((255,255,255,255), (0,0), mask_f)
    
    # 2. Coloca a Imagem Original por cima da sangria
    pos_x = (nova_img.width - img.width) // 2
    pos_y = (nova_img.height - img.height) // 2
    nova_img.paste(img, (pos_x, pos_y), img)

    # 3. Coloca a Linha de Corte por cima de tudo
    if linha_ativa:
        overlay_linha = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
        borda_guia = mask_f.filter(ImageFilter.MaxFilter(5))
        overlay_linha.paste((0,0,0,255), (0,0), borda_guia)
        nova_img = Image.alpha_composite(nova_img, overlay_linha)
    
    final_bbox = nova_img.getbbox()
    return nova_img.crop(final_bbox), mask_f.crop(final_bbox)

# --- MONTAGEM DO PROJETO ---
def montar_projeto(lista_config, margem_cm, modo_layout, nivel_suavidade):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX)
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        pv, pm = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade)
        for _ in range(item['quantidade']): 
            all_pieces.append({'img': pv, 'mask': pm})

    folhas = []
    pecas_restantes = all_pieces.copy()
    while pecas_restantes and len(folhas) < 20:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        temp_mask = Image.new("L", (A4_WIDTH, A4_HEIGHT), 0)
        ainda_cabem = []
        
        if modo_layout == "Modo Linhas":
            cx, cy, lh = m_px, m_px, 0
            for p in pecas_restantes:
                iw, ih = p['img'].size
                if cx + iw > A4_WIDTH - m_px:
                    cx, cy, lh = m_px, cy + lh + e_px, 0
                if cy + ih <= A4_HEIGHT - m_px:
                    temp_canvas.paste(p['img'], (cx, cy), p['img'])
                    temp_mask.paste(p['mask'], (cx, cy), p['mask'])
                    cx, lh = cx + iw + e_px, max(lh, ih)
                else: ainda_cabem.append(p)
        else: # MODO TETRIS
            pecas_restantes.sort(key=lambda x: x['img'].size[0]*x['img'].size[1], reverse=True)
            for p in pecas_restantes:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(250):
                    tx, ty = random.randint(m_px, A4_WIDTH-iw-m_px), random.randint(m_px, A4_HEIGHT-ih-m_px)
                    if not ImageChops.multiply(temp_mask.crop((tx, ty, tx+iw, ty+ih)), p['mask']).getbbox():
                        temp_canvas.paste(p['img'], (tx, ty), p['img'])
                        temp_mask.paste(p['mask'], (tx, ty), p['mask'])
                        encaixou = True; break
                if not encaixou: ainda_cabem.append(p)

        bbox = temp_canvas.getbbox()
        if bbox:
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            l_r, a_r = bbox[2]-bbox[0], bbox[3]-bbox[1]
            off_x, off_y = (A4_WIDTH-l_r)//2 - bbox[0], (A4_HEIGHT-a_r)//2 - bbox[1]
            final_page.paste(temp_canvas, (off_x, off_y), temp_canvas)
            folhas.append(final_page)
        pecas_restantes = ainda_cabem
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")
st.title("✂️ ScanNCut Pro - Versão Final")

with st.sidebar:
    st.header("Configurações Gerais")
    suavidade = st.slider("Arredondamento", 0, 30, 15)
    modo_layout = st.radio("Layout", ["Modo Linhas", "Modo Tetris"])
    margem = st.slider("Margem (cm)", 0.3, 2.0, 1.0)
    
    st.divider()
    st.header("🪄 Sincronizar Tudo")
    bulk_size = st.number_input("Tamanho Base (cm)", 1.0, 25.0, 5.0)
    bulk_qtd = st.number_input("Qtd Base", 1, 100, 10)
    if st.button("Aplicar a Todos os Itens"):
        for i in range(100):
            if f"m{i}" in st.session_state: st.session_state[f"m{i}"] = bulk_size
            if f"q{i}" in st.session_state: st.session_state[f"q{i}"] = bulk_qtd

u = st.file_uploader("Upload PNG", type="png", accept_multiple_files=True)
if u:
    confs = []
    for i, f in enumerate(u):
        with st.expander(f"⚙️ {f.name}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            img = Image.open(f)
            with c1: st.image(img, width=80)
            with c2:
                med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                qtd = st.number_input(f"Quantidade", 1, 100, 10, key=f"q{i}")
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)", "Sem Contorno"], key=f"t{i}")
                sang = st.selectbox("Sangria", ["1mm tagredonda", "3mm", "5mm", "7mm", "9mm"], index=0, key=f"s{i}")
                lin = st.checkbox("Linha Preta Visível", True, key=f"l{i}")
            confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PROJETO CENTRALIZADO"):
        folhas = montar_projeto(confs, margem, modo_layout, suavidade)
        if folhas:
            for idx, f in enumerate(folhas): st.image(f, caption=f"Pág {idx+1}", use_container_width=True)
            out = io.BytesIO()
            folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF", out.getvalue(), "projeto_scanncut.pdf", use_container_width=True)
