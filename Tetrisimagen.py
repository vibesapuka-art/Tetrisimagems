import streamlit as st
from PIL import Image, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS RÍGIDAS (A4 300 DPI) ---
DPI = 300
CM_TO_PX = 118.1102
A4_WIDTH_PX = int(21.0 * CM_TO_PX)  # 2480 px
A4_HEIGHT_PX = int(29.7 * CM_TO_PX) # 3508 px

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PRECISÃO PELO CONTEÚDO REAL ---
def gerar_peca_final(img, medida_cm, sangria_cm, linha_ativa, suavidade, espessura_mm, espelhar=False):
    img = img.convert("RGBA")
    
    # 1. ENCONTRA O CONTEÚDO REAL (Ignora transparência ao redor)
    bbox = img.getbbox()
    if not bbox:
        return None
    img_real = img.crop(bbox)
    
    if espelhar:
        img_real = ImageOps.mirror(img_real)

    # 2. REDIMENSIONAMENTO PROPORCIONAL PELO MAIOR LADO
    w, h = img_real.size
    maior_lado_px = medida_cm * CM_TO_PX
    escala = maior_lado_px / max(w, h)
    
    # Redimensiona mantendo a proporção exata para não achatar ou esticar
    novo_tamanho = (int(w * escala), int(h * escala))
    img_redimensionada = img_real.resize(novo_tamanho, Image.LANCZOS)

    # 3. CÁLCULO DE SANGRIA E LINHA (EXTERNOS AO DESENHO)
    sang_px = int(sangria_cm * CM_TO_PX)
    lin_px = int((espessura_mm / 10) * CM_TO_PX)
    
    padding = sang_px + lin_px + 10
    canvas_w = img_redimensionada.width + (padding * 2)
    canvas_h = img_redimensionada.height + (padding * 2)
    
    mask_alpha = Image.new("L", (canvas_w, canvas_h), 0)
    mask_alpha.paste(img_redimensionada.split()[3], (padding, padding))
    
    if sang_px > 0:
        mask_final = mask_alpha.filter(ImageFilter.MaxFilter(tornar_impar(sang_px * 2)))
        if suavidade > 0:
            mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=suavidade/2))
            mask_final = mask_final.point(lambda p: 255 if p > 128 else 0)
    else:
        mask_final = mask_alpha

    # 4. MONTAGEM DA PEÇA
    peca = Image.new("RGBA", mask_final.size, (0, 0, 0, 0))
    peca.paste((255, 255, 255, 255), (0, 0), mask_final)
    
    if linha_ativa:
        mask_contorno = mask_final.filter(ImageFilter.MaxFilter(tornar_impar(lin_px if lin_px > 0 else 1)))
        peca.paste((0, 0, 0, 255), (0, 0), mask_contorno)
        interior = mask_final.filter(ImageFilter.MinFilter(3))
        peca.paste((0,0,0,0), (0,0), interior)

    pos_x = (peca.width - img_redimensionada.width) // 2
    pos_y = (peca.height - img_redimensionada.height) // 2
    peca.paste(img_redimensionada, (pos_x, pos_y), img_redimensionada)
    
    return peca.crop(peca.getbbox())

# --- SISTEMA DE MONTAGEM A4 ---
def organizar_no_a4(lista_pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    espacamento_px = int(0.15 * CM_TO_PX) 
    folhas = []
    
    while lista_pecas:
        folha = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255, 255, 255))
        x, y, altura_linha = m_px, m_px, 0
        indices_removidos = []
        
        for i, p in enumerate(lista_pecas):
            pw, ph = p.size
            if x + pw > A4_WIDTH_PX - m_px:
                x = m_px
                y += altura_linha + espacamento_px
                altura_linha = 0
            
            if y + ph <= A4_HEIGHT_PX - m_px:
                folha.paste(p, (x, y), p)
                x += pw + espacamento_px
                altura_linha = max(altura_linha, ph)
                indices_removidos.append(i)
            else:
                break
        
        folhas.append(folha)
        for idx in sorted(indices_removidos, reverse=True):
            lista_pecas.pop(idx)
        if not indices_removidos: break 
            
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Love Edit", layout="wide")
st.title("✂️ Bazzott Love Edit - Tamanho Real")

if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes Globais")
    linha_w = st.slider("Linha (mm)", 0.1, 3.0, 0.3)
    suave = st.slider("Suavização", 0, 30, 10)
    margem_folha = st.slider("Margem Papel (cm)", 0.3, 2.0, 0.5)
    
    st.divider()
    st.header("📦 Sincronização em Massa")
    m_tamanho = st.number_input("Tamanho do Desenho (cm)", 1.0, 25.0, 4.0)
    m_qtd = st.number_input("Quantidade Total", 1, 100, 24)
    m_sangria = st.slider("Sangria (cm)", 0.0, 2.0, 0.1)
    
    if st.button("🔄 Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = m_tamanho
            st.session_state[f"q{i}"] = m_qtd
            st.session_state[f"s{i}"] = m_sangria
        st.rerun()

u = st.file_uploader("Upload PNG", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f)})

if st.session_state.galeria:
    fila_processamento = []
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                t_cm = st.number_input("Lado Maior (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                q_norm = st.number_input("Qtd Normal", 0, 100, key=f"q{i}", value=st.session_state.get(f"q{i}", 24))
            with c3:
                s_cm = st.slider("Sangria (cm)", 0.0, 2.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.1))
                q_esp = st.number_input("Qtd Espelho", 0, 100, key=f"qe{i}", value=0)
                l_ativa = st.checkbox("Linha Preta", True, key=f"l{i}")
            
            if q_norm > 0:
                p_n = gerar_peca_final(item['img'], t_cm, s_cm, l_ativa, suave, linha_w, False)
                if p_n: 
                    for _ in range(q_norm): fila_processamento.append(p_n)
            if q_esp > 0:
                p_e = gerar_peca_final(item['img'], t_cm, s_cm, l_ativa, suave, linha_w, True)
                if p_e: 
                    for _ in range(q_esp): fila_processamento.append(p_e)

    if st.button("🚀 GERAR PDF FINAL", use_container_width=True):
        folhas_finais = organizar_no_a4(fila_processamento, margem_folha)
        if folhas_finais:
            pdf_bytes = io.BytesIO()
            folhas_finais[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas_finais[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF Precisão", pdf_bytes.getvalue(), "Bazzott_Precision.pdf", use_container_width=True)
