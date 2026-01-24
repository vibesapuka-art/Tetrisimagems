import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS RÍGIDAS (A4 300 DPI) ---
DPI = 300
CM_TO_PX = 118.1102
A4_WIDTH_PX = 2480  # 21cm exatos
A4_HEIGHT_PX = 3508 # 29.7cm exatos

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PRECISÃO ---
def gerar_peca_final(img, medida_cm, sangria_cm, linha_ativa, suavidade, espessura_mm, espelhar=False):
    img = img.convert("RGBA")
    bbox = img.getbbox() # Pega apenas a área com desenho
    if not bbox: return None
    img_real = img.crop(bbox)
    
    if espelhar:
        img_real = ImageOps.mirror(img_real)

    # AJUSTE DE TAMANHO: O maior lado terá a medida_cm escolhida
    w, h = img_real.size
    alvo_px = medida_cm * CM_TO_PX
    fator = alvo_px / max(w, h)
    
    img_redim = img_real.resize((int(w * fator), int(h * fator)), Image.LANCZOS)

    # ADIÇÃO DE SANGRIA (EXTERNA)
    s_px = int(sangria_cm * CM_TO_PX)
    l_px = int((espessura_mm / 10) * CM_TO_PX)
    
    padding = s_px + l_px + 10
    canvas = Image.new("L", (img_redim.width + padding*2, img_redim.height + padding*2), 0)
    canvas.paste(img_redim.split()[3], (padding, padding))
    
    mask = canvas.filter(ImageFilter.MaxFilter(tornar_impar(s_px * 2 if s_px > 0 else 1)))
    if suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=suavidade/2))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    peca = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    peca.paste((255, 255, 255, 255), (0, 0), mask)
    
    if linha_ativa:
        m_lin = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px if l_px > 0 else 1)))
        peca.paste((0, 0, 0, 255), (0, 0), m_lin)
        int_limpo = mask.filter(ImageFilter.MinFilter(3))
        peca.paste((0,0,0,0), (0,0), int_limpo)

    peca.paste(img_redim, ((peca.width - img_redim.width)//2, (peca.height - img_redim.height)//2), img_redim)
    return peca.crop(peca.getbbox())

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit - Precisão Real")

if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes Globais")
    l_w = st.slider("Linha (mm)", 0.1, 3.0, 0.3)
    suave = st.slider("Suavização", 0, 30, 10)
    marg_f = st.slider("Margem Papel (cm)", 0.3, 2.0, 0.5)
    
    st.divider()
    m_tam = st.number_input("Tamanho do Desenho (cm)", 1.0, 25.0, 4.0)
    m_qtd = st.number_input("Quantidade Total", 1, 100, 24)
    m_sang = st.slider("Sangria (cm)", 0.0, 2.0, 0.1)
    
    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = m_tam
            st.session_state[f"q{i}"] = m_qtd
            st.session_state[f"s{i}"] = m_sang
        st.rerun()

u = st.file_uploader("Upload PNG", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    pecas_para_pdf = []
    # Mostra a galeria
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                t = st.number_input("Tamanho (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                q = st.number_input("Qtd Normal", 0, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 24))
            with c3:
                s = st.slider("Sangria (cm)", 0.0, 2.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.1))
                qe = st.number_input("Qtd Espelho", 0, 100, key=f"qe{i}", value=0)
                lin = st.checkbox("Linha", True, key=f"l{i}")
            
            # Gera as peças para o PDF
            p_n = gerar_peca_final(item['img'], t, s, lin, suave, l_w, False)
            p_e = gerar_peca_final(item['img'], t, s, lin, suave, l_w, True)
            if p_n:
                for _ in range(q): pecas_para_pdf.append(p_n)
            if p_e:
                for _ in range(qe): pecas_para_pdf.append(p_e)

    if st.button("🚀 GERAR PDF", use_container_width=True):
        folhas = []
        fila = pecas_para_pdf.copy()
        while fila:
            f = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255, 255, 255))
            x, y, lh, m_px = int(marg_f*CM_TO_PX), int(marg_f*CM_TO_PX), 0, int(marg_f*CM_TO_PX)
            rem = []
            for idx, p in enumerate(fila):
                if x + p.width > A4_WIDTH_PX - m_px: x, y, lh = m_px, y + lh + 10, 0
                if y + p.height <= A4_HEIGHT_PX - m_px:
                    f.paste(p, (x, y), p)
                    x += p.width + 10
                    lh = max(lh, p.height)
                    rem.append(idx)
                else: break
            folhas.append(f)
            for j in sorted(rem, reverse=True): fila.pop(j)
            if not rem: break

        for folha in folhas: st.image(folha)
        out = io.BytesIO()
        folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
        st.download_button("📥 Baixar PDF", out.getvalue(), "Bazzott_Final.pdf", use_container_width=True)
