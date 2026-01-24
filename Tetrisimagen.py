import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS (PADRÃO A4 300 DPI) ---
# 300 DPI: 1 polegada (2.54cm) = 300px -> 1cm = 118.1102px
DPI = 300
CM_TO_PX = 118.1102
A4_WIDTH_PX = int(21.0 * CM_TO_PX)  # 2480
A4_HEIGHT_PX = int(29.7 * CM_TO_PX) # 3508

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO (TAMANHO REAL) ---
def gerar_peca_precisa(img, medida_cm, sangria_cm, linha_ativa, suavidade, espessura_mm, espelhar=False):
    # 1. Limpeza e Espelhamento
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox: img = img.crop(bbox)
    if espelhar: img = ImageOps.mirror(img)

    # 2. REDIMENSIONAMENTO DO DESENHO (O CORAÇÃO DO PROBLEMA)
    # Aqui garantimos que o DESENHO tenha a medida exata pedida
    w, h = img.size
    proporcao = (medida_cm * CM_TO_PX) / max(w, h)
    img_desenho = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    # 3. CÁLCULO DA SANGRIA (ADICIONADA POR FORA)
    sangria_px = int(sangria_cm * CM_TO_PX)
    linha_px = int((espessura_mm / 10) * CM_TO_PX)
    
    # Criamos a máscara baseada no desenho já no tamanho correto
    # Adicionamos um respiro para o processamento de filtros
    padding = sangria_px + linha_px + 10
    canvas_mask = Image.new("L", (img_desenho.width + padding*2, img_desenho.height + padding*2), 0)
    canvas_mask.paste(img_desenho.split()[3], (padding, padding))
    
    # Gerar a borda branca (Sangria)
    if sangria_px > 0:
        mask_sangria = canvas_mask.filter(ImageFilter.MaxFilter(tornar_impar(sangria_px * 2)))
        if suavidade > 0:
            mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(radius=suavidade/2))
            mask_sangria = mask_sangria.point(lambda p: 255 if p > 128 else 0)
    else:
        mask_sangria = canvas_mask

    # 4. MONTAGEM DA PEÇA FINAL
    peca_final = Image.new("RGBA", mask_sangria.size, (0, 0, 0, 0))
    
    # Fundo Branco
    peca_final.paste((255, 255, 255, 255), (0, 0), mask_sangria)
    
    # Linha Preta (opcional)
    if linha_ativa:
        mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(tornar_impar(linha_px if linha_px > 0 else 1)))
        peca_final.paste((0, 0, 0, 255), (0, 0), mask_linha)
        # Limpa o interior para a linha não cobrir o desenho
        interior = mask_sangria.filter(ImageFilter.MinFilter(3))
        peca_final.paste((0,0,0,0), (0,0), interior)

    # Colar o desenho original por cima (centralizado)
    off_x = (peca_final.width - img_desenho.width) // 2
    off_y = (peca_final.height - img_desenho.height) // 2
    peca_final.paste(img_desenho, (off_x, off_y), img_desenho)
    
    return peca_final.crop(peca_final.getbbox())

# --- FUNÇÃO DE MONTAGEM NO A4 ---
def montar_folhas_a4(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.1 * CM_TO_PX) # Espaço de 1mm entre peças para segurança
    folhas = []
    
    while pecas:
        folha = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255, 255, 255))
        cx, cy, lh = m_px, m_px, 0
        inseridos_indices = []
        
        for i, p in enumerate(pecas):
            pw, ph = p.size
            if cx + pw > A4_WIDTH_PX - m_px:
                cx = m_px
                cy += lh + e_px
                lh = 0
            
            if cy + ph <= A4_HEIGHT_PX - m_px:
                folha.paste(p, (cx, cy), p)
                cx += pw + e_px
                lh = max(lh, ph)
                inseridos_indices.append(i)
            else:
                break
        
        folhas.append(folha)
        for idx in sorted(inseridos_indices, reverse=True):
            pecas.pop(idx)
        if not inseridos_indices: break # Evitar loop infinito
            
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit - Precisão A4")

if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes de Folha")
    espessura = st.slider("Linha (mm)", 0.1, 3.0, 0.3)
    suavidade = st.slider("Suavização", 0, 30, 10)
    margem = st.slider("Margem Papel (cm)", 0.3, 1.5, 0.5)
    
    st.divider()
    st.header("📦 Sincronização em Massa")
    b_size = st.number_input("Tamanho (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Qtd", 1, 100, 24)
    b_sangria = st.slider("Sangria (cm)", 0.0, 1.0, 0.1)
    
    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_size
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_sangria
        st.rerun()

u = st.file_uploader("Suba seus PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    all_pieces_to_render = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                med = st.number_input("Desenho (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                qtd = st.number_input("Qtd Normal", 0, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 24))
            with c3:
                sang = st.slider("Sangria Externa (cm)", 0.0, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.1))
                qtd_e = st.number_input("Qtd Espelho", 0, 100, key=f"qe{i}", value=0)
                lin = st.checkbox("Linha Preta", True, key=f"l{i}")
            
            # Gerar Peças
            if qtd > 0:
                p_n = gerar_peca_precisa(item['img'], med, sang, lin, suavidade, espessura, False)
                for _ in range(qtd): all_pieces_to_render.append(p_n)
            if qtd_e > 0:
                p_e = gerar_peca_precisa(item['img'], med, sang, lin, suavidade, espessura, True)
                for _ in range(qtd_e): all_pieces_to_render.append(p_e)

    if st.button("🚀 GERAR PDF FINAL", use_container_width=True):
        folhas = montar_folhas_a4(all_pieces_to_render, margem)
        if folhas:
            for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}")
            
            pdf_out = io.BytesIO()
            # Forçamos a resolução de 300 DPI no salvamento do PDF
            folhas[0].save(pdf_out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0, subsampling=0, quality=100)
            st.download_button("📥 Baixar PDF A4 Real", pdf_out.getvalue(), "Bazzott_Final_A4.pdf", use_container_width=True)
