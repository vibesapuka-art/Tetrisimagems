import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS RÍGIDAS (300 DPI) ---
# A4 em pixels a 300 DPI: 2480 x 3508
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11  # Fator real para 300 DPI (1 polegada = 2.54cm = 300px)

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE CONTORNO COM ESCALA REAL ---
def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar=False):
    img = img.convert("RGBA")
    bbox_limpeza = img.getbbox()
    if bbox_limpeza:
        img = img.crop(bbox_limpeza)

    if espelhar:
        img = ImageOps.mirror(img)

    # CÁLCULO DE ESCALA PRECISO
    # O tamanho final da imagem (sem sangria) deve ser exatamente medida_cm
    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    # Redimensiona mantendo a proporção baseada na maior dimensão
    proporcao = alvo_px / max(w, h)
    img = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    dist_px = int(tornar_impar(sangria_cm * CM_TO_PX))
    
    if dist_px > 0:
        padding = dist_px + 10
        canvas_alpha = Image.new("L", (img.width + padding*2, img.height + padding*2), 0)
        canvas_alpha.paste(img.split()[3], (padding, padding))
        mask = canvas_alpha.filter(ImageFilter.MaxFilter(dist_px))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img.split()[3].point(lambda p: 255 if p > 128 else 0)

    peca_final = Image.new("RGBA", mask.size if dist_px > 0 else img.size, (0, 0, 0, 0))
    
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3))
        peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
    
    peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    
    off_x = (peca_final.width - img.width) // 2
    off_y = (peca_final.height - img.height) // 2
    peca_final.paste(img, (off_x, off_y), img)
    
    return peca_final.crop(peca_final.getbbox())

# --- MONTAGEM DA FOLHA (SEM REDIMENSIONAMENTO) ---
def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.2 * CM_TO_PX) # Espaço fixo entre figuras
    folhas = []
    lista_pendente = pecas.copy()
    
    while lista_pendente:
        # Fundo Branco A4 Puro
        folha_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        camada_png = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            
            # Quebra de linha se passar da largura
            if x + pw > A4_WIDTH - m_px:
                x = m_px
                y += h_linha + e_px
                h_linha = 0
            
            # Se couber na altura, cola
            if y + ph <= A4_HEIGHT - m_px:
                camada_png.paste(p, (x, y), p)
                x += pw + e_px
                h_linha = max(h_linha, ph)
                inseridos.append(i)
            else:
                break
        
        if not inseridos: break
        
        for idx in sorted(inseridos, reverse=True):
            lista_pendente.pop(idx)
        
        # Une a camada das imagens com o fundo branco
        folha_branca.paste(camada_png, (0, 0), camada_png)
        folhas.append(folha_branca)
        
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Studio Precision", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes de Folha")
    margem = st.slider("Margem da Folha (cm)", 0.5, 2.0, 0.8)
    suave = st.slider("Suavização", 0, 30, 10)
    if st.button("🗑️ LIMPAR TUDO"):
        st.session_state.galeria = []
        st.rerun()

u = st.file_uploader("Adicionar novos PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [item['name'] for item in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f).copy()})

if st.session_state.galeria:
    pecas_para_pdf = []
    total_figuras = 0
    indices_para_remover = []

    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3, c4 = st.columns([1, 2, 2, 0.5])
            with c1: st.image(item['img'], width=80)
            with c2:
                t = st.number_input("Tam Real (cm)", 1.0, 25.0, key=f"m{i}", value=4.0)
                q_n = st.number_input("Qtd Normal", 1, 500, key=f"q{i}", value=10)
            with c3:
                q_e = st.number_input("Qtd Espelhado", 0, 500, key=f"qe{i}", value=10)
                s = st.slider("Sangria (cm)", 0.0, 1.0, key=f"s{i}", value=0.20, step=0.05)
            with c4:
                if st.button("❌", key=f"del_{i}"): indices_para_remover.append(i)
                l = st.checkbox("Corte", True, key=f"l{i}")

            # Processa Normal
            p_n = gerar_contorno_individual(item['img'], t, s, l, suave, False)
            for _ in range(q_n): 
                pecas_para_pdf.append(p_n)
                total_figuras += 1
            # Processa Espelhado
            if q_e > 0:
                p_e = gerar_contorno_individual(item['img'], t, s, l, suave, True)
                for _ in range(q_e):
                    pecas_para_pdf.append(p_e)
                    total_figuras += 1

    if indices_para_remover:
        for idx in sorted(indices_para_remover, reverse=True): st.session_state.galeria.pop(idx)
        st.rerun()

    if st.button(f"🚀 GERAR PDF ({total_figuras} itens)", use_container_width=True):
        folhas = montar_folhas(pecas_para_pdf, margem)
        for idx, f in enumerate(folhas):
            st.image(f, caption=f"Página {idx+1} - Visualize em 100% para conferir o tamanho")
        
        pdf_out = io.BytesIO()
        folhas[0].save(pdf_out, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
        st.download_button("📥 BAIXAR PDF", pdf_out.getvalue(), "Studio_Bazzott_RealSize.pdf", use_container_width=True)
