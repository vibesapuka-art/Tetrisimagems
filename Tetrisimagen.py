import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import io
import time
import hashlib

# --- CONFIGURAÇÕES TÉCNICAS (300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar):
    # Limpeza e Espelhamento
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    if espelhar:
        img = ImageOps.mirror(img)

    # Redimensionamento
    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    prop = min(alvo_px / w, alvo_px / h)
    img = img.resize((int(w * prop), int(h * prop)), Image.LANCZOS)

    # Sangria e Máscara
    dist_px = int(sangria_cm * CM_TO_PX)
    if dist_px > 0:
        pad = dist_px + 10
        mask_canvas = Image.new("L", (img.width + pad*2, img.height + pad*2), 0)
        mask_canvas.paste(img.split()[3], (pad, pad))
        mask = mask_canvas.filter(ImageFilter.MaxFilter(int(dist_px) | 1))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/5))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img.split()[3]

    final = Image.new("RGBA", mask.size if dist_px > 0 else img.size, (0,0,0,0))
    if linha_ativa:
        l_mask = mask.filter(ImageFilter.MaxFilter(3))
        final.paste((0,0,0,255), (0,0), l_mask)
    
    final.paste((255,255,255,255), (0,0), mask)
    ox = (final.width - img.width)//2 if dist_px > 0 else 0
    oy = (final.height - img.height)//2 if dist_px > 0 else 0
    final.paste(img, (ox, oy), img)
    
    return final.crop(final.getbbox())

def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    folhas = []
    pendentes = pecas.copy()
    while pendentes:
        f = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, lh = m_px, m_px, 0
        idx_rem = []
        for i, p in enumerate(pendentes):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x, y, lh = m_px, y + lh + 10, 0
            if y + ph <= A4_HEIGHT - m_px:
                f.paste(p, (x, y), p)
                x, lh = x + pw + 10, max(lh, ph)
                idx_rem.append(i)
            else: break
        if not idx_rem: break
        for idx in sorted(idx_rem, reverse=True): pendentes.pop(idx)
        b = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        b.paste(f, (0, 0), f)
        folhas.append(b)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Studio FIX", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.title("🛠️ Painel")
    # Correção do erro de ID duplicado usando uma chave única (key)
    if st.button("🗑️ LIMPAR TUDO", key="btn_limpar_global"):
        st.session_state.galeria = []
        st.rerun()
    
    margem = st.slider("Margem (cm)", 0.3, 1.5, 0.5)
    suave = st.slider("Suavização", 0, 30, 10)

u = st.file_uploader("Suba seus PNGs aqui", type="png", accept_multiple_files=True)
if u:
    for f in u:
        # Gera ID único baseado no nome e timestamp para evitar conflitos
        uid = hashlib.md5(f"{f.name}{time.time()}".encode()).hexdigest()[:8]
        st.session_state.galeria.append({"id": uid, "name": f.name, "img": Image.open(f).copy()})
    st.rerun()

if st.session_state.galeria:
    preparadas = []
    remover = []

    for i, item in enumerate(st.session_state.galeria):
        fid = item['id']
        with st.container(border=True):
            col_img, col_cfg, col_del = st.columns([1, 4, 0.5])
            with col_img:
                st.image(item['img'], width=80)
                esp = st.checkbox("Espelhar", key=f"esp_{fid}")
            with col_cfg:
                c1, c2 = st.columns(2)
                t = c1.number_input("Tam (cm)", 1.0, 25.0, 4.0, key=f"t_{fid}")
                q = c1.number_input("Qtd", 1, 500, 10, key=f"q_{fid}")
                s = c2.slider("Sangria", 0.0, 1.0, 0.25, key=f"s_{fid}")
                l = c2.checkbox("Corte", True, key=f"l_{fid}")
            with col_del:
                if st.button("❌", key=f"del_{fid}"): remover.append(i)

            res = gerar_contorno_individual(item['img'], t, s, l, suave, esp)
            for _ in range(int(q)): preparadas.append(res)

    if remover:
        for idx in sorted(remover, reverse=True): st.session_state.galeria.pop(idx)
        st.rerun()

    if preparadas and st.button(f"🚀 GERAR PDF ({len(preparadas)} itens)", use_container_width=True, key="btn_gerar_final"):
        with st.spinner("Processando..."):
            folhas = montar_folhas(preparadas, margem)
            for idx, folha in enumerate(folhas):
                st.image(folha, caption=f"Página {idx+1}", use_container_width=True)
            
            buf = io.BytesIO()
            folhas[0].save(buf, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 BAIXAR PDF", buf.getvalue(), "projeto.pdf", use_container_width=True, key="btn_download")
