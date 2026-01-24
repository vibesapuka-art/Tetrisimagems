import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS (A4 300 DPI) ---
DPI = 300
CM_TO_PX = 118.1102
A4_WIDTH_PX = 2480  
A4_HEIGHT_PX = 3508 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PRECISÃO MILIMÉTRICA ---
def gerar_peca_final(img, medida_cm, sangria_cm, linha_ativa, suavidade, espessura_mm, espelhar=False):
    img = img.convert("RGBA")
    
    # 1. RECORTA O PNG (Tira todo o vazio original do arquivo)
    bbox_init = img.getbbox()
    if not bbox_init: return None
    img = img.crop(bbox_init)
    
    if espelhar:
        img = ImageOps.mirror(img)

    # 2. REDIMENSIONA O DESENHO (O maior lado terá a medida_cm real)
    w, h = img.size
    alvo_px = medida_cm * CM_TO_PX
    fator = alvo_px / max(w, h)
    img_redim = img.resize((int(w * fator), int(h * fator)), Image.LANCZOS)

    # 3. GERAÇÃO DA SANGRIA E LINHA
    s_px = int(sangria_cm * CM_TO_PX)
    l_px = int((espessura_mm / 10) * CM_TO_PX)
    
    # Criamos um canvas apenas o suficiente para o efeito
    pad = s_px + l_px + 5
    canvas = Image.new("L", (img_redim.width + pad*2, img_redim.height + pad*2), 0)
    canvas.paste(img_redim.split()[3], (pad, pad))
    
    # Efeito de Expansão (Sangria)
    mask = canvas.filter(ImageFilter.MaxFilter(tornar_impar(s_px * 2 if s_px > 0 else 1)))
    if suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=suavidade/2))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Montagem da Peça
    peca = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    peca.paste((255, 255, 255, 255), (0, 0), mask) # Fundo Branco
    
    if linha_ativa:
        m_lin = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px if l_px > 0 else 1)))
        peca.paste((0, 0, 0, 255), (0, 0), m_lin)
        int_limpo = mask.filter(ImageFilter.MinFilter(3))
        peca.paste((0,0,0,0), (0,0), int_limpo)

    # Cola o desenho centralizado
    peca.paste(img_redim, (pad, pad), img_redim)
    
    # 4. O PULO DO GATO: Recorta novamente para tirar a moldura invisível do processamento
    return peca.crop(peca.getbbox())

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit - Calibragem de Tamanho Real")

if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes Globais")
    l_w = st.slider("Espessura Linha (mm)", 0.1, 2.0, 0.3)
    suavidade = st.slider("Suavização Borda", 0, 20, 10)
    marg_f = st.slider("Margem da Folha (cm)", 0.3, 1.5, 0.5)
    
    st.divider()
    m_tam = st.number_input("Tamanho do Desenho (cm)", 1.0, 25.0, 4.0)
    m_qtd = st.number_input("Quantidade", 1, 100, 24)
    m_sang = st.slider("Sangria (cm)", 0.0, 1.0, 0.1)
    
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
    fila_pdf = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                t = st.number_input("Tamanho Real (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                q = st.number_input("Qtd Normal", 0, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 24))
            with c3:
                s = st.slider("Sangria (cm)", 0.0, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.1))
                qe = st.number_input("Qtd Espelho", 0, 100, key=f"qe{i}", value=0)
                lin = st.checkbox("Linha de Corte", True, key=f"l{i}")
            
            p_n = gerar_peca_final(item['img'], t, s, lin, suavidade, l_w, False)
            p_e = gerar_peca_final(item['img'], t, s, lin, suavidade, l_w, True)
            if p_n:
                for _ in range(q): fila_pdf.append(p_n)
            if p_e:
                for _ in range(qe): fila_pdf.append(p_e)

    if st.button("🚀 GERAR PDF E VISUALIZAR", use_container_width=True):
        folhas = []
        pecas = fila_pdf.copy()
        while pecas:
            folha = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255, 255, 255))
            m_px = int(marg_f * CM_TO_PX)
            x, y, lh = m_px, m_px, 0
            indices_usados = []
            for idx, p in enumerate(pecas):
                if x + p.width > A4_WIDTH_PX - m_px:
                    x = m_px
                    y += lh + 10 # Espaço de 10px entre linhas
                    lh = 0
                if y + p.height <= A4_HEIGHT_PX - m_px:
                    folha.paste(p, (x, y), p)
                    x += p.width + 10 # Espaço de 10px entre colunas
                    lh = max(lh, p.height)
                    indices_usados.append(idx)
                else: break
            folhas.append(folha)
            for j in sorted(indices_usados, reverse=True): pecas.pop(j)
            if not indices_usados: break

        for f in folhas: st.image(f)
        out = io.BytesIO()
        folhas[0].save(out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
        st.download_button("📥 Baixar PDF Corrigido", out.getvalue(), "Bazzott_RealSize.pdf", use_container_width=True)
