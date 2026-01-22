import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io
import random

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- FUNÇÃO DE CONTORNO ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade):
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)

    if tipo_contorno == "Sem Contorno":
        return img, img.split()[3].point(lambda p: 255 if p > 100 else 0)

    val_cm = 0.05 if tipo_contorno == "Corte no Desenho (0mm)" else float(sangria_escolhida.replace('mm', '')) / 10
    p_px = int(val_cm * CM_TO_PX)
    
    fator = 0.5
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(p_px * fator)
    respiro = p_px_s * 2 + 60
    
    img_exp = Image.new("RGBA", (img_s.width + respiro, img_s.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img_s, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    mask = alpha.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    mask_f = mask.resize((img.width + p_px*2 + 80, img.height + p_px*2 + 80), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    if linha_ativa:
        borda_guia = mask_f.filter(ImageFilter.MaxFilter(5))
        nova_img.paste((0,0,0,255), (0,0), borda_guia)
    
    nova_img.paste((255,255,255,255), (0,0), mask_f)
    pos_x = (nova_img.width - img.width) // 2
    pos_y = (nova_img.height - img.height) // 2
    nova_img.paste(img, (pos_x, pos_y), img)
    
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
        else: # TETRIS
            pecas_restantes.sort(key=lambda x: x['img'].size[0]*x['img'].size[1], reverse=True)
            for p in pecas_restantes:
                iw, ih = p['img'].size
                encaixou = False
                for _ in range(200):
                    tx, ty = random.randint(m_px, A4_WIDTH-iw-m_px), random.randint(m_px, A4_HEIGHT-ih-m_px)
                    if not ImageChops.multiply(temp_mask.crop((tx, ty, tx+iw, ty+ih)), p['mask']).getbbox():
                        temp_canvas.paste(p['img'], (tx, ty), p['img'])
                        temp_mask.paste(p['mask'], (tx, ty), p['mask'])
                        encaixou = True; break
                if not encaixou: ainda_cabem.append(p)

        bbox = temp_canvas.getbbox()
        if bbox:
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            l_real, a_real = bbox[2] - bbox[0], bbox[3] - bbox[1]
            off_x, off_y = (A4_WIDTH - l_real) // 2 - bbox[0], (A4_HEIGHT - a_real) // 2 - bbox[1]
            final_page.paste(temp_canvas, (off_x, off_y), temp_canvas)
            folhas.append(final_page)
        pecas_restantes = ainda_cabem
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")

# Inicialização da galeria na sessão para evitar perda de dados
if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("1. Configurações Globais")
    suavidade = st.slider("Arredondamento (Suavizar)", 0, 30, 15)
    modo_layout = st.radio("Organização", ["Modo Linhas", "Modo Tetris"])
    margem = st.slider("Margem Papel (cm)", 0.3, 2.0, 1.0)
    
    st.divider()
    st.header("2. Sincronização em Massa")
    b_size = st.number_input("Tamanho Padrão (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade Padrão", 1, 100, 10)
    lista_mm = ["3mm", "5mm", "7mm", "9mm"]
    b_sangria = st.selectbox("Sangria Padrão (mm)", lista_mm, index=0)
    
    if st.button("🪄 Sincronizar Tudo"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_sangria
        st.rerun()

u = st.file_uploader("Suba seus arquivos PNG", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    confs = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"⚙️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                med = st.number_input(f"Medida (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 5.0))
                qtd = st.number_input(f"Qtd", 1, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 10))
            with c3:
                tipo = st.selectbox("Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                # Recupera o index correto da sangria sincronizada
                val_s = st.session_state.get(f"s{i}", "3mm")
                idx_s = lista_mm.index(val_s) if val_s in lista_mm else 0
                sang = st.selectbox("mm", lista_mm, key=f"s{i}", index=idx_s)
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            confs.append({'img': item['img'], 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PROJETO CENTRALIZADO", use_container_width=True):
        folhas = montar_projeto(confs, margem, modo_layout, suavidade)
        if folhas:
            for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            out = io.BytesIO()
            folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF Final", out.getvalue(), "projeto_scanncut.pdf", use_container_width=True)
        
