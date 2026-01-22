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

# --- MOTOR DE PROCESSAMENTO ATUALIZADO (BORDA REFORÇADA) ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    if tipo_contorno == "Sem Contorno":
        return img, img.split()[3]

    # Ajuste de distância: Adicionada opção de 2mm e reforço para 0mm
    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 8 # Aumentado para garantir que a linha apareça por fora
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    respiro = p_px_s * 2 + 120
    
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    mask_f = mask.resize((img.width + distancia_px*2 + 180, img.height + distancia_px*2 + 180), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)

    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Camada 1: Sangria Branca
    if tipo_contorno == "Com Sangria":
        fundo_branco = Image.new("RGBA", mask_f.size, (255, 255, 255, 255))
        final_rgba.paste(fundo_branco, (0, 0), mask_f)
    
    # Camada 2: LINHA PRETA REFORÇADA (Stroke Externo mais largo)
    if linha_ativa:
        # Criamos um contorno preto que se estende para fora da máscara
        mask_linha = mask_f.filter(ImageFilter.MaxFilter(9)) # Traço bem visível
        camada_preta = Image.new("RGBA", mask_f.size, (0, 0, 0, 255))
        final_rgba.paste(camada_preta, (0, 0), mask_linha)
        
        # Limpamos o interior para a linha não cobrir a imagem
        interior = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior)
    
    # Camada 3: Imagem Original
    pos_x = (mask_f.width - img.width) // 2
    pos_y = (mask_f.height - img.height) // 2
    
    img_camada = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_camada.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_camada)

    final_bbox = final_rgba.getbbox()
    return final_rgba.crop(final_bbox), mask_f.crop(final_bbox)

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
st.title("✂️ ScanNCut Pro - Opção 2mm e Linha Forte")

with st.sidebar:
    st.header("1. Configurações")
    suavidade = st.slider("Arredondamento", 0, 30, 10)
    margem = st.slider("Margem Papel (cm)", 0.5, 2.0, 1.0)
    
    st.divider()
    st.header("2. Sincronizar Tudo")
    b_size = st.number_input("Tamanho (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade", 1, 100, 10)
    if st.button("Aplicar a Todos"):
        for i in range(100):
            if f"m{i}" in st.session_state: st.session_state[f"m{i}"] = b_size
            if f"q{i}" in st.session_state: st.session_state[f"q{i}"] = b_qtd

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
                qtd = st.number_input(f"Qtd", 1, 100, 10, key=f"q{i}")
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                # ADICIONADA OPÇÃO 2MM
                sang = st.selectbox("Sangria", ["2mm", "3mm", "5mm", "7mm", "9mm"], index=0, key=f"s{i}")
                lin = st.checkbox("Linha Preta Visível", True, key=f"l{i}")
            confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PDF"):
        folhas = montar_projeto(confs, margem, "Modo Linhas", suavidade)
        if folhas:
            for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            out = io.BytesIO()
            folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF", out.getvalue(), "projeto_scanncut.pdf")
