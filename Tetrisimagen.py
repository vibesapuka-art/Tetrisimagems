import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import io

# --- CONFIGURAÇÕES TÉCNICAS RÍGIDAS (300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar=False):
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox: img = img.crop(bbox)
    if espelhar: img = ImageOps.mirror(img)

    # 1. Redimensiona o desenho para o tamanho real escolhido (SEM contar a sangria ainda)
    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    proporcao = alvo_px / max(w, h)
    img_redimensionada = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    # 2. Calcula a sangria externa
    dist_px = int(sangria_cm * CM_TO_PX)
    
    if dist_px > 0:
        # Criamos um espaço maior para a sangria não ser cortada na borda da imagem individual
        padding = dist_px + 5
        mask_canvas = Image.new("L", (img_redimensionada.width + padding*2, img_redimensionada.height + padding*2), 0)
        mask_canvas.paste(img_redimensionada.split()[3], (padding, padding))
        
        # Gera o contorno (MaxFilter)
        # Garantimos que o filtro seja ímpar para precisão
        filtro_size = dist_px if dist_px % 2 != 0 else dist_px + 1
        mask = mask_canvas.filter(ImageFilter.MaxFilter(filtro_size))
        
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
            
        peca_final = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        
        # Linha de corte (opcional)
        if linha_ativa:
            linha_mask = mask.filter(ImageFilter.MaxFilter(3))
            peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
        
        # Fundo da sangria (Branco)
        peca_final.paste((255, 255, 255, 255), (0, 0), mask)
        
        # Cola o desenho original por cima, centralizado
        off_x = (peca_final.width - img_redimensionada.width) // 2
        off_y = (peca_final.height - img_redimensionada.height) // 2
        peca_final.paste(img_redimensionada, (off_x, off_y), img_redimensionada)
    else:
        peca_final = img_redimensionada

    return peca_final.crop(peca_final.getbbox())

def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.05 * CM_TO_PX) # Espaço mínimo entre sangrias (0.5mm)
    folhas = []
    lista_pendente = pecas.copy()
    
    while lista_pendente:
        folha_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        camada_png = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x = m_px
                y += h_linha + e_px
                h_linha = 0
            
            if y + ph <= A4_HEIGHT - m_px:
                camada_png.paste(p, (x, y), p)
                x += pw + e_px
                h_linha = max(h_linha, ph)
                inseridos.append(i)
            else:
                break
        
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        folha_branca.paste(camada_png, (0, 0), camada_png)
        folhas.append(folha_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Studio PRO FIX", layout="wide")
if 'galeria' not in st.session_state: st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajuste de Folha")
    margem = st.slider("Margem Papel (cm)", 0.3, 1.5, 0.7)
    suave = st.slider("Suavização", 0, 20, 5)
    if st.button("🗑️ LIMPAR TUDO"):
        st.session_state.galeria = []
        st.rerun()

u = st.file_uploader("Suba seus PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [item['name'] for item in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f).copy()})

if st.session_state.galeria:
    pecas_pdf = []
    total_count = 0
    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                t = st.number_input("Tamanho do Desenho (cm)", 1.0, 25.0, key=f"m{i}", value=4.0)
                qn = st.number_input("Qtd Normal", 0, 500, key=f"q{i}", value=12)
            with c3:
                qe = st.number_input("Qtd Espelhado (Clone)", 0, 500, key=f"qe{i}", value=0)
                s = st.slider("Sangria Externa (cm)", 0.0, 1.0, key=f"s{i}", value=0.20, step=0.05)
            
            # Gera as peças com o desenho no tamanho T e a sangria S por fora
            if qn > 0:
                p_n = gerar_contorno_individual(item['img'], t, s, True, suave, False)
                for _ in range(qn): pecas_pdf.append(p_n)
            if qe > 0:
                p_e = gerar_contorno_individual(item['img'], t, s, True, suave, True)
                for _ in range(qe): pecas_pdf.append(p_e)

    if st.button(f"🚀 GERAR PDF", use_container_width=True):
        folhas = montar_folhas(pecas_pdf, margem)
        for idx, f in enumerate(folhas): st.image(f, caption=f"Página {idx+1}")
        pdf_out = io.BytesIO()
        folhas[0].save(pdf_out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
        st.download_button("📥 BAIXAR PDF", pdf_out.getvalue(), "Bazzott_Precision.pdf", use_container_width=True)
