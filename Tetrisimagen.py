import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps
import io

# --- CONFIGURAÇÕES TÉCNICAS (PRECISÃO 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE CONTORNO ---
def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar):
    bbox_limpeza = img.getbbox()
    if bbox_limpeza:
        img = img.crop(bbox_limpeza)

    # NOVO: Espelhar a imagem se o checkbox estiver marcado
    if espelhar:
        img = ImageOps.mirror(img)

    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS).convert("RGBA")

    dist_px = int(sangria_cm * CM_TO_PX)
    
    if dist_px > 0:
        padding = dist_px + 40
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
    
    if dist_px > 0:
        off_x = (peca_final.width - img.width) // 2
        off_y = (peca_final.height - img.height) // 2
        peca_final.paste(img, (off_x, off_y), img)
    else:
        peca_final.paste(img, (0, 0), img)
    
    return peca_final.crop(peca_final.getbbox())

# --- MONTAGEM DA FOLHA ---
def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX) 
    folhas = []
    lista_pendente = pecas.copy()
    
    while lista_pendente:
        folha = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x, y, h_linha = m_px, y + h_linha + e_px, 0
            if y + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (x, y), p)
                x, h_linha = x + pw + e_px, max(h_linha, ph)
                inseridos.append(i)
            else: break
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Studio Pro", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Configurações Globais")
    margem = st.slider("Margem da Folha (cm)", 0.5, 2.0, 1.0)
    suave = st.slider("Suavização do Corte", 0, 30, 15)
    
    st.divider()
    if st.button("Limpar Galeria"):
        st.session_state.galeria = []
        st.rerun()

u = st.file_uploader("Adicionar novos PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        img_data = Image.open(f).copy()
        # Voltamos a usar apenas o nome do arquivo como identificador
        st.session_state.galeria.append({"name": f.name, "img": img_data})
    st.rerun()

if st.session_state.galeria:
    pecas_para_pdf = []
    total_figuras = 0
    indices_para_remover = []

    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            col_img, col_cfg, col_sang, col_del = st.columns([1, 2, 2, 0.5])
            
            with col_img: 
                st.image(item['img'], width=80)
                # Checkbox simples de espelhar
                esp = st.checkbox("Espelhar", key=f"esp_{i}")
            
            with col_cfg:
                t = st.number_input("Tam (cm)", 1.0, 25.0, key=f"m{i}", value=4.0)
                q = st.number_input("Qtd", 1, 500, key=f"q{i}", value=10)
            
            with col_sang:
                s = st.slider("Sangria (cm)", 0.0, 1.0, key=f"s{i}", value=0.25, step=0.05)
                l = st.checkbox("Linha Corte", True, key=f"l{i}")
            
            with col_del:
                if st.button("❌", key=f"del_{i}"):
                    indices_para_remover.append(i)
            
            # Chama a função passando o estado do espelhamento
            p_processada = gerar_contorno_individual(item['img'], t, s, l, suave, esp)
            for _ in range(q): 
                pecas_para_pdf.append(p_processada)
                total_figuras += 1

    if indices_para_remover:
        for idx in sorted(indices_para_remover, reverse=True):
            st.session_state.galeria.pop(idx)
        st.rerun()

    if st.button(f"🚀 GERAR PDF COM {total_figuras} FIGURAS", use_container_width=True):
        folhas_finais = montar_folhas(pecas_para_pdf, margem)
        if folhas_finais:
            for idx, f in enumerate(folhas_finais): 
                st.image(f, caption=f"Página {idx+1}")
            
            pdf_output = io.BytesIO()
            folhas_finais[0].save(pdf_output, format="PDF", save_all=True, append_images=folhas_finais[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF Final", pdf_output.getvalue(), "Bazzott_Studio.pdf", use_container_width=True)
