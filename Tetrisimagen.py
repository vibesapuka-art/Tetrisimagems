import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io
import time

# --- CONFIGURAÇÕES TÉCNICAS (300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar):
    # Limpeza de bordas
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # FUNÇÃO DE ESPELHAMENTO (Para o verso da bandeirinha)
    if espelhar:
        img = ImageOps.mirror(img)

    # Redimensionamento preciso
    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS).convert("RGBA")

    dist_px = int(sangria_cm * CM_TO_PX)
    if dist_px > 0:
        padding = dist_px + 20
        canvas_alpha = Image.new("L", (img.width + padding*2, img.height + padding*2), 0)
        canvas_alpha.paste(img.split()[3], (padding, padding))
        mask = canvas_alpha.filter(ImageFilter.MaxFilter(tornar_impar(dist_px)))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img.split()[3].point(lambda p: 255 if p > 128 else 0)

    peca_final = Image.new("RGBA", mask.size if dist_px > 0 else img.size, (0, 0, 0, 0))
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3)) if dist_px > 0 else mask
        peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
    
    peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    off_x = (peca_final.width - img.width) // 2 if dist_px > 0 else 0
    off_y = (peca_final.height - img.height) // 2 if dist_px > 0 else 0
    peca_final.paste(img, (off_x, off_y), img)
    
    return peca_final.crop(peca_final.getbbox())

def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    folhas = []
    lista_pendente = pecas.copy()
    while lista_pendente:
        folha = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x, y, h_linha = m_px, y + h_linha + 10, 0
            if y + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (x, y), p)
                x, h_linha = x + pw + 10, max(h_linha, ph)
                inseridos.append(i)
            else: break
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Editor", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Configurações")
    margem = st.slider("Margem da Folha (cm)", 0.3, 1.5, 0.5)
    suave = st.slider("Suavização", 0, 30, 15)
    if st.button("🗑️ LIMPAR TUDO"):
        st.session_state.galeria = []
        st.rerun()

u = st.file_uploader("Subir PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        # ID único baseado no tempo para permitir duplicatas
        id_item = f"{f.name}_{time.time()}_{len(st.session_state.galeria)}"
        st.session_state.galeria.append({
            "id": id_item,
            "name": f.name, 
            "img": Image.open(f).copy()
        })
    st.rerun()

if st.session_state.galeria:
    pecas_preparadas = []
    indices_remover = []

    for i, item in enumerate(st.session_state.galeria):
        iid = item['id']
        with st.expander(f"Configurar: {item['name']}", expanded=True):
            c1, c2, c3, c4 = st.columns([0.8, 2, 2, 0.5])
            with c1:
                st.image(item['img'], width=80)
                # Checkbox de Espelhamento
                esp = st.checkbox("Espelhar", key=f"esp_{iid}")
            with c2:
                t = st.number_input("Tamanho (cm)", 1.0, 25.0, value=4.0, key=f"m{iid}")
                q = st.number_input("Quantidade (un)", 1, 500, value=10, key=f"q{iid}")
            with c3:
                s = st.slider("Sangria (cm)", 0.0, 1.0, 0.25, step=0.05, key=f"s{iid}")
                l = st.checkbox("Linha de Corte", True, key=f"l{iid}")
            with c4:
                if st.button("❌", key=f"del_{iid}"): indices_remover.append(i)

            p_processada = gerar_contorno_individual(item['img'], t, s, l, suave, esp)
            for _ in range(int(q)):
                pecas_preparadas.append(p_processada)

    if indices_remover:
        for idx in sorted(indices_remover, reverse=True): st.session_state.galeria.pop(idx)
        st.rerun()

    if st.button(f"🚀 GERAR PDF ({len(pecas_preparadas)} figuras)", use_container_width=True):
        folhas = montar_folhas(pecas_preparadas, margem)
        if folhas:
            for idx, f in enumerate(folhas):
                st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            
            pdf_bytes = io.BytesIO()
            folhas[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.download_button("📥 BAIXAR PDF FINAL", pdf_bytes.getvalue(), "Bazzott_Bandeirinhas.pdf", use_container_width=True)
